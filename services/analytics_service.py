"""
Orchestratore del calcolo delle metriche avanzate di fitness e recupero.

Flusso principale:
    compute_analytics(db)
        ├── compute_workout_metrics(db)   → analytics_workout (upsert per workout)
        └── compute_daily_metrics(db)     → analytics_daily (upsert per giorno)

Idempotente: può essere rieseguita senza duplicare dati.
Le query DB sono in analytics_queries.py, la logica di calcolo è in
analytics_workout.py e analytics_daily.py.
"""

import aiosqlite

from services.analytics_daily import compute_daily_metrics
from services.analytics_workout import compute_workout_metrics
from services.analytics_queries import get_reference_max_hr
from utils.metrics import RACE_DISTANCES, format_seconds, riegel_predict

# Mappa tipi HealthKit normalizzati → categoria "corsa" per le previsioni Riegel
_RUNNING_TYPES = ("running",)


async def compute_analytics(db: aiosqlite.Connection) -> tuple[int, int]:
    """
    Esegue il calcolo completo in due fasi:
    1. Metriche per workout (training load, stima load energetica)
    2. Metriche giornaliere (CTL/ATL/TSB, ACWR, recovery, sleep, baselines)

    Ritorna (n_workouts, n_days) processati.
    """
    n_workouts = await compute_workout_metrics(db)
    n_days     = await compute_daily_metrics(db)
    return n_workouts, n_days


async def get_race_predictions(
    db: aiosqlite.Connection,
    sport_types: list[str] | None = None,
) -> object | None:
    """
    Genera le previsioni Riegel per le 4 distanze standard.

    Sorgente: il workout running con miglior pace tra gli ultimi 20 workout validi
    (distanza > 5 km, duration_seconds > 0).

    Ritorna None se non ci sono workout validi.
    """
    # Accetta sia "Run"/"TrailRun" (stile legacy) che "running" (HealthKit)
    if sport_types is None:
        hk_types = list(_RUNNING_TYPES)
    else:
        hk_types = _normalize_sport_types(sport_types)
        if not hk_types:
            hk_types = list(_RUNNING_TYPES)

    placeholders = ",".join("?" * len(hk_types))

    async with db.execute(
        f"""SELECT id, activity_type, start_date,
                   total_distance_meters, duration_seconds
            FROM health_workouts
            WHERE activity_type IN ({placeholders})
              AND total_distance_meters > 5000
              AND duration_seconds > 0
            ORDER BY start_date DESC
            LIMIT 20""",
        hk_types,
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return None

    # Miglior pace = durata minima per unità di distanza
    best = min(rows, key=lambda r: r["duration_seconds"] / r["total_distance_meters"])
    d1_km = best["total_distance_meters"] / 1000.0
    t1_s  = float(best["duration_seconds"])

    from models.analytics import RacePredictionItem, RacePredictionsResponse

    predictions = [
        RacePredictionItem(
            distance_label=label,
            distance_km=d2_km,
            predicted_seconds=int(riegel_predict(t1_s, d1_km, d2_km)),
            predicted_time=format_seconds(riegel_predict(t1_s, d1_km, d2_km)),
        )
        for label, d2_km in RACE_DISTANCES
    ]

    return RacePredictionsResponse(
        source_distance_km=round(d1_km, 3),
        source_time_seconds=int(t1_s),
        source_activity_name=f"Corsa {round(d1_km, 1)} km",
        source_date=best["start_date"],
        sport_type=best["activity_type"],
        predictions=predictions,
    )


def _normalize_sport_types(sport_types: list[str]) -> list[str]:
    """Normalizza i tipi sport legacy (Strava-style) verso tipi HealthKit lowercase."""
    _MAP = {
        "Run":      "running",
        "TrailRun": "running",
        "Hike":     "hiking",
        "Walk":     "walking",
        "Cycling":  "cycling",
    }
    result: list[str] = []
    for s in sport_types:
        mapped = _MAP.get(s, s.lower())
        if mapped not in result:
            result.append(mapped)
    return result
