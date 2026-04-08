"""Metriche specifiche per la corsa: efficiency factor, decoupling, previsioni gara."""

import math

# Distanze standard per le previsioni gara (label, km)
RACE_DISTANCES: list[tuple[str, float]] = [
    ("5 km", 5.0),
    ("10 km", 10.0),
    ("Mezza maratona", 21.0975),
    ("Maratona", 42.195),
]

_RIEGEL_EXP = 1.06


def efficiency_factor(
    distance_m: float,
    duration_s: float,
    avg_hr: float,
) -> float | None:
    """
    Fattore di efficienza aerobica (EF).

    EF = speed_mps / avg_hr

    Valori tipici per runner allenati: 0.012–0.020 m/s/bpm.
    Un EF crescente nel tempo indica miglioramento aerobico.

    Ritorna None se avg_hr <= 0 o duration_s <= 0.
    """
    if avg_hr <= 0 or duration_s <= 0:
        return None
    speed_mps = distance_m / duration_s
    return round(speed_mps / avg_hr, 6)


def aerobic_decoupling(ef1: float, ef2: float) -> float | None:
    """
    Decoupling aerobico tra prima e seconda metà di un'attività.

    Decoupling (%) = 100 × (EF1 − EF2) / EF1

    Soglie: < 5% buono, 5–10% lieve deriva, > 10% fatica evidente.

    PREREQUISITO: richiede stream HR + velocità sincronizzati, non disponibili
    nella pipeline attuale. Ritorna sempre None dal servizio di calcolo.

    Ritorna None se ef1 <= 0.
    """
    if ef1 <= 0:
        return None
    return round(100.0 * (ef1 - ef2) / ef1, 2)


def riegel_predict(t1_seconds: float, d1_km: float, d2_km: float) -> float:
    """
    Formula di Riegel (1977) per la previsione dei tempi gara.

    T2 = T1 × (D2 / D1) ^ 1.06

    Accurata per estrapolazioni entro ×3 della distanza sorgente.
    Ritorna 0.0 se d1_km o t1_seconds non sono positivi.
    """
    if d1_km <= 0 or t1_seconds <= 0:
        return 0.0
    return round(t1_seconds * (d2_km / d1_km) ** _RIEGEL_EXP, 1)


def format_seconds(seconds: float) -> str:
    """Formatta un numero di secondi in H:MM:SS o M:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"
