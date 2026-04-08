"""
Endpoint statistiche workout HealthKit: /api/workouts/stats/*.

Sostituisce activities_stats.py (che leggeva dalla tabella Strava `activities`).
I tipi sport usati da HealthKit sono lowercase ("running", "hiking", "walking", …).
I parametri sport_types accettano sia la notazione HealthKit ("running") sia quella
legacy ("Run", "TrailRun", "Hike") per compatibilità con i client esistenti.
"""

from datetime import UTC, date, datetime, timedelta

import aiosqlite
from fastapi import APIRouter, Depends, Query

from db.database import get_db
from dependencies import require_auth
from models.activity import (
    ActivityRecord,
    HikeRecordsResponse,
    HRZoneItem,
    MonthlyComparisonResponse,
    MonthSummary,
    PaceTrendPoint,
    PersonalRecord,
    SportSummary,
    WeeklyStatsItem,
    WeeklyStreakResponse,
)

router = APIRouter(prefix="/api/workouts", tags=["workout-stats"], dependencies=[Depends(require_auth)])

_MESI_IT = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

# Distanze target per i record personali
_PR_DISTANCES: list[tuple[str, float, float, float]] = [
    ("5 km",           5.0,   4.5,  5.5),
    ("10 km",         10.0,   9.0, 11.0),
    ("Mezza maratona", 21.1, 19.0, 22.5),
    ("Maratona",       42.2, 40.0, 44.0),
]

# Mappa tipi legacy → HealthKit lowercase
_LEGACY_MAP: dict[str, str] = {
    "Run":      "running",
    "TrailRun": "running",   # HealthKit non distingue trail run
    "Hike":     "hiking",
    "Walk":     "walking",
    "Cycling":  "cycling",
}


def _normalize(sport_types: list[str]) -> list[str]:
    """Converte tipi sport legacy in tipi HealthKit lowercase (deduplica)."""
    result: list[str] = []
    for s in sport_types:
        mapped = _LEGACY_MAP.get(s, s.lower())
        if mapped not in result:
            result.append(mapped)
    return result


def _sport_label(activity_type: str) -> str:
    _MAP = {
        "running": "Corsa",
        "hiking":  "Escursionismo",
        "walking": "Camminata",
        "cycling": "Ciclismo",
        "swimming": "Nuoto",
    }
    return _MAP.get(activity_type, activity_type.replace("_", " ").title())


