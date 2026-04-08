import os
from datetime import date, timedelta
from typing import Literal

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException

from db.database import get_db
from models.health import CyclePhaseResponse, HealthSyncPayload, HealthSyncResponse, HealthSyncSummary

router = APIRouter(prefix="/health", tags=["health"])

_PHASE_LABELS: dict[str, str] = {
    "menstrual":  "Fase mestruale",
    "follicular": "Fase follicolare",
    "ovulatory":  "Fase ovulatoria",
    "luteal":     "Fase luteale",
}


def _find_period_starts(flow_rows: list[dict]) -> list[date]:
    """
    Trova il primo giorno di ogni ciclo mestruale usando clustering.

    Strategia: raggruppa tutti i record con gap ≤ 2 giorni in cluster.
    Un cluster è un "periodo" se ha almeno un giorno con flusso reale
    oppure ha ≥ 3 giorni consecutivi (alcune app segnano solo "giorno ciclo"
    senza specificare il livello, usando 'not_present').
    """
    if not flow_rows:
        return []

    sorted_rows = sorted(flow_rows, key=lambda r: r["date"])
    clusters: list[list[dict]] = []
    current: list[dict] = [sorted_rows[0]]

    for row in sorted_rows[1:]:
        gap = (date.fromisoformat(row["date"]) - date.fromisoformat(current[-1]["date"])).days
        if gap <= 2:
            current.append(row)
        else:
            clusters.append(current)
            current = [row]
    clusters.append(current)

    starts: list[date] = []
    for cluster in clusters:
        has_real_flow = any(r["flow_level"] != "not_present" for r in cluster)
        if has_real_flow or len(cluster) >= 3:
            starts.append(date.fromisoformat(cluster[0]["date"]))
    return starts


def _calculate_cycle_phase(
    flow_rows: list[dict],
    today: date,
) -> CyclePhaseResponse | None:
    """
    Calcola la fase del ciclo mestruale dal log dei flussi.

    Ritorna None se non ci sono dati sufficienti.
    """
    if not flow_rows:
        return None

    period_starts = _find_period_starts(flow_rows)
    if not period_starts:
        return None

    last_start = period_starts[-1]
    cycle_day = (today - last_start).days + 1
    if cycle_day < 1:
        return None

    # Lunghezza media ciclo — clampata a intervallo fisiologico
    if len(period_starts) >= 2:
        gaps = [(period_starts[i + 1] - period_starts[i]).days
                for i in range(len(period_starts) - 1)]
        avg_length = max(21, min(35, round(sum(gaps) / len(gaps))))
    else:
        avg_length = 28

    # Fase basata su proporzione del ciclo (si adatta alla lunghezza individuale)
    pct = (cycle_day - 1) / avg_length
    if pct < 5 / 28:
        phase: Literal["menstrual", "follicular", "ovulatory", "luteal"] = "menstrual"
    elif pct < 13 / 28:
        phase = "follicular"
    elif pct < 16 / 28:
        phase = "ovulatory"
    else:
        phase = "luteal"

    next_period = last_start + timedelta(days=avg_length)
    days_until = (next_period - today).days

    return CyclePhaseResponse(
        phase=phase,
        phase_label=_PHASE_LABELS[phase],
        cycle_day=cycle_day,
        cycle_length_avg=avg_length,
        period_start=last_start.isoformat(),
        next_period_estimate=next_period.isoformat(),
        days_until_next_period=days_until,
    )

# Token condiviso con l'app iOS — imposta la variabile d'ambiente IOS_APP_TOKEN.
# Default al placeholder usato in APIConfig.swift durante lo sviluppo.
_DEFAULT_TOKEN = "PLACEHOLDER_TOKEN"


def _verify_token(x_app_token: str = Header(...)) -> None:
    """Verifica il token di autenticazione inviato dall'app iOS (header X-App-Token)."""
    expected = os.getenv("IOS_APP_TOKEN", _DEFAULT_TOKEN)
    if x_app_token != expected:
        raise HTTPException(status_code=401, detail="Token non valido")


