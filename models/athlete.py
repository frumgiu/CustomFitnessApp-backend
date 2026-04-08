from pydantic import BaseModel


class AthleteProfile(BaseModel):
    """Profilo atleta locale — modificabile dall'utente nelle impostazioni."""
    name: str | None = None
    sex: str = "F"                   # "M" | "F"
    birthday: str | None = None      # "yyyy-MM-dd"
    weight_kg: float | None = None
    height_cm: float | None = None
    max_hr: int | None = None
    updated_at: str | None = None


class AthleteProfileUpdate(BaseModel):
    """Campi aggiornabili del profilo atleta (tutti opzionali)."""
    name: str | None = None
    sex: str | None = None
    birthday: str | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    max_hr: int | None = None