@router.get("/stats/weekly", response_model=list[WeeklyStatsItem])
async def stats_weekly(
    sport_types: list[str] = Query(default=[]),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[WeeklyStatsItem]:
    """Distanza, dislivello e tempo aggregati per settimana nelle ultime 12 settimane."""
    cutoff = (datetime.now(UTC) - timedelta(weeks=12)).isoformat()

    conditions = ["start_date >= ?"]
    params: list[object] = [cutoff]

    if sport_types:
        hk_types = _normalize(sport_types)
        placeholders = ",".join("?" * len(hk_types))
        conditions.append(f"activity_type IN ({placeholders})")
        params.extend(hk_types)

    where = " AND ".join(conditions)

    async with db.execute(
        f"""SELECT
               DATE(start_date,
                    '-' || CAST((CAST(strftime('%w', start_date) AS INTEGER) + 6) % 7 AS INTEGER) || ' days'
               ) AS week_start,
               SUM(total_distance_meters) AS total_distance,
               SUM(duration_seconds)      AS total_duration,
               COUNT(*)                   AS activity_count
           FROM health_workouts
           WHERE {where}
           GROUP BY week_start
           ORDER BY week_start ASC""",
        params,
    ) as cur:
        rows = await cur.fetchall()

    result = [
        WeeklyStatsItem(
            week_start=r["week_start"],
            distance_km=round((r["total_distance"] or 0.0) / 1000, 3),
            moving_time=int(r["total_duration"] or 0),
            activity_count=r["activity_count"],
            elevation_m=0.0,   # HealthKit workouts non hanno elevation_gain
        ) for r in rows]
    
    print(f"[STATS WEEKLY] Weekly about running: {result}", flush=True)
    return result


@router.get("/stats/monthly-comparison", response_model=MonthlyComparisonResponse)
async def stats_monthly_comparison(
    db: aiosqlite.Connection = Depends(get_db),
) -> MonthlyComparisonResponse:
    """Statistiche del mese corrente vs gli stessi giorni del mese precedente."""
    today = datetime.now(UTC).date()
    current_start = today.replace(day=1)

    prev_last = current_start - timedelta(days=1)
    prev_start = prev_last.replace(day=1)
    prev_end   = prev_start.replace(day=min(today.day, prev_last.day))

    current_label  = f"{_MESI_IT[today.month - 1]} {today.year}"
    previous_label = f"{_MESI_IT[prev_start.month - 1]} {prev_start.year}"

    query = """
        SELECT activity_type,
               COUNT(*)                    AS activity_count,
               SUM(total_distance_meters)  AS total_distance,
               SUM(duration_seconds)       AS total_duration
        FROM health_workouts
        WHERE {where}
        GROUP BY activity_type
        ORDER BY activity_count DESC
    """

    def _build_summary(rows: list[aiosqlite.Row]) -> MonthSummary:
        by_sport = [
            SportSummary(
                sport_type=_sport_label(r["activity_type"]),
                activity_count=r["activity_count"],
                total_distance_km=round((r["total_distance"] or 0.0) / 1000, 3),
                total_moving_time=int(r["total_duration"] or 0),
                total_elevation_m=0.0,
            )
            for r in rows
        ]
        return MonthSummary(
            activity_count=sum(s.activity_count for s in by_sport),
            total_distance_km=round(sum(s.total_distance_km for s in by_sport), 3),
            total_moving_time=sum(s.total_moving_time for s in by_sport),
            total_elevation_m=0.0,
            by_sport=by_sport,
        )

    async with db.execute(
        query.format(where="DATE(start_date) >= ? AND DATE(start_date) <= ?"),
        (current_start.isoformat(), today.isoformat()),
    ) as cur:
        current_rows = await cur.fetchall()
    async with db.execute(
        query.format(where="DATE(start_date) >= ? AND DATE(start_date) <= ?"),
        (prev_start.isoformat(), prev_end.isoformat()),
    ) as cur:
        previous_rows = await cur.fetchall()

    result = MonthlyComparisonResponse(
        current_month=_build_summary(current_rows),
        previous_month=_build_summary(previous_rows),
        current_label=current_label,
        previous_label=previous_label,
    )

    print(f"[STATS MONTHLY] Weekly about running: {result}", flush=True)
    return result


@router.get("/stats/pace-trend", response_model=list[PaceTrendPoint])
async def stats_pace_trend(
    db: aiosqlite.Connection = Depends(get_db),
) -> list[PaceTrendPoint]:
    """Ultime 30 corse con data e pace medio (per il grafico trend del passo)."""
    async with db.execute(
        """SELECT id, start_date, total_distance_meters, duration_seconds
           FROM health_workouts
           WHERE activity_type = 'running'
             AND total_distance_meters > 0
             AND duration_seconds > 0
           ORDER BY start_date DESC
           LIMIT 30""",
    ) as cur:
        rows = await cur.fetchall()

    return [
        PaceTrendPoint(
            workout_id=r["id"],
            start_date=r["start_date"],
            distance_km=round(r["total_distance_meters"] / 1000, 3),
            pace_sec_km=int(r["duration_seconds"] / (r["total_distance_meters"] / 1000)),
        )
        for r in rows
    ]


@router.get("/stats/hr-zones", response_model=list[HRZoneItem])
async def stats_hr_zones(
    db: aiosqlite.Connection = Depends(get_db),
) -> list[HRZoneItem]:
    """
    Distribuzione giornaliera per zona HR dagli ultimi 90 giorni.

    Usa health_daily_heart_rate (avg_bpm/max_bpm per giorno) invece di
    per-workout HR (non disponibile da HealthKit).
    Restituisce solo i giorni con workout registrati in quel giorno.
    """
    from services.analytics_queries import get_reference_max_hr

    max_hr = await get_reference_max_hr(db)
    if not max_hr:
        return []

    cutoff = (datetime.now(UTC).date() - timedelta(days=90)).isoformat()

    # Giorni con almeno un workout running
    async with db.execute(
        """SELECT DISTINCT DATE(start_date) AS day
           FROM health_workouts
           WHERE activity_type = 'running' AND DATE(start_date) >= ?""",
        (cutoff,),
    ) as cur:
        workout_days = {r["day"] for r in await cur.fetchall()}

    if not workout_days:
        return []

    async with db.execute(
        "SELECT date, avg_bpm FROM health_daily_heart_rate WHERE date >= ?",
        (cutoff,),
    ) as cur:
        hr_rows = await cur.fetchall()

    zone_counts: dict[str, int] = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 0, "Z5": 0}
    for row in hr_rows:
        if row["date"] not in workout_days:
            continue
        pct = row["avg_bpm"] / max_hr * 100
        if pct < 60:
            zone_counts["Z1"] += 1
        elif pct < 70:
            zone_counts["Z2"] += 1
        elif pct < 80:
            zone_counts["Z3"] += 1
        elif pct < 90:
            zone_counts["Z4"] += 1
        else:
            zone_counts["Z5"] += 1

    return [HRZoneItem(zone=z, count=c) for z, c in zone_counts.items() if c > 0]


