"""
Performance Management Chart: CTL, ATL, TSB e ACWR.

Riferimenti:
    Banister (1975) — modello impulso-risposta.
    Coggan — adattamento pratico CTL/ATL/TSB.
    Hulin et al. (2016) — ACWR e rischio infortuni.
"""

from datetime import date, timedelta


def update_ctl(prev_ctl: float, daily_load: float, tau: int = 42) -> float:
    """
    Aggiorna il Chronic Training Load (fitness).

    CTL_t = CTL_(t-1) + (Load_t − CTL_(t-1)) / tau

    tau=42 giorni: costante classica del PMC. Chiamare con daily_load=0
    per i giorni senza attività (CTL decade naturalmente).
    """
    return round(prev_ctl + (daily_load - prev_ctl) / tau, 3)


def update_atl(prev_atl: float, daily_load: float, tau: int = 7) -> float:
    """
    Aggiorna l'Acute Training Load (fatica).

    ATL_t = ATL_(t-1) + (Load_t − ATL_(t-1)) / tau

    tau=7 giorni: la fatica si accumula e smaltisce più rapidamente del fitness.
    """
    return round(prev_atl + (daily_load - prev_atl) / tau, 3)


def compute_tsb(ctl: float, atl: float) -> float:
    """
    Training Stress Balance (forma / freshness).

    TSB = CTL − ATL

    Positivo → atleta più riposato che allenato.
    Negativo → fatica superiore al fitness corrente.
    """
    return round(ctl - atl, 3)


def compute_acwr(
    daily_loads: list[tuple[str, float]],
    reference_date: str,
) -> float | None:
    """
    ACWR per la data di riferimento.

    Acute load   = somma dei carichi negli ultimi 7 giorni (incluso reference_date).
    Chronic load = sum(28 giorni) / 4  (media settimanale delle ultime 4 settimane).
    ACWR         = acute / chronic.

    Zona sicura: 0.8–1.3. Sopra 1.5 → rischio infortuni elevato.

    Ritorna None se chronic_load == 0 o dati < 7 giorni.
    Input: lista di (date_str YYYY-MM-DD, load) in qualsiasi ordine.
    """
    ref = date.fromisoformat(reference_date)
    load_by_date: dict[str, float] = dict(daily_loads)

    acute_days = [(ref - timedelta(days=i)).isoformat() for i in range(7)]
    acute_load = sum(load_by_date.get(d, 0.0) for d in acute_days)

    chronic_days = [(ref - timedelta(days=i)).isoformat() for i in range(28)]
    chronic_load = sum(load_by_date.get(d, 0.0) for d in chronic_days) / 4.0

    if chronic_load == 0.0:
        return None

    return round(acute_load / chronic_load, 3)
