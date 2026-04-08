"""
Calcolo metriche giornaliere aggregate → tabella analytics_daily.

CTL/ATL vengono ricalcolati dall'inizio dello storico ad ogni esecuzione.
"""

from datetime import UTC, date, datetime

import aiosqlite

from services.analytics_queries import (
    date_range,
    fetch_activity_dates,
    fetch_daily_hrv,
    fetch_daily_loads,
    fetch_daily_rhr,
    fetch_daily_sleep,
)
from utils.metrics import (
    compute_acwr,
    compute_tsb,
    recovery_score,
    rolling_baseline,
    sleep_score,
    update_atl,
    update_ctl,
)

# Finestre temporali per le baselines rolling
_HRV_WINDOW   = 7    # giorni — variabilità giornaliera alta
_RHR_WINDOW   = 14   # giorni — più stabile dell'HRV
_SLEEP_WINDOW = 28   # giorni — incorpora pattern settimanali


async def compute_daily_metrics(db: aiosqlite.Connection) -> int:
    """
    Calcola e persiste le metriche aggregate per ogni giorno di calendario.

    Convenzione CTL/ATL:
    - Ogni passo = 1 giorno. Giorni senza attività: daily_load=0.
    - CTL₀ = ATL₀ = 0, ricalcolo completo dalla prima data disponibile.

    Ritorna il numero di giorni processati.
    """
    daily_loads = await fetch_daily_loads(db)
    daily_hrv   = await fetch_daily_hrv(db)
    daily_rhr   = await fetch_daily_rhr(db)
    daily_sleep = await fetch_daily_sleep(db)
    activity_dates = await fetch_activity_dates(db)

    if not activity_dates and not daily_hrv and not daily_rhr and not daily_sleep:
        return 0

    all_dates = (
        activity_dates
        + list(daily_loads.keys())
        + list(daily_hrv.keys())
        + list(daily_rhr.keys())
        + list(daily_sleep.keys())
    )
    start_day = date.fromisoformat(min(all_dates))
    days = date_range(start_day, date.today())

    # Serie temporali ordinate per baseline rolling
    hrv_series:   list[tuple[str, float]] = sorted(daily_hrv.items())
    rhr_series:   list[tuple[str, float]] = sorted(daily_rhr.items())
    sleep_series: list[tuple[str, float]] = sorted(
        {d: v["total"] for d, v in daily_sleep.items() if v["total"] is not None}.items()
    )
    all_load_pairs: list[tuple[str, float]] = sorted(daily_loads.items())

    ctl   = 0.0
    atl   = 0.0
    now   = datetime.now(UTC).isoformat()
    count = 0

    for day_str in days:
        load = daily_loads.get(day_str, 0.0)

        ctl  = update_ctl(ctl, load)
        atl  = update_atl(atl, load)
        tsb  = compute_tsb(ctl, atl)
        acwr = compute_acwr(all_load_pairs, day_str)

        # Baseline HRV (7 giorni)
        hrv_baseline_val = hrv_delta_val = hrv_z_val = None
        hrv_up_to = [v for d, v in hrv_series if d <= day_str]
        if hrv_up_to:
            result = rolling_baseline(hrv_up_to, _HRV_WINDOW)
            if result:
                hrv_baseline_val, hrv_delta_val, hrv_z_val = result

        # Baseline RHR (14 giorni)
        rhr_baseline_val = rhr_delta_val = None
        rhr_up_to = [v for d, v in rhr_series if d <= day_str]
        if rhr_up_to:
            result = rolling_baseline(rhr_up_to, _RHR_WINDOW)
            if result:
                rhr_baseline_val, rhr_delta_val, _ = result

        # Baseline sonno (28 giorni)
        sleep_baseline_val = sleep_delta_val = None
        sleep_up_to = [v for d, v in sleep_series if d <= day_str]
        if sleep_up_to:
            result = rolling_baseline(sleep_up_to, _SLEEP_WINDOW)
            if result:
                sleep_baseline_val, sleep_delta_val, _ = result

        # Sleep Score
        s_score  = None
        sleep_data = daily_sleep.get(day_str)
        if sleep_data:
            s_score = sleep_score(
                total_minutes=sleep_data["total"],
                deep_sleep_minutes=sleep_data["deep"],
                rem_sleep_minutes=sleep_data["rem"],
            )

        # Recovery Score
        r_score = recovery_score(
            hrv_delta=hrv_delta_val,
            rhr_delta=rhr_delta_val,
            sleep_minutes=sleep_data["total"] if sleep_data else None,
            tsb=tsb,
        )

        await db.execute(
            """INSERT INTO analytics_daily (
                   date, daily_load, ctl, atl, tsb, acwr,
                   recovery_score, sleep_score,
                   hrv_baseline, hrv_delta, hrv_zscore,
                   rhr_baseline, rhr_delta,
                   sleep_baseline, sleep_delta,
                   computed_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   daily_load     = excluded.daily_load,
                   ctl            = excluded.ctl,
                   atl            = excluded.atl,
                   tsb            = excluded.tsb,
                   acwr           = excluded.acwr,
                   recovery_score = excluded.recovery_score,
                   sleep_score    = excluded.sleep_score,
                   hrv_baseline   = excluded.hrv_baseline,
                   hrv_delta      = excluded.hrv_delta,
                   hrv_zscore     = excluded.hrv_zscore,
                   rhr_baseline   = excluded.rhr_baseline,
                   rhr_delta      = excluded.rhr_delta,
                   sleep_baseline = excluded.sleep_baseline,
                   sleep_delta    = excluded.sleep_delta,
                   computed_at    = excluded.computed_at""",
            (
                day_str, load, ctl, atl, tsb, acwr,
                r_score, s_score,
                hrv_baseline_val, hrv_delta_val, hrv_z_val,
                rhr_baseline_val, rhr_delta_val,
                sleep_baseline_val, sleep_delta_val,
                now,
            ),
        )
        count += 1

    await db.commit()
    return count
