from datetime import UTC, datetime, timedelta

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query

from db.database import get_db
from dependencies import require_auth
from models.analytics import (
    ActivityMetrics,
    ComputeResult,
    DailyMetrics,
    FitnessPoint,
    RacePredictionsResponse,
)
from services.analytics_service import compute_analytics, get_race_predictions

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_auth)])


@router.post("/compute", response_model=ComputeResult, status_code=200)
async def trigger_compute(
    db: aiosqlite.Connection = Depends(get_db),
) -> ComputeResult:
    """
    Avvia il calcolo (o ricalcolo) di tutte le metriche derivate.

    Fase 1: metriche per singola attività (training load, zone HR, efficienza, trail effort).
    Fase 2: metriche giornaliere (CTL/ATL/TSB, ACWR, recovery score, sleep score, baselines).

    L'operazione è idempotente: può essere eseguita più volte senza effetti collaterali.
    Da richiamare dopo ogni sync Strava o sync health iOS per aggiornare i dati.
    """
    n_activities, n_days = await compute_analytics(db)
    return ComputeResult(
        activities_processed=n_activities,
        days_processed=n_days,
        message=f"Calcolo completato: {n_activities} attività, {n_days} giorni processati.",
    )


@router.get("/workout/{workout_id}", response_model=ActivityMetrics)
async def get_workout_metrics(
    workout_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> ActivityMetrics:
    """Metriche derivate per un singolo workout HealthKit (training load, efficienza)."""
    async with db.execute(
        """SELECT workout_id, training_load, load_method,
                  efficiency_factor, equivalent_dist_km, trail_effort, computed_at
           FROM analytics_workout
           WHERE workout_id = ?""",
        (workout_id,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Metriche non ancora calcolate per questo workout. Esegui POST /analytics/compute.",
        )

    return ActivityMetrics(
        workout_id=row["workout_id"],
        training_load=row["training_load"],
        load_method=row["load_method"],
        efficiency_factor=row["efficiency_factor"],
        equivalent_dist_km=row["equivalent_dist_km"],
        trail_effort=row["trail_effort"],
        computed_at=row["computed_at"],
    )


@router.get("/daily", response_model=list[DailyMetrics])
async def get_daily_metrics(
    from_date: str | None = Query(None, description="Data inizio ISO (es. 2024-01-01)"),
    to_date: str | None = Query(None, description="Data fine ISO (es. 2024-12-31)"),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[DailyMetrics]:
    """
    Metriche aggregate giornaliere in un intervallo di date.

    Default: ultimi 90 giorni se nessun intervallo è specificato.
    """
    if to_date is None:
        to_date = datetime.now(UTC).date().isoformat()
    if from_date is None:
        from_date = (datetime.now(UTC).date() - timedelta(days=90)).isoformat()

    async with db.execute(
        """SELECT date, daily_load, ctl, atl, tsb, acwr,
                  recovery_score, sleep_score,
                  hrv_baseline, hrv_delta, hrv_zscore,
                  rhr_baseline, rhr_delta,
                  sleep_baseline, sleep_delta, computed_at
           FROM analytics_daily
           WHERE date >= ? AND date <= ?
           ORDER BY date ASC""",
        (from_date, to_date),
    ) as cur:
        rows = await cur.fetchall()

    return [
        DailyMetrics(
            date=r["date"],
            daily_load=r["daily_load"] or 0.0,
            ctl=r["ctl"],
            atl=r["atl"],
            tsb=r["tsb"],
            acwr=r["acwr"],
            recovery_score=r["recovery_score"],
            sleep_score=r["sleep_score"],
            hrv_baseline=r["hrv_baseline"],
            hrv_delta=r["hrv_delta"],
            hrv_zscore=r["hrv_zscore"],
            rhr_baseline=r["rhr_baseline"],
            rhr_delta=r["rhr_delta"],
            sleep_baseline=r["sleep_baseline"],
            sleep_delta=r["sleep_delta"],
            computed_at=r["computed_at"],
        )
        for r in rows
    ]


@router.get("/fitness", response_model=list[FitnessPoint])
async def get_fitness_curve(
    days: int = Query(90, ge=7, le=365, description="Numero di giorni di storico"),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[FitnessPoint]:
    """
    Curva CTL/ATL/TSB (Performance Management Chart) per gli ultimi N giorni.

    Utile per la dashboard: visualizza fitness, fatica e forma nel tempo.
    Ritorna solo i giorni con CTL/ATL calcolati (esclude i giorni senza dati).
    """
    from_date = (datetime.now(UTC).date() - timedelta(days=days)).isoformat()

    async with db.execute(
        """SELECT date, daily_load, ctl, atl, tsb
           FROM analytics_daily
           WHERE date >= ? AND ctl IS NOT NULL
           ORDER BY date ASC""",
        (from_date,),
    ) as cur:
        rows = await cur.fetchall()

    return [
        FitnessPoint(
            date=r["date"],
            ctl=r["ctl"],
            atl=r["atl"],
            tsb=r["tsb"],
            daily_load=r["daily_load"] or 0.0,
        )
        for r in rows
    ]


@router.get("/recovery", response_model=list[DailyMetrics])
async def get_recovery_metrics(
    days: int = Query(30, ge=7, le=90, description="Numero di giorni di storico"),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[DailyMetrics]:
    """
    Recovery score, sleep score e baselines HRV/RHR per gli ultimi N giorni.

    Sottoinsieme di /analytics/daily focalizzato sul recupero.
    """
    from_date = (datetime.now(UTC).date() - timedelta(days=days)).isoformat()

    async with db.execute(
        """SELECT date, daily_load, ctl, atl, tsb, acwr,
                  recovery_score, sleep_score,
                  hrv_baseline, hrv_delta, hrv_zscore,
                  rhr_baseline, rhr_delta,
                  sleep_baseline, sleep_delta, computed_at
           FROM analytics_daily
           WHERE date >= ? AND (recovery_score IS NOT NULL OR sleep_score IS NOT NULL)
           ORDER BY date DESC""",
        (from_date,),
    ) as cur:
        rows = await cur.fetchall()

    return [
        DailyMetrics(
            date=r["date"],
            daily_load=r["daily_load"] or 0.0,
            ctl=r["ctl"],
            atl=r["atl"],
            tsb=r["tsb"],
            acwr=r["acwr"],
            recovery_score=r["recovery_score"],
            sleep_score=r["sleep_score"],
            hrv_baseline=r["hrv_baseline"],
            hrv_delta=r["hrv_delta"],
            hrv_zscore=r["hrv_zscore"],
            rhr_baseline=r["rhr_baseline"],
            rhr_delta=r["rhr_delta"],
            sleep_baseline=r["sleep_baseline"],
            sleep_delta=r["sleep_delta"],
            computed_at=r["computed_at"],
        )
        for r in rows
    ]


@router.get("/race-predictions", response_model=RacePredictionsResponse)
async def race_predictions_all(
    sport_types: list[str] = Query(
        default=[],
        description="Sport da considerare (default: Run, TrailRun)",
    ),
    db: aiosqlite.Connection = Depends(get_db),
) -> RacePredictionsResponse:
    """
    Previsioni Riegel per 5 km, 10 km, mezza maratona e maratona.

    Performance sorgente: la run con il miglior pace tra le ultime 20
    attività valide (distanza > 5 km). Seleziona automaticamente
    la prestazione più rappresentativa del potenziale attuale.

    Ritorna 404 se non ci sono attività valide.
    """
    result = await get_race_predictions(
        db,
        sport_types=sport_types if sport_types else None,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Nessuna run valida (distanza > 5 km) trovata nel database.",
        )
    return result