@router.post("/sync", response_model=HealthSyncResponse, status_code=200)
async def sync_health_data(
    payload: HealthSyncPayload,
    db: aiosqlite.Connection = Depends(get_db),
    _: None = Depends(_verify_token),
) -> HealthSyncResponse:
    """
    Riceve e persiste i dati salute inviati dall'app iOS.

    Ogni tipo di dato ha la sua tabella. Upsert basato su date/timestamp:
    una seconda sync sullo stesso giorno aggiorna i valori esistenti.
    """
    print(f"[HEALTH SYNC] Requested sync from HealthKit", flush=True)
    counts: dict[str, int] = {}

    # Step count giornaliero
    if payload.steps:
        await db.executemany(
            """INSERT INTO health_steps (date, steps) VALUES (?, ?)
               ON CONFLICT(date) DO UPDATE SET steps = excluded.steps""",
            [(s.date, s.steps) for s in payload.steps],
        )
        counts["steps"] = len(payload.steps)

    # Sleep analysis
    if payload.sleep:
        await db.executemany(
            """INSERT INTO health_sleep
                   (date, sleep_start, sleep_end, total_sleep_minutes,
                    deep_sleep_minutes, rem_sleep_minutes, core_sleep_minutes)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   sleep_start          = excluded.sleep_start,
                   sleep_end            = excluded.sleep_end,
                   total_sleep_minutes  = excluded.total_sleep_minutes,
                   deep_sleep_minutes   = excluded.deep_sleep_minutes,
                   rem_sleep_minutes    = excluded.rem_sleep_minutes,
                   core_sleep_minutes   = excluded.core_sleep_minutes""",
            [
                (
                    s.date, s.sleep_start, s.sleep_end, s.total_sleep_minutes,
                    s.deep_sleep_minutes, s.rem_sleep_minutes, s.core_sleep_minutes,
                )
                for s in payload.sleep
            ],
        )
        counts["sleep"] = len(payload.sleep)

    # Campioni FC puntuali (INSERT OR IGNORE: stesso timestamp = stesso campione)
    if payload.heart_rate_samples:
        await db.executemany(
            """INSERT OR IGNORE INTO health_heart_rate_samples (timestamp, bpm, source)
               VALUES (?, ?, ?)""",
            [(s.timestamp, s.bpm, s.source) for s in payload.heart_rate_samples],
        )
        counts["heart_rate_samples"] = len(payload.heart_rate_samples)

    # FC media/min/max giornaliera
    if payload.daily_heart_rate:
        await db.executemany(
            """INSERT INTO health_daily_heart_rate (date, avg_bpm, min_bpm, max_bpm)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   avg_bpm = excluded.avg_bpm,
                   min_bpm = excluded.min_bpm,
                   max_bpm = excluded.max_bpm""",
            [(d.date, d.avg_bpm, d.min_bpm, d.max_bpm) for d in payload.daily_heart_rate],
        )
        counts["daily_heart_rate"] = len(payload.daily_heart_rate)

    # FC a riposo giornaliera
    if payload.resting_heart_rate:
        await db.executemany(
            """INSERT INTO health_resting_heart_rate (date, bpm) VALUES (?, ?)
               ON CONFLICT(date) DO UPDATE SET bpm = excluded.bpm""",
            [(r.date, r.bpm) for r in payload.resting_heart_rate],
        )
        counts["resting_heart_rate"] = len(payload.resting_heart_rate)

    # HRV SDNN (INSERT OR IGNORE: stesso timestamp = stesso campione)
    if payload.hrv:
        await db.executemany(
            """INSERT OR IGNORE INTO health_hrv (timestamp, sdnn_ms) VALUES (?, ?)""",
            [(h.timestamp, h.sdnn_ms) for h in payload.hrv],
        )
        counts["hrv"] = len(payload.hrv)

    # Energia attiva giornaliera
    if payload.active_energy:
        await db.executemany(
            """INSERT INTO health_active_energy (date, kcal) VALUES (?, ?)
               ON CONFLICT(date) DO UPDATE SET kcal = excluded.kcal""",
            [(e.date, e.kcal) for e in payload.active_energy],
        )
        counts["active_energy"] = len(payload.active_energy)

    # Flusso mestruale giornaliero (upsert per data)
    if payload.menstrual_flow:
        await db.executemany(
            """INSERT INTO health_menstrual_flow (date, flow_level) VALUES (?, ?)
               ON CONFLICT(date) DO UPDATE SET flow_level = excluded.flow_level""",
            [(m.date, m.flow_level) for m in payload.menstrual_flow],
        )
        counts["menstrual_flow"] = len(payload.menstrual_flow)

    # Workout (INSERT OR IGNORE: UUID immutabile per ogni workout)
    if payload.workouts:
        await db.executemany(
            """INSERT OR IGNORE INTO health_workouts
                   (id, activity_type, start_date, end_date,
                    duration_seconds, total_energy_kcal, total_distance_meters, source_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    w.id, w.activity_type, w.start_date, w.end_date,
                    w.duration_seconds, w.total_energy_kcal, w.total_distance_meters, w.source_name,
                )
                for w in payload.workouts
            ],
        )
        counts["workouts"] = len(payload.workouts)

    # Logga la sync per poter mostrare "ultima sync" nell'app iOS
    await db.execute(
        "INSERT INTO health_sync_log (synced_at) VALUES (?)",
        (payload.synced_at,),
    )

    await db.commit()

    total = sum(counts.values())
    print(f"[HEALTH SYNC] data found from sync: {payload}", flush=True)
    return HealthSyncResponse(
        received=True,
        message=f"Sync completata: {total} record ricevuti",
        counts=counts,
    )


@router.get("/summary", response_model=HealthSyncSummary)
async def get_health_sync_summary(
    db: aiosqlite.Connection = Depends(get_db),
    _: None = Depends(_verify_token),
) -> HealthSyncSummary:
    """
    Restituisce i conteggi dei dati salute presenti nel DB.

    Usato dall'app iOS per mostrare quanti dati sono già stati importati
    rispetto a quelli disponibili in HealthKit.
    """
    async with db.execute("""
        SELECT
            (SELECT COUNT(*)        FROM health_workouts)          AS workout_count,
            (SELECT COUNT(*)        FROM health_steps)             AS step_days,
            (SELECT COUNT(*)        FROM health_sleep)             AS sleep_days,
            (SELECT COUNT(*)        FROM health_resting_heart_rate) AS resting_hr_days,
            (SELECT COUNT(DISTINCT DATE(timestamp)) FROM health_hrv) AS hrv_days,
            (SELECT COUNT(*)        FROM health_active_energy)     AS active_energy_days,
            (SELECT MAX(synced_at)  FROM health_sync_log)          AS last_sync_at
    """) as cur:
        row = await cur.fetchone()

    return HealthSyncSummary(
        workout_count=row["workout_count"] or 0,
        step_days=row["step_days"] or 0,
        sleep_days=row["sleep_days"] or 0,
        resting_hr_days=row["resting_hr_days"] or 0,
        hrv_days=row["hrv_days"] or 0,
        active_energy_days=row["active_energy_days"] or 0,
        last_sync_at=row["last_sync_at"],
    )


@router.get("/cycle/current", response_model=CyclePhaseResponse)
async def get_current_cycle_phase(
    db: aiosqlite.Connection = Depends(get_db),
) -> CyclePhaseResponse:
    """
    Restituisce la fase del ciclo mestruale corrente calcolata dallo storico dei flussi.

    - Identifica gli inizi ciclo (primo giorno con flusso dopo gap ≥ 3 giorni).
    - Calcola la durata media del ciclo dai gap storici (default 28 giorni).
    - Determina la fase attuale in base al giorno del ciclo:
      - Mestruale: giorni 1–5 (proporzionale)
      - Follicolare: giorni 6–13
      - Ovulatoria: giorni 14–16
      - Luteale: giorni 17–fine ciclo

    Ritorna 404 se non ci sono dati sufficienti (nessun flusso registrato).
    """
    # Ultimi 18 mesi: necessario per calcolare durata media ciclo con dati storici sufficienti
    from_date = (date.today() - timedelta(days=548)).isoformat()

    async with db.execute(
        """SELECT date, flow_level FROM health_menstrual_flow
           WHERE date >= ? ORDER BY date ASC""",
        (from_date,),
    ) as cur:
        rows = await cur.fetchall()

    flow_data = [{"date": r["date"], "flow_level": r["flow_level"]} for r in rows]
    result = _calculate_cycle_phase(flow_data, date.today())

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Nessun dato sul ciclo mestruale disponibile. Sincronizza i dati salute dall'app iOS.",
        )
    
    print(f"[HEALTH CYCLE PHASE] phase calculated: {result}", flush=True)
    return result
