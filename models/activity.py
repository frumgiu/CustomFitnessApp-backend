from pydantic import BaseModel


class SportSummary(BaseModel):
    """Totali aggregati per un singolo sport in un periodo."""
    sport_type: str
    activity_count: int
    total_distance_km: float
    total_moving_time: int  # secondi
    total_elevation_m: float = 0


class StatsSummaryResponse(BaseModel):
    """Confronto ultimi 30 giorni vs 30 giorni precedenti, per sport."""
    current: list[SportSummary]   # ultimi 30 giorni
    previous: list[SportSummary]  # 30 giorni precedenti


class WeeklyStatsItem(BaseModel):
    """Aggregato distanza/tempo/dislivello per una singola settimana."""
    week_start: str   # data ISO del lunedì della settimana
    distance_km: float
    moving_time: int  # secondi
    activity_count: int
    elevation_m: float = 0


class WeeklyStreakResponse(BaseModel):
    """Streak di settimane consecutive con almeno un'allenamento."""
    streak_weeks: int
    last_active_week: str | None  # data ISO del lunedì dell'ultima settimana attiva


class PaceTrendPoint(BaseModel):
    """Dato di pace per una singola run (per il grafico trend)."""
    workout_id: str
    start_date: str
    distance_km: float
    pace_sec_km: int  # secondi/km


class HRZoneItem(BaseModel):
    """Conteggio attività per zona di frequenza cardiaca."""
    zone: str    # "Z1" … "Z5"
    count: int


class PersonalRecord(BaseModel):
    """Miglior tempo registrato per una distanza-target (5k, 10k, ecc.)."""
    distance_label: str              # "5 km", "10 km", ecc.
    distance_km: float               # distanza target nominale
    sport_type: str
    best_time_seconds: int           # durata dell'attività migliore
    best_pace_sec_km: int            # pace medio calcolato
    activity_date: str               # start_date dell'attività
    activity_name: str
    workout_id: str | None = None    # UUID del workout HealthKit
    previous_best_seconds: int | None = None   # secondo miglior tempo (per confronto)
    previous_best_date: str | None = None


class MonthSummary(BaseModel):
    """Totali aggregati per un mese (tutti gli sport + dettaglio per sport)."""
    activity_count: int
    total_distance_km: float
    total_moving_time: int           # secondi
    total_elevation_m: float
    by_sport: list[SportSummary]


class MonthlyComparisonResponse(BaseModel):
    """Confronto statistiche mese corrente vs mese precedente (stessi giorni)."""
    current_month: MonthSummary
    previous_month: MonthSummary
    current_label: str               # es. "Aprile 2026"
    previous_label: str              # es. "Marzo 2026"


class ActivityRecord(BaseModel):
    """Record (massimo) per una singola metrica in un'attività."""
    workout_id: str | None = None    # UUID del workout HealthKit
    activity_name: str
    activity_date: str
    value: float                     # km per distanza, m per dislivello


class HikeRecordsResponse(BaseModel):
    """Record di distanza e dislivello per attività Hike/TrailRun."""
    max_distance: ActivityRecord | None = None
    max_elevation: ActivityRecord | None = None
    total_activities: int = 0
    total_distance_km: float = 0
    total_elevation_m: float = 0
