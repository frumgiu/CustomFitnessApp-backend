"""
Endpoint lista workout da HealthKit: /api/workouts/.
"""

from datetime import UTC, datetime, timedelta

import aiosqlite
from fastapi import APIRouter, Depends, Query

from db.database import get_db
from dependencies import require_auth
from models.workout import PaginatedWorkouts, WorkoutDetail, WorkoutListItem

router = APIRouter(prefix="/api/workouts", tags=["workouts"], dependencies=[Depends(require_auth)])

# Mappa tipi HealthKit → label display
_SPORT_DISPLAY: dict[str, str] = {
    "running":           "Corsa",
    "hiking":            "Escursionismo",
    "walking":           "Camminata",
    "cycling":           "Ciclismo",
    "swimming":          "Nuoto",
    "yoga":              "Yoga",
    "strength_training": "Forza",
    "hiit":              "HIIT",
    "cross_training":    "Cross Training",
    "elliptical":        "Ellittica",
    "rowing":            "Canottaggio",
    "dance":             "Danza",
    "pilates":           "Pilates",
    "mind_and_body":     "Mente e corpo",
    "recovery":          "Recupero attivo",
    "climbing":          "Arrampicata",
    "skating":           "Pattinaggio",
    "skiing":            "Sci",
}


def _sport_label(activity_type: str) -> str:
    return _SPORT_DISPLAY.get(activity_type, activity_type.replace("_", " ").title())


def _pace_sec_km(distance_m: float | None, duration_s: float) -> int | None:
    if distance_m and distance_m > 0 and duration_s > 0:
        return int(duration_s / (distance_m / 1000))
    return None


@router.get("/", response_model=PaginatedWorkouts)
async def list_workouts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sport_type: str | None = Query(None, description="Tipo sport HealthKit (es. 'running', 'hiking')"),
    db: aiosqlite.Connection = Depends(get_db),
) -> PaginatedWorkouts:
    """Lista paginata dei workout HealthKit, dal più recente."""
    conditions = ["1=1"]
    params: list[object] = []

    if sport_type:
        conditions.append("activity_type = ?")
        params.append(sport_type)

    where = " AND ".join(conditions)

    async with db.execute(
        f"SELECT COUNT(*) AS cnt FROM health_workouts WHERE {where}", params
    ) as cur:
        total_row = await cur.fetchone()
    total = total_row["cnt"] if total_row else 0

    async with db.execute(
        f"""SELECT id, activity_type, start_date, end_date,
                   duration_seconds, total_energy_kcal, total_distance_meters, source_name
            FROM health_workouts
            WHERE {where}
            ORDER BY start_date DESC
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ) as cur:
        rows = await cur.fetchall()

    items = [
        WorkoutListItem(
            workout_id=r["id"],
            activity_type=r["activity_type"],
            sport_label=_sport_label(r["activity_type"]),
            start_date=r["start_date"],
            duration_seconds=int(r["duration_seconds"]),
            distance_km=round(r["total_distance_meters"] / 1000, 3) if r["total_distance_meters"] else None,
            energy_kcal=round(r["total_energy_kcal"], 1) if r["total_energy_kcal"] else None,
            pace_sec_km=_pace_sec_km(r["total_distance_meters"], r["duration_seconds"]),
            source_name=r["source_name"],
        )
        for r in rows
    ]

    return PaginatedWorkouts(items=items, total=total, limit=limit, offset=offset)


@router.get("/{workout_id}", response_model=WorkoutDetail)
async def get_workout(
    workout_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> WorkoutDetail:
    from fastapi import HTTPException

    async with db.execute(
        """SELECT w.id, w.activity_type, w.start_date, w.end_date,
                  w.duration_seconds, w.total_energy_kcal, w.total_distance_meters, w.source_name,
                  aw.training_load, aw.load_method
           FROM health_workouts w
           LEFT JOIN analytics_workout aw ON w.id = aw.workout_id
           WHERE w.id = ?""",
        (workout_id,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Workout non trovato.")

    return WorkoutDetail(
        workout_id=row["id"],
        activity_type=row["activity_type"],
        sport_label=_sport_label(row["activity_type"]),
        start_date=row["start_date"],
        end_date=row["end_date"],
        duration_seconds=int(row["duration_seconds"]),
        distance_km=round(row["total_distance_meters"] / 1000, 3) if row["total_distance_meters"] else None,
        energy_kcal=round(row["total_energy_kcal"], 1) if row["total_energy_kcal"] else None,
        pace_sec_km=_pace_sec_km(row["total_distance_meters"], row["duration_seconds"]),
        source_name=row["source_name"],
        training_load=row["training_load"],
        load_method=row["load_method"],
    )
