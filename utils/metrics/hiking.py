"""Metriche per attività hiking e trail running."""

import math


def equivalent_distance_km(distance_km: float, elevation_gain_m: float) -> float:
    """
    Distanza equivalente per attività in montagna.

    equivalent_km = distance_km + elevation_gain_m / 100

    Basata sulla regola di Naismith/Scarf (1998):
    ogni 100 m di dislivello positivo ≈ 1 km in piano.
    """
    return round(distance_km + elevation_gain_m / 100.0, 3)


def trail_effort(
    duration_min: float,
    distance_km: float,
    elevation_gain_m: float,
    avg_hr: float | None = None,
    max_hr: float | None = None,
) -> float:
    """
    Indice di effort per attività hiking/trail running (adimensionale).

    Formula base:
        effort = equivalent_distance_km × sqrt(duration_min / 60)

    Se avg_hr e max_hr sono disponibili, pesa per l'intensità:
        effort × (1 + (avg_hr / max_hr) × 0.5)

    L'indice è relativo: utile per confrontare attività simili tra loro.
    """
    eq_km = equivalent_distance_km(distance_km, elevation_gain_m)
    duration_factor = math.sqrt(max(duration_min, 0.0) / 60.0)
    effort = eq_km * duration_factor

    if avg_hr is not None and max_hr is not None and max_hr > 0:
        hrr = min(avg_hr / max_hr, 1.0)
        effort *= 1.0 + hrr * 0.5

    return round(effort, 3)
