"""Recovery Score, Sleep Score e baseline rolling."""

import math


def recovery_score(
    hrv_delta: float | None = None,
    rhr_delta: float | None = None,
    sleep_minutes: float | None = None,
    tsb: float | None = None,
    sleep_target_minutes: float = 480.0,
) -> float:
    """
    Score di recupero composto 0–100.

    Parte da baseline 50. Componenti e contributi massimi:
        HRV delta   (+35 / -35): ogni ms ±2 punti.
        RHR delta   (+25 / -25): segno invertito, ogni bpm ±5 punti.
        Sonno       (+12.5 / -25): centrato sul 75% del target (8h default).
        TSB         (+15 / -15): ogni unità ±1 punto.

    Se tutti i dati mancano ritorna 50 (neutrale).
    Risultato clamped a [0, 100].
    """
    score = 50.0

    if hrv_delta is not None:
        score += max(-35.0, min(35.0, hrv_delta * 2.0))

    if rhr_delta is not None:
        score += max(-25.0, min(25.0, -rhr_delta * 5.0))

    if sleep_minutes is not None and sleep_target_minutes > 0:
        sleep_ratio = min(1.0, sleep_minutes / sleep_target_minutes)
        sleep_contribution = (sleep_ratio - 0.75) * 50.0
        score += max(-25.0, min(12.5, sleep_contribution))

    if tsb is not None:
        score += max(-15.0, min(15.0, tsb * 1.0))

    return round(max(0.0, min(100.0, score)), 1)


def sleep_score(
    total_minutes: float | None = None,
    duration_target_minutes: float = 480.0,
    deep_sleep_minutes: float | None = None,
    rem_sleep_minutes: float | None = None,
) -> float | None:
    """
    Score del sonno 0–100 dai dati HealthKit.

    Componenti (pesi adattivi):
        Durata     (50%): % del target raggiunto.
        Deep sleep (25%): target ideale ~20% del totale.
        REM sleep  (25%): target ideale ~22% del totale.

    Se un componente manca il peso viene redistribuito sugli altri.
    Ritorna None se total_minutes è None.
    """
    if total_minutes is None:
        return None

    duration_score = min(100.0, (total_minutes / duration_target_minutes) * 100.0)
    components: list[float] = [duration_score]
    weights: list[float] = [50.0]

    if deep_sleep_minutes is not None and total_minutes > 0:
        deep_score = min(1.0, (deep_sleep_minutes / total_minutes) / 0.20) * 100.0
        components.append(deep_score)
        weights.append(25.0)

    if rem_sleep_minutes is not None and total_minutes > 0:
        rem_score = min(1.0, (rem_sleep_minutes / total_minutes) / 0.22) * 100.0
        components.append(rem_score)
        weights.append(25.0)

    total_w = sum(weights)
    score = sum(s * w for s, w in zip(components, weights)) / total_w
    return round(score, 1)


def rolling_baseline(
    values: list[float],
    window: int,
) -> tuple[float, float, float] | None:
    """
    Baseline rolling su una finestra temporale.

    Input: lista di valori dal più vecchio al più recente.
    La baseline è calcolata sugli ultimi `window` valori precedenti al corrente.

    Ritorna (baseline_mean, delta, z_score) oppure None se < 3 valori.

    Finestre consigliate:
        HRV:  7 giorni (alta variabilità).
        RHR: 14 giorni (più stabile).
        Sonno: 28 giorni (pattern settimanale).
    """
    if len(values) < 3:
        return None

    baseline_values = values[-(window + 1):-1]
    if len(baseline_values) < 2:
        return None

    current = values[-1]
    mean = sum(baseline_values) / len(baseline_values)
    variance = sum((v - mean) ** 2 for v in baseline_values) / len(baseline_values)
    std = math.sqrt(variance)

    delta = current - mean
    z_score = delta / std if std > 0 else 0.0

    return round(mean, 3), round(delta, 3), round(z_score, 3)
