from typing import Literal

from pydantic import BaseModel


class RacePrediction(BaseModel):
    """Previsione tempo gara per una distanza specifica."""

    distance_km: float
    predicted_seconds: int
    predicted_time: str          # formato "H:MM:SS" o "MM:SS"
    confidence: Literal["low", "medium", "high"]
    based_on: int                # numero di attività usate per il calcolo
