"""
TRIMP (Training Impulse) — Bannister e Edwards.

LIMITI NOTI:
- Edwards TRIMP richiede stream HR granulare per minuto → non disponibile
  dalla cache SQLite (solo average_heartrate per attività).
- La stima zone_minutes usa l'average_heartrate come approssimazione.
"""

import math
from typing import Literal


def bannister_trimp(
    duration_min: float,
    avg_hr: float,
    resting_hr: float,
    max_hr: float,
    sex: Literal["M", "F"] = "M",
) -> float | None:
    """
    TRIMP di Bannister (1991).

    Formula:
        HRr = (avg_hr - resting_hr) / (max_hr - resting_hr)   ∈ [0, 1]
        TRIMP = duration_min × HRr × k × exp(c × HRr)

    Costanti per sesso (Bannister 1991):
        uomo:  k=0.64, c=1.92
        donna: k=0.86, c=1.67

    Ritorna None se max_hr <= resting_hr (dati inconsistenti).
    """
    if max_hr <= resting_hr:
        return None

    hrr = (avg_hr - resting_hr) / (max_hr - resting_hr)
    hrr = max(0.0, min(1.0, hrr))

    k, c = (0.86, 1.67) if sex == "F" else (0.64, 1.92)
    return round(duration_min * hrr * k * math.exp(c * hrr), 2)


def edwards_trimp(zone_minutes: dict[str, float]) -> float:
    """
    TRIMP di Edwards (1993) basato sul tempo in ciascuna zona HR.

    Pesi: Z1×1, Z2×2, Z3×3, Z4×4, Z5×5.
    Input: dict {"Z1": minuti, …, "Z5": minuti}. Chiavi mancanti = 0 min.

    NOTA: richiede minuti reali per zona (stream HR granulari).
    """
    weights = {"Z1": 1, "Z2": 2, "Z3": 3, "Z4": 4, "Z5": 5}
    return round(sum(zone_minutes.get(z, 0.0) * w for z, w in weights.items()), 2)


def estimate_zone_minutes(
    duration_min: float,
    avg_hr: float,
    max_hr: float,
) -> dict[str, float]:
    """
    Stima i minuti per zona assegnando l'intera durata alla zona dell'average_heartrate.

    APPROSSIMAZIONE: classifica l'attività in una zona unica.
    Soglie zone HR (% del max HR):
        Z1: < 60%  |  Z2: 60–70%  |  Z3: 70–80%  |  Z4: 80–90%  |  Z5: ≥ 90%
    """
    if max_hr <= 0:
        return {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0, "Z4": 0.0, "Z5": 0.0}

    pct = avg_hr / max_hr * 100
    zone = (
        "Z1" if pct < 60 else
        "Z2" if pct < 70 else
        "Z3" if pct < 80 else
        "Z4" if pct < 90 else
        "Z5"
    )
    result = {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0, "Z4": 0.0, "Z5": 0.0}
    result[zone] = duration_min
    return result


def compute_training_load(
    duration_min: float,
    avg_hr: float | None,
    resting_hr: float | None,
    max_hr: float | None,
    sex: Literal["M", "F"] = "M",
    zone_minutes: dict[str, float] | None = None,
    energy_kcal: float | None = None,
) -> tuple[float | None, str | None]:
    """
    Calcola il training load usando la formula migliore disponibile.

    Priorità:
    1. Edwards TRIMP se zone_minutes è fornito con almeno un valore > 0.
    2. Bannister TRIMP se avg_hr, resting_hr e max_hr sono tutti disponibili.
    3. Stima energetica (kcal × 0.1) se energy_kcal è disponibile — usata per
       workout HealthKit senza dati HR.
    4. (None, None) — dati insufficienti.

    Ritorna: (load, method)
    """
    if zone_minutes and any(v > 0 for v in zone_minutes.values()):
        return edwards_trimp(zone_minutes), "edwards"

    if avg_hr is not None and resting_hr is not None and max_hr is not None:
        load = bannister_trimp(duration_min, avg_hr, resting_hr, max_hr, sex)
        if load is not None:
            return load, "bannister"

    if energy_kcal is not None and energy_kcal > 0:
        # Stima: 100 kcal ≈ 10 TRIMP (allineato con Bannister per corsa moderata)
        return round(energy_kcal * 0.1, 2), "energy"

    return None, None
