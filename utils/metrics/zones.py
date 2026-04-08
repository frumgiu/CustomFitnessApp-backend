"""Zone HR: classificazione e statistiche per attività."""

from .training_load import estimate_zone_minutes


def hr_zone_stats(
    duration_min: float,
    avg_hr: float,
    max_hr: float,
) -> dict[str, float]:
    """
    Distribuisce la durata per zona HR e calcola le percentuali.

    Ritorna dict con:
        z1_min … z5_min: minuti stimati in ogni zona
        z1_pct … z5_pct: percentuale sul totale (0–100)

    NOTA: assegna l'intera durata alla zona dell'average_heartrate.
    Soglie (% del max HR): Z1<60, Z2 60-70, Z3 70-80, Z4 80-90, Z5≥90.
    """
    zone_mins = estimate_zone_minutes(duration_min, avg_hr, max_hr)
    result: dict[str, float] = {}
    for i, z in enumerate(["Z1", "Z2", "Z3", "Z4", "Z5"], 1):
        mins = zone_mins[z]
        pct = (mins / duration_min * 100) if duration_min > 0 else 0.0
        result[f"z{i}_min"] = round(mins, 2)
        result[f"z{i}_pct"] = round(pct, 1)
    return result