@router.get("/stats/personal-records", response_model=list[PersonalRecord])
async def stats_personal_records(
    sport_types: list[str] = Query(default=[]),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[PersonalRecord]:
    """Migliori tempi per le distanze standard. Default: corsa (running)."""
    if not sport_types:
        hk_types = ["running"]
    else:
        hk_types = _normalize(sport_types)

    placeholders = ",".join("?" * len(hk_types))
    records: list[PersonalRecord] = []

    for label, target_km, min_km, max_km in _PR_DISTANCES:
        async with db.execute(
            f"""SELECT id, activity_type, start_date,
                       total_distance_meters, duration_seconds
                FROM health_workouts
                WHERE activity_type IN ({placeholders})
                  AND total_distance_meters >= ? AND total_distance_meters <= ?
                  AND duration_seconds > 0
                ORDER BY duration_seconds ASC
                LIMIT 2""",
            [*hk_types, min_km * 1000, max_km * 1000],
        ) as cur:
            rows = await cur.fetchall()

        if not rows:
            continue

        best = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        dist_km = best["total_distance_meters"] / 1000

        records.append(
            PersonalRecord(
                distance_label=label,
                distance_km=target_km,
                sport_type=_sport_label(best["activity_type"]),
                best_time_seconds=int(best["duration_seconds"]),
                best_pace_sec_km=int(best["duration_seconds"] / dist_km),
                activity_date=best["start_date"],
                activity_name=f"Corsa {round(dist_km, 1)} km",
                workout_id=best["id"],
                previous_best_seconds=int(prev["duration_seconds"]) if prev else None,
                previous_best_date=prev["start_date"] if prev else None,
            )
        )

    return records


@router.get("/stats/hike-records", response_model=HikeRecordsResponse)
async def stats_hike_records(
    sport_types: list[str] = Query(default=[]),
    db: aiosqlite.Connection = Depends(get_db),
) -> HikeRecordsResponse:
    """Record di distanza per escursioni. Default: hiking."""
    if not sport_types:
        hk_types = ["hiking"]
    else:
        hk_types = _normalize(sport_types)

    placeholders = ",".join("?" * len(hk_types))

    async with db.execute(
        f"""SELECT id, start_date, total_distance_meters
            FROM health_workouts
            WHERE activity_type IN ({placeholders}) AND total_distance_meters > 0
            ORDER BY total_distance_meters DESC LIMIT 1""",
        hk_types,
    ) as cur:
        dist_row = await cur.fetchone()

    async with db.execute(
        f"""SELECT COUNT(*) AS cnt, SUM(total_distance_meters) AS total_dist
            FROM health_workouts
            WHERE activity_type IN ({placeholders})""",
        hk_types,
    ) as cur:
        tot = await cur.fetchone()

    max_dist_km = round(dist_row["total_distance_meters"] / 1000, 3) if dist_row else 0.0

    return HikeRecordsResponse(
        max_distance=ActivityRecord(
            workout_id=dist_row["id"],
            activity_name=f"Escursione {round(dist_row['total_distance_meters'] / 1000, 1)} km",
            activity_date=dist_row["start_date"],
            value=max_dist_km,
        ) if dist_row else None,
        max_elevation=None,   # HealthKit workouts non hanno elevation_gain
        total_activities=tot["cnt"] or 0,
        total_distance_km=round((tot["total_dist"] or 0.0) / 1000, 1),
        total_elevation_m=0.0,
    )


@router.get("/stats/weekly-streak", response_model=WeeklyStreakResponse)
async def stats_weekly_streak(
    db: aiosqlite.Connection = Depends(get_db),
) -> WeeklyStreakResponse:
    """
    Streak di settimane consecutive con almeno un workout HealthKit.

    La settimana corrente (ancora in corso) conta anche se incompleta.
    La streak si azzera se manca un'intera settimana senza workout.
    """
    async with db.execute(
        """SELECT DISTINCT
               DATE(start_date,
                    '-' || CAST((CAST(strftime('%w', start_date) AS INTEGER) + 6) % 7 AS INTEGER) || ' days'
               ) AS week_start
           FROM health_workouts
           ORDER BY week_start DESC"""
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return WeeklyStreakResponse(streak_weeks=0, last_active_week=None)

    def to_date(s: str) -> date:
        return date.fromisoformat(s)

    def monday_of(d: date) -> date:
        return d - timedelta(days=d.weekday())

    active_weeks = [to_date(r["week_start"]) for r in rows]
    this_week    = monday_of(date.today())

    weeks_gap = (this_week - active_weeks[0]).days // 7
    if weeks_gap > 1:
        return WeeklyStreakResponse(streak_weeks=0, last_active_week=active_weeks[0].isoformat())

    streak = 1
    for i in range(1, len(active_weeks)):
        expected = active_weeks[i - 1] - timedelta(weeks=1)
        if active_weeks[i] == expected:
            streak += 1
        else:
            break

    result = WeeklyStreakResponse(
        streak_weeks=streak,
        last_active_week=active_weeks[0].isoformat(),
    )

    print(f"[STATS WEEKLY STREAK] Streak duration: {result}", flush=True)
    return result
