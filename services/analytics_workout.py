"""
Calcolo metriche per singolo workout HealthKit → tabella analytics_workout.

Sostituisce analytics_activity.py (che leggeva dalla tabella Strava `activities`).
I workout HealthKit non hanno dati HR granulari: il training load viene stimato
dall'energia calcolata (kcal) quando disponibile.
"""

from datetime import UTC, datetime

import aiosqlite

from services.analytics_queries import (
    get_athlete_sex,
    get_reference_max_hr,
    get_resting_hr_for_date,
)
from utils.metrics import (
    compute_training_load,
    efficiency_factor,
    equivalent_distance_km,
    trail_effort,
)

# Tipi HealthKit → categoria sport (lowercase, come inviati dall'app iOS)
_RUNNING_TYPES = {"running"}
_HIKING_TYPES  = {"hiking"}


async def compute_workout_metrics(db: aiosqlite.Connection) -> int:
    """
    Calcola e persiste le metriche derivate per tutti i workout HealthKit.

    Riprocessa anche i workout già presenti (idempotente via ON CONFLICT DO UPDATE).
    Ritorna il numero di workout processati.
    """
    sex        = await get_athlete_sex(db)
    max_hr_ref = await get_reference_max_hr(db)

    async with db.execute(
        """SELECT id, activity_type, start_date,
                  duration_seconds, total_distance_meters, total_energy_kcal
           FROM health_workouts
           ORDER BY start_date ASC"""
    ) as cur:
        workouts = await cur.fetchall()

    now   = datetime.now(UTC).isoformat()
    count = 0

    for w in workouts:
        workout_id:     str          = w["id"]
        activity_type:  str          = w["activity_type"]
        start_date:     str          = w["start_date"]
        duration_s:     float        = w["duration_seconds"]
        distance_m:     float | None = w["total_distance_meters"]
        energy_kcal:    float | None = w["total_energy_kcal"]

        duration_min  = duration_s / 60.0
        # HealthKit non fornisce average_heartrate per workout
        avg_hr        = None
        resting_hr    = await get_resting_hr_for_date(db, start_date)

        # Training Load (Bannister non disponibile senza avg_hr — usa stima energetica)
        load, load_method = compute_training_load(
            duration_min=duration_min,
            avg_hr=avg_hr,
            resting_hr=resting_hr,
            max_hr=max_hr_ref,
            sex=sex,
            energy_kcal=energy_kcal,
        )

        # Efficiency Factor: richiede avg_hr — non disponibile dai workout HealthKit
        ef: float | None = None

        # Hiking / Trail metrics: richiede elevation_gain — non disponibile da HealthKit
        eq_dist:  float | None = None
        t_effort: float | None = None

        await db.execute(
            """INSERT INTO analytics_workout (
                   workout_id, training_load, load_method,
                   efficiency_factor, equivalent_dist_km, trail_effort, computed_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(workout_id) DO UPDATE SET
                   training_load      = excluded.training_load,
                   load_method        = excluded.load_method,
                   efficiency_factor  = excluded.efficiency_factor,
                   equivalent_dist_km = excluded.equivalent_dist_km,
                   trail_effort       = excluded.trail_effort,
                   computed_at        = excluded.computed_at""",
            (workout_id, load, load_method, ef, eq_dist, t_effort, now),
        )
        count += 1

    await db.commit()
    return count
