from pydantic import BaseModel


class WorkoutListItem(BaseModel):
    """Workout HealthKit — campi essenziali per la lista."""
    workout_id: str                       # UUID stringa
    activity_type: str                    # tipo HealthKit lowercase ("running", "hiking", …)
    sport_label: str                      # label display ("Corsa", "Escursionismo", …)
    start_date: str                       # ISO 8601 UTC
    duration_seconds: int
    distance_km: float | None = None
    energy_kcal: float | None = None
    pace_sec_km: int | None = None        # secondi/km (solo se distanza disponibile)
    source_name: str


class PaginatedWorkouts(BaseModel):
    """Lista paginata di workout."""
    items: list[WorkoutListItem]
    total: int
    limit: int
    offset: int


class WorkoutDetail(WorkoutListItem):
    """Dettaglio workout con metriche analytics."""
    end_date: str
    training_load: float | None = None
    load_method: str | None = None        # 'bannister' | 'energy' | None
