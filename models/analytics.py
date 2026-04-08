from pydantic import BaseModel


class ActivityMetrics(BaseModel):
    """Metriche derivate per un singolo workout HealthKit."""
    workout_id: str
    training_load: float | None = None
    load_method: str | None = None        # 'bannister' | 'edwards' | None
    # Zone HR in minuti (stima da average_heartrate — non da stream granulare)
    hr_z1_min: float | None = None
    hr_z2_min: float | None = None
    hr_z3_min: float | None = None
    hr_z4_min: float | None = None
    hr_z5_min: float | None = None
    # Zone HR in percentuale
    hr_z1_pct: float | None = None
    hr_z2_pct: float | None = None
    hr_z3_pct: float | None = None
    hr_z4_pct: float | None = None
    hr_z5_pct: float | None = None
    efficiency_factor: float | None = None   # solo per Run/TrailRun
    # Sempre None finché gli stream HR non sono cachati nel DB
    aerobic_decoupling: float | None = None
    equivalent_dist_km: float | None = None  # solo per Hike/TrailRun
    trail_effort: float | None = None        # solo per Hike/TrailRun
    computed_at: str | None = None


class DailyMetrics(BaseModel):
    """Metriche aggregate giornaliere: fitness, recupero, sonno, baselines."""
    date: str
    daily_load: float = 0.0
    ctl: float | None = None           # Chronic Training Load (tau=42gg)
    atl: float | None = None           # Acute Training Load (tau=7gg)
    tsb: float | None = None           # Training Stress Balance = CTL - ATL
    acwr: float | None = None          # Acute:Chronic Workload Ratio
    recovery_score: float | None = None    # 0–100
    sleep_score: float | None = None       # 0–100
    hrv_baseline: float | None = None
    hrv_delta: float | None = None
    hrv_zscore: float | None = None
    rhr_baseline: float | None = None
    rhr_delta: float | None = None
    sleep_baseline: float | None = None
    sleep_delta: float | None = None
    computed_at: str | None = None


class FitnessPoint(BaseModel):
    """Punto singolo della curva PMC (Performance Management Chart)."""
    date: str
    ctl: float
    atl: float
    tsb: float
    daily_load: float


class RacePredictionItem(BaseModel):
    """Singola previsione Riegel per una distanza gara."""
    distance_label: str     # "5 km", "10 km", "Mezza maratona", "Maratona"
    distance_km: float
    predicted_seconds: int
    predicted_time: str     # "H:MM:SS" o "M:SS"


class RacePredictionsResponse(BaseModel):
    """Previsioni Riegel per tutte le distanze standard, da una sorgente scelta."""
    source_distance_km: float
    source_time_seconds: int
    source_activity_name: str
    source_date: str
    sport_type: str
    predictions: list[RacePredictionItem]


class ComputeResult(BaseModel):
    """Risultato di una computazione analytics."""
    activities_processed: int
    days_processed: int
    message: str
