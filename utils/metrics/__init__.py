"""
Package utils.metrics — funzioni pure per il calcolo di metriche di fitness e recupero.

Tutte le funzioni sono stateless e deterministiche: nessun accesso a DB o I/O.
I valori mancanti (None) sono gestiti esplicitamente.

LIMITI NOTI:
- Edwards TRIMP: richiede stream HR granulare → non disponibile dalla cache SQLite.
- Aerobic Decoupling: richiede stream HR + velocità sincronizzati → non in pipeline.
- Zone HR per minuto: stima usa average_heartrate per l'intera durata.
"""

from .training_load import (
    bannister_trimp,
    edwards_trimp,
    estimate_zone_minutes,
    compute_training_load,
)
from .zones import hr_zone_stats
from .pmc import update_ctl, update_atl, compute_tsb, compute_acwr
from .running import (
    efficiency_factor,
    aerobic_decoupling,
    riegel_predict,
    format_seconds,
    RACE_DISTANCES,
)
from .hiking import equivalent_distance_km, trail_effort
from .recovery import recovery_score, sleep_score, rolling_baseline

__all__ = [
    # training load
    "bannister_trimp",
    "edwards_trimp",
    "estimate_zone_minutes",
    "compute_training_load",
    # zone HR
    "hr_zone_stats",
    # PMC
    "update_ctl",
    "update_atl",
    "compute_tsb",
    "compute_acwr",
    # running
    "efficiency_factor",
    "aerobic_decoupling",
    "riegel_predict",
    "format_seconds",
    "RACE_DISTANCES",
    # hiking
    "equivalent_distance_km",
    "trail_effort",
    # recovery
    "recovery_score",
    "sleep_score",
    "rolling_baseline",
]
