from datetime import UTC, datetime

import aiosqlite
from fastapi import APIRouter, Depends

from db.database import get_db
from models.athlete import AthleteProfile, AthleteProfileUpdate

router = APIRouter(prefix="/api/athlete", tags=["athlete"])


@router.get("/", response_model=AthleteProfile)
async def get_athlete_profile(
    db: aiosqlite.Connection = Depends(get_db),
) -> AthleteProfile:
    """Restituisce il profilo atleta locale (impostabile da Settings)."""
    async with db.execute(
        "SELECT name, sex, birthday, weight_kg, height_cm, max_hr, updated_at FROM athlete_profile WHERE id = 1"
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        return AthleteProfile()

    return AthleteProfile(
        name=row["name"],
        sex=row["sex"],
        birthday=row["birthday"],
        weight_kg=row["weight_kg"],
        height_cm=row["height_cm"],
        max_hr=row["max_hr"],
        updated_at=row["updated_at"],
    )


@router.put("/", response_model=AthleteProfile)
async def update_athlete_profile(
    update: AthleteProfileUpdate,
    db: aiosqlite.Connection = Depends(get_db),
) -> AthleteProfile:
    """Aggiorna il profilo atleta locale. Crea il record se non esiste."""
    now = datetime.now(UTC).isoformat()

    # Leggi il profilo corrente (per mantenere i campi non aggiornati)
    async with db.execute(
        "SELECT name, sex, birthday, weight_kg, height_cm, max_hr FROM athlete_profile WHERE id = 1"
    ) as cur:
        existing = await cur.fetchone()

    if existing:
        # Merge: mantieni i valori esistenti se il campo aggiornato è None
        name      = update.name      if update.name      is not None else existing["name"]
        sex       = update.sex       if update.sex       is not None else existing["sex"]
        birthday  = update.birthday  if update.birthday  is not None else existing["birthday"]
        weight_kg = update.weight_kg if update.weight_kg is not None else existing["weight_kg"]
        height_cm = update.height_cm if update.height_cm is not None else existing["height_cm"]
        max_hr    = update.max_hr    if update.max_hr    is not None else existing["max_hr"]
    else:
        name      = update.name
        sex       = update.sex or "F"
        birthday  = update.birthday
        weight_kg = update.weight_kg
        height_cm = update.height_cm
        max_hr    = update.max_hr

    await db.execute(
        """INSERT INTO athlete_profile (id, name, sex, birthday, weight_kg, height_cm, max_hr, updated_at)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               name       = excluded.name,
               sex        = excluded.sex,
               birthday   = excluded.birthday,
               weight_kg  = excluded.weight_kg,
               height_cm  = excluded.height_cm,
               max_hr     = excluded.max_hr,
               updated_at = excluded.updated_at""",
        (name, sex, birthday, weight_kg, height_cm, max_hr, now),
    )
    await db.commit()

    return AthleteProfile(
        name=name,
        sex=sex,
        birthday=birthday,
        weight_kg=weight_kg,
        height_cm=height_cm,
        max_hr=max_hr,
        updated_at=now,
    )
