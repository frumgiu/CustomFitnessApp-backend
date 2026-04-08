"""
Query DB per il servizio analytics.

Funzioni di sola lettura che recuperano dati aggregati per giorno
da SQLite. Usate da analytics_workout.py e analytics_daily.py.
"""

from datetime import date, timedelta
from typing import Literal

import aiosqlite


async def get_athlete_sex(db: aiosqlite.Connection) -> Literal["M", "F"]:
    """Legge il sesso dell'atleta dal profilo locale. Default 'F'."""
    async with db.execute("SELECT sex FROM athlete_profile WHERE id = 1") as cur:
        row = await cur.fetchone()
    if row and row["sex"] in ("M", "F"):
        return row["sex"]
    return "F"


async def get_athlete_max_hr(db: aiosqlite.Connection) -> int | None:
    """Legge il max HR dal profilo atleta, se impostato dall'utente."""
    async with db.execute("SELECT max_hr FROM athlete_profile WHERE id = 1") as cur:
        row = await cur.fetchone()
    if row and row["max_hr"]:
        return int(row["max_hr"])
    return None


async def get_reference_max_hr(db: aiosqlite.Connection) -> float | None:
    """
    Stima il max HR individuale.

    Priorità:
    1. max_hr esplicitamente impostato nel profilo atleta.
    2. 95° percentile dei max_bpm giornalieri da health_daily_heart_rate.
    3. None se nessun dato disponibile.
    """
    profile_max_hr = await get_athlete_max_hr(db)
    if profile_max_hr:
        return float(profile_max_hr)

    async with db.execute(
        "SELECT max_bpm FROM health_daily_heart_rate ORDER BY max_bpm ASC"
    ) as cur:
        rows = await cur.fetchall()

    if len(rows) < 5:
        return None

    values = [r["max_bpm"] for r in rows]
    idx = min(int(len(values) * 0.95), len(values) - 1)
    return float(values[idx])


async def get_resting_hr_for_date(
    db: aiosqlite.Connection,
    activity_date: str,
) -> float | None:
    """
    FC a riposo del giorno del workout (o dei 3 giorni precedenti come fallback).
    """
    day = date.fromisoformat(activity_date[:10])
    for offset in range(4):
        target = (day - timedelta(days=offset)).isoformat()
        async with db.execute(
            "SELECT bpm FROM health_resting_heart_rate WHERE date = ?", (target,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            return float(row["bpm"])
    return None


async def fetch_daily_loads(db: aiosqlite.Connection) -> dict[str, float]:
    """
    Aggrega il training load per giorno dai workout HealthKit.

    Esclude workout senza training_load calcolato.
    """
    async with db.execute(
        """SELECT DATE(w.start_date) AS day, SUM(aw.training_load) AS total_load
           FROM health_workouts w
           JOIN analytics_workout aw ON w.id = aw.workout_id
           WHERE aw.training_load IS NOT NULL
           GROUP BY day
           ORDER BY day ASC"""
    ) as cur:
        rows = await cur.fetchall()
    return {r["day"]: float(r["total_load"]) for r in rows}


async def fetch_daily_hrv(db: aiosqlite.Connection) -> dict[str, float]:
    """Media giornaliera degli SDNN HRV da campioni HealthKit."""
    async with db.execute(
        """SELECT DATE(timestamp) AS day, AVG(sdnn_ms) AS avg_sdnn
           FROM health_hrv
           GROUP BY day
           ORDER BY day ASC"""
    ) as cur:
        rows = await cur.fetchall()
    return {r["day"]: float(r["avg_sdnn"]) for r in rows}


async def fetch_daily_rhr(db: aiosqlite.Connection) -> dict[str, float]:
    """FC a riposo giornaliera (un valore per giorno da HealthKit)."""
    async with db.execute(
        "SELECT date, bpm FROM health_resting_heart_rate ORDER BY date ASC"
    ) as cur:
        rows = await cur.fetchall()
    return {r["date"]: float(r["bpm"]) for r in rows}


async def fetch_daily_sleep(db: aiosqlite.Connection) -> dict[str, dict]:
    """Dati sonno giornalieri (durata totale, deep, REM) indicizzati per data."""
    async with db.execute(
        """SELECT date, total_sleep_minutes, deep_sleep_minutes, rem_sleep_minutes
           FROM health_sleep
           ORDER BY date ASC"""
    ) as cur:
        rows = await cur.fetchall()
    return {
        r["date"]: {
            "total": r["total_sleep_minutes"],
            "deep":  r["deep_sleep_minutes"],
            "rem":   r["rem_sleep_minutes"],
        }
        for r in rows
    }


async def fetch_activity_dates(db: aiosqlite.Connection) -> list[str]:
    """Date distinte in cui ci sono workout HealthKit (formato YYYY-MM-DD)."""
    async with db.execute(
        "SELECT DISTINCT DATE(start_date) AS day FROM health_workouts ORDER BY day ASC"
    ) as cur:
        return [r["day"] for r in await cur.fetchall()]


def date_range(start: date, end: date) -> list[str]:
    """Genera lista di date ISO da start a end (inclusi)."""
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days
