from pydantic import BaseModel, Field


# --- DTO ricevuti dall'app iOS ---
# Nomi in snake_case: Pydantic v2 li riceve direttamente dall'iOS che usa CodingKeys espliciti.


class StepsDTO(BaseModel):
    date: str           # "yyyy-MM-dd"
    steps: int


class SleepDTO(BaseModel):
    date: str           # "yyyy-MM-dd" del giorno di risveglio
    sleep_start: str    # ISO 8601 UTC
    sleep_end: str      # ISO 8601 UTC
    total_sleep_minutes: int
    deep_sleep_minutes: int | None = None
    rem_sleep_minutes: int | None = None
    core_sleep_minutes: int | None = None


class HeartRateSampleDTO(BaseModel):
    timestamp: str      # ISO 8601 UTC
    bpm: float
    source: str


class DailyHeartRateDTO(BaseModel):
    date: str
    avg_bpm: float
    min_bpm: float
    max_bpm: float


class RestingHeartRateDTO(BaseModel):
    date: str
    bpm: float


class HRVDTO(BaseModel):
    timestamp: str      # ISO 8601 UTC
    sdnn_ms: float      # millisecondi


class ActiveEnergyDTO(BaseModel):
    date: str
    kcal: float


class WorkoutDTO(BaseModel):
    id: str             # UUID stringa
    activity_type: str
    start_date: str     # ISO 8601 UTC
    end_date: str       # ISO 8601 UTC
    duration_seconds: float
    total_energy_kcal: float | None = None
    total_distance_meters: float | None = None
    source_name: str


class MenstrualFlowDTO(BaseModel):
    date: str           # "yyyy-MM-dd"
    flow_level: str     # 'not_present' | 'unspecified' | 'light' | 'medium' | 'heavy'


# --- Payload principale ---

class HealthSyncPayload(BaseModel):
    synced_at: str
    steps: list[StepsDTO] = Field(default_factory=list)
    sleep: list[SleepDTO] = Field(default_factory=list)
    heart_rate_samples: list[HeartRateSampleDTO] = Field(default_factory=list)
    daily_heart_rate: list[DailyHeartRateDTO] = Field(default_factory=list)
    resting_heart_rate: list[RestingHeartRateDTO] = Field(default_factory=list)
    hrv: list[HRVDTO] = Field(default_factory=list)
    active_energy: list[ActiveEnergyDTO] = Field(default_factory=list)
    workouts: list[WorkoutDTO] = Field(default_factory=list)
    menstrual_flow: list[MenstrualFlowDTO] = Field(default_factory=list)


# --- Risposta ---

class HealthSyncResponse(BaseModel):
    received: bool
    message: str
    counts: dict[str, int]  # es. {"steps": 30, "workouts": 5}


# --- Riepilogo dati nel DB ---

class HealthSyncSummary(BaseModel):
    workout_count: int
    step_days: int
    sleep_days: int
    resting_hr_days: int
    hrv_days: int
    active_energy_days: int
    last_sync_at: str | None = None  # ISO 8601 UTC dell'ultima sync ricevuta


# --- Ciclo mestruale ---

class CyclePhaseResponse(BaseModel):
    phase: str              # 'menstrual' | 'follicular' | 'ovulatory' | 'luteal'
    phase_label: str        # etichetta italiana
    cycle_day: int          # giorno del ciclo corrente (1 = primo giorno mestruazioni)
    cycle_length_avg: int   # durata media del ciclo in giorni
    period_start: str       # "yyyy-MM-dd" inizio ultima mestruazione
    next_period_estimate: str  # "yyyy-MM-dd" stima prossimo ciclo
    days_until_next_period: int
