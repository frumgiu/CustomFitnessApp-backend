"""
Test unitari per utils/metrics.py

Coprono le formule principali: TRIMP (Bannister ed Edwards), CTL/ATL/TSB,
ACWR, efficiency factor, trail effort, Riegel, recovery score, sleep score,
baselines rolling.

Esegui con:
    cd backend && pytest tests/test_metrics.py -v
"""

import pytest

from utils.metrics import (
    aerobic_decoupling,
    bannister_trimp,
    compute_acwr,
    compute_training_load,
    compute_tsb,
    edwards_trimp,
    efficiency_factor,
    equivalent_distance_km,
    estimate_zone_minutes,
    format_seconds,
    hr_zone_stats,
    recovery_score,
    riegel_predict,
    rolling_baseline,
    sleep_score,
    trail_effort,
    update_atl,
    update_ctl,
)


# ---------------------------------------------------------------------------
# Bannister TRIMP
# ---------------------------------------------------------------------------

class TestBannisterTrimp:
    def test_maschio_valori_tipici(self) -> None:
        # Durata 60 min, HR media 150, resting 55, max 190, maschio
        # HRr = (150-55)/(190-55) = 95/135 ≈ 0.7037
        # TRIMP = 60 * 0.7037 * 0.64 * exp(1.92 * 0.7037) ≈ ~
        result = bannister_trimp(60.0, 150.0, 55.0, 190.0, "M")
        assert result is not None
        assert result > 0
        # Valore atteso approssimato (range ragionevole per una run Z3-Z4 di 60 min)
        assert 40 < result < 120

    def test_femmina_valori_tipici(self) -> None:
        result_m = bannister_trimp(60.0, 150.0, 55.0, 190.0, "M")
        result_f = bannister_trimp(60.0, 150.0, 55.0, 190.0, "F")
        assert result_m is not None
        assert result_f is not None
        # Donna ha k più alto ma c più basso — a HR moderata il TRIMP donna è più alto
        # (non testate la direzione, solo che siano diversi)
        assert result_m != result_f

    def test_max_hr_uguale_resting_hr(self) -> None:
        # Dati inconsistenti → None
        assert bannister_trimp(60.0, 150.0, 180.0, 180.0) is None

    def test_max_hr_minore_resting_hr(self) -> None:
        assert bannister_trimp(60.0, 150.0, 200.0, 180.0) is None

    def test_hrr_clamp_avg_hr_oltre_max(self) -> None:
        # avg_hr > max_hr → HRr > 1, viene clampato a 1
        result = bannister_trimp(60.0, 200.0, 55.0, 190.0, "M")
        # Deve tornare un valore, non None
        assert result is not None
        assert result > 0

    def test_hrr_clamp_avg_hr_sotto_resting(self) -> None:
        # avg_hr < resting_hr → HRr < 0, viene clampato a 0
        result = bannister_trimp(60.0, 40.0, 55.0, 190.0, "M")
        assert result is not None
        # HRr=0 → TRIMP = duration * 0 * k * exp(0) = 0
        assert result == 0.0

    def test_durata_zero(self) -> None:
        result = bannister_trimp(0.0, 150.0, 55.0, 190.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Edwards TRIMP
# ---------------------------------------------------------------------------

class TestEdwardsTrimp:
    def test_valori_tipici(self) -> None:
        zones = {"Z1": 10.0, "Z2": 20.0, "Z3": 15.0, "Z4": 10.0, "Z5": 5.0}
        # 10*1 + 20*2 + 15*3 + 10*4 + 5*5 = 10+40+45+40+25 = 160
        assert edwards_trimp(zones) == 160.0

    def test_solo_zona_tre(self) -> None:
        zones = {"Z3": 30.0}
        assert edwards_trimp(zones) == 90.0

    def test_dizionario_vuoto(self) -> None:
        assert edwards_trimp({}) == 0.0

    def test_chiavi_parziali(self) -> None:
        # Chiavi mancanti trattate come 0
        zones = {"Z1": 5.0, "Z5": 10.0}
        assert edwards_trimp(zones) == 5 * 1 + 10 * 5


# ---------------------------------------------------------------------------
# estimate_zone_minutes
# ---------------------------------------------------------------------------

class TestEstimateZoneMinutes:
    def test_z3_50_min(self) -> None:
        # avg_hr = 75% del max → Z3
        result = estimate_zone_minutes(50.0, 150.0, 200.0)
        assert result["Z3"] == 50.0
        assert result["Z1"] == result["Z2"] == result["Z4"] == result["Z5"] == 0.0

    def test_z1_bassa_intensita(self) -> None:
        result = estimate_zone_minutes(30.0, 100.0, 200.0)  # 50% → Z1
        assert result["Z1"] == 30.0

    def test_z5_massima_intensita(self) -> None:
        result = estimate_zone_minutes(10.0, 185.0, 200.0)  # 92.5% → Z5
        assert result["Z5"] == 10.0

    def test_max_hr_zero(self) -> None:
        result = estimate_zone_minutes(30.0, 150.0, 0.0)
        assert all(v == 0.0 for v in result.values())


# ---------------------------------------------------------------------------
# compute_training_load
# ---------------------------------------------------------------------------

class TestComputeTrainingLoad:
    def test_bannister_se_dati_disponibili(self) -> None:
        load, method = compute_training_load(60.0, 150.0, 55.0, 190.0, "M")
        assert method == "bannister"
        assert load is not None and load > 0

    def test_edwards_se_zone_fornite(self) -> None:
        zones = {"Z3": 60.0}
        load, method = compute_training_load(60.0, 150.0, 55.0, 190.0, "M", zone_minutes=zones)
        assert method == "edwards"
        assert load == 180.0

    def test_none_se_dati_mancanti(self) -> None:
        load, method = compute_training_load(60.0, None, None, None)
        assert load is None
        assert method is None

    def test_none_se_solo_avg_hr(self) -> None:
        # avg_hr senza resting e max → Bannister non calcolabile
        load, method = compute_training_load(60.0, 150.0, None, None)
        assert load is None


# ---------------------------------------------------------------------------
# CTL / ATL / TSB
# ---------------------------------------------------------------------------

class TestCtlAtlTsb:
    def test_ctl_cresce_con_carico(self) -> None:
        ctl = 0.0
        for _ in range(10):
            ctl = update_ctl(ctl, 100.0)
        assert ctl > 0

    def test_ctl_decade_senza_carico(self) -> None:
        ctl = 50.0
        ctl_after = update_ctl(ctl, 0.0)
        assert ctl_after < ctl

    def test_ctl_converge_al_carico(self) -> None:
        # Con carico costante di 100, CTL converge a 100 in molti giorni
        ctl = 0.0
        for _ in range(300):
            ctl = update_ctl(ctl, 100.0)
        assert abs(ctl - 100.0) < 1.0

    def test_atl_piu_reattivo_di_ctl(self) -> None:
        # Dopo un giorno ad alto carico, ATL cresce più di CTL
        atl = update_atl(0.0, 100.0)
        ctl = update_ctl(0.0, 100.0)
        assert atl > ctl  # tau ATL=7 < tau CTL=42 → risposta più rapida

    def test_tsb_positivo_quando_riposato(self) -> None:
        # CTL alto, ATL basso → TSB positivo
        assert compute_tsb(50.0, 30.0) == 20.0

    def test_tsb_negativo_quando_affaticato(self) -> None:
        assert compute_tsb(30.0, 50.0) == -20.0


# ---------------------------------------------------------------------------
# ACWR
# ---------------------------------------------------------------------------

class TestAcwr:
    def _make_loads(self, n_days: int, daily: float) -> list[tuple[str, float]]:
        """Genera n_days di carico costante da oggi indietro."""
        from datetime import date, timedelta
        today = date.today()
        return [
            ((today - timedelta(days=i)).isoformat(), daily)
            for i in range(n_days)
        ]

    def test_acwr_uno_con_carico_costante(self) -> None:
        from datetime import date
        loads = self._make_loads(28, 50.0)
        ref = date.today().isoformat()
        acwr = compute_acwr(loads, ref)
        # Acute = 7*50 = 350; Chronic = 28*50/4 = 350 → ACWR = 1.0
        assert acwr is not None
        assert abs(acwr - 1.0) < 0.01

    def test_acwr_none_senza_chronic(self) -> None:
        from datetime import date
        # Nessun carico → chronic=0 → None
        loads: list[tuple[str, float]] = []
        acwr = compute_acwr(loads, date.today().isoformat())
        assert acwr is None

    def test_acwr_alto_con_picco_acuto(self) -> None:
        from datetime import date, timedelta
        today = date.today()
        # 28 giorni a 10, ultimi 7 a 100
        loads = (
            [((today - timedelta(days=i)).isoformat(), 100.0) for i in range(7)]
            + [((today - timedelta(days=i)).isoformat(), 10.0) for i in range(7, 28)]
        )
        acwr = compute_acwr(loads, today.isoformat())
        assert acwr is not None
        assert acwr > 1.0


# ---------------------------------------------------------------------------
# Efficiency Factor
# ---------------------------------------------------------------------------

class TestEfficiencyFactor:
    def test_valore_tipico(self) -> None:
        # 10 km in 50 min con HR media 150
        ef = efficiency_factor(10000.0, 3000.0, 150.0)
        # speed = 10000/3000 ≈ 3.33 m/s; EF = 3.33/150 ≈ 0.0222
        assert ef is not None
        assert abs(ef - 10000 / 3000 / 150) < 0.000001

    def test_none_se_avg_hr_zero(self) -> None:
        assert efficiency_factor(10000.0, 3000.0, 0.0) is None

    def test_none_se_durata_zero(self) -> None:
        assert efficiency_factor(10000.0, 0.0, 150.0) is None

    def test_none_se_hr_negativa(self) -> None:
        assert efficiency_factor(10000.0, 3000.0, -10.0) is None


# ---------------------------------------------------------------------------
# Aerobic Decoupling
# ---------------------------------------------------------------------------

class TestAerobicDecoupling:
    def test_nessun_decoupling(self) -> None:
        # EF1 == EF2 → 0%
        assert aerobic_decoupling(0.02, 0.02) == 0.0

    def test_decoupling_positivo(self) -> None:
        # EF prima metà migliore → decoupling > 0
        result = aerobic_decoupling(0.02, 0.018)
        assert result is not None
        assert result > 0

    def test_none_se_ef1_zero(self) -> None:
        assert aerobic_decoupling(0.0, 0.018) is None


# ---------------------------------------------------------------------------
# Hiking / Trail
# ---------------------------------------------------------------------------

class TestHikingMetrics:
    def test_equivalent_distance(self) -> None:
        # 10 km + 500 m dislivello = 10 + 5 = 15 km
        assert equivalent_distance_km(10.0, 500.0) == 15.0

    def test_equivalent_distance_piano(self) -> None:
        # Senza dislivello = distanza reale
        assert equivalent_distance_km(10.0, 0.0) == 10.0

    def test_trail_effort_base(self) -> None:
        # Senza HR: 15 km equivalenti, 2 ore → effort = 15 * sqrt(2) ≈ 21.2
        effort = trail_effort(120.0, 10.0, 500.0)
        import math
        expected = 15.0 * math.sqrt(2.0)
        assert abs(effort - expected) < 0.1

    def test_trail_effort_con_hr(self) -> None:
        effort_no_hr = trail_effort(120.0, 10.0, 500.0)
        effort_con_hr = trail_effort(120.0, 10.0, 500.0, avg_hr=160.0, max_hr=190.0)
        # Con HR l'effort deve essere più alto
        assert effort_con_hr > effort_no_hr

    def test_trail_effort_durata_zero(self) -> None:
        # Non deve crashare con durata 0
        result = trail_effort(0.0, 5.0, 200.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Riegel
# ---------------------------------------------------------------------------

class TestRiegel:
    def test_stessa_distanza(self) -> None:
        # Prevedere per la stessa distanza deve ritornare lo stesso tempo
        result = riegel_predict(1800.0, 10.0, 10.0)
        assert result == 1800.0

    def test_maratona_da_mezza(self) -> None:
        # Mezza in 1:45:00 (6300s) → maratona prevista?
        t2 = riegel_predict(6300.0, 21.0975, 42.195)
        # T2 = 6300 * 2^1.06 ≈ 6300 * 2.085 ≈ 13136s ≈ 3:38:56
        assert 12000 < t2 < 15000

    def test_distanza_zero(self) -> None:
        assert riegel_predict(1800.0, 0.0, 10.0) == 0.0

    def test_tempo_zero(self) -> None:
        assert riegel_predict(0.0, 10.0, 5.0) == 0.0


# ---------------------------------------------------------------------------
# Recovery Score
# ---------------------------------------------------------------------------

class TestRecoveryScore:
    def test_neutrale_senza_dati(self) -> None:
        # Nessun dato → score neutrale 50
        assert recovery_score() == 50.0

    def test_hrv_alta_aumenta_score(self) -> None:
        score = recovery_score(hrv_delta=5.0)
        assert score > 50.0

    def test_hrv_bassa_diminuisce_score(self) -> None:
        score = recovery_score(hrv_delta=-5.0)
        assert score < 50.0

    def test_rhr_alta_diminuisce_score(self) -> None:
        # rhr_delta positivo = FC più alta del solito = peggio
        score = recovery_score(rhr_delta=5.0)
        assert score < 50.0

    def test_clamp_massimo(self) -> None:
        # Valori estremi positivi → clamp a 100
        score = recovery_score(hrv_delta=50.0, rhr_delta=-20.0, sleep_minutes=600.0, tsb=30.0)
        assert score == 100.0

    def test_clamp_minimo(self) -> None:
        # Valori estremi negativi → clamp a 0
        score = recovery_score(hrv_delta=-50.0, rhr_delta=20.0, sleep_minutes=0.0, tsb=-30.0)
        assert score == 0.0

    def test_sonno_target_raggiunto(self) -> None:
        # 8h esatte (target default) → contributo leggermente positivo
        score_con = recovery_score(sleep_minutes=480.0)
        score_senza = recovery_score()
        assert score_con > score_senza


# ---------------------------------------------------------------------------
# Sleep Score
# ---------------------------------------------------------------------------

class TestSleepScore:
    def test_none_senza_dati(self) -> None:
        assert sleep_score() is None

    def test_target_raggiunto(self) -> None:
        # 8h esatte → score durata = 100
        score = sleep_score(total_minutes=480.0)
        assert score is not None
        assert score == 100.0

    def test_meta_del_target(self) -> None:
        # 4h su 8h target → score durata = 50
        score = sleep_score(total_minutes=240.0)
        assert score is not None
        assert abs(score - 50.0) < 1.0

    def test_oltre_il_target(self) -> None:
        # 10h > 8h → score clamped a 100
        score = sleep_score(total_minutes=600.0)
        assert score == 100.0

    def test_con_deep_e_rem(self) -> None:
        # 8h, 20% deep (target), 22% REM (target) → score alto
        score = sleep_score(
            total_minutes=480.0,
            deep_sleep_minutes=96.0,   # 20%
            rem_sleep_minutes=105.6,   # 22%
        )
        assert score is not None
        assert score > 90.0

    def test_senza_deep_usa_solo_durata(self) -> None:
        # Senza deep sleep, usa solo durata + REM
        score_full = sleep_score(480.0, deep_sleep_minutes=96.0, rem_sleep_minutes=96.0)
        score_no_deep = sleep_score(480.0, rem_sleep_minutes=96.0)
        # Entrambi validi, non None
        assert score_full is not None
        assert score_no_deep is not None


# ---------------------------------------------------------------------------
# Rolling Baseline
# ---------------------------------------------------------------------------

class TestRollingBaseline:
    def test_none_con_meno_di_tre_valori(self) -> None:
        assert rolling_baseline([60.0, 65.0], window=7) is None
        assert rolling_baseline([60.0], window=7) is None

    def test_valori_costanti(self) -> None:
        # Tutti uguali → delta=0, z_score=0
        values = [60.0] * 15
        result = rolling_baseline(values, window=7)
        assert result is not None
        mean, delta, z = result
        assert abs(mean - 60.0) < 0.1
        assert delta == 0.0
        assert z == 0.0

    def test_valore_corrente_sopra_baseline(self) -> None:
        # Baseline a 60, valore corrente a 75 → delta positivo
        values = [60.0] * 10 + [75.0]
        result = rolling_baseline(values, window=7)
        assert result is not None
        _, delta, _ = result
        assert delta > 0

    def test_valore_corrente_sotto_baseline(self) -> None:
        values = [80.0] * 10 + [60.0]
        result = rolling_baseline(values, window=7)
        assert result is not None
        _, delta, _ = result
        assert delta < 0

    def test_finestra_piu_grande_della_serie(self) -> None:
        # Finestra 28 con solo 10 valori → deve funzionare ugualmente
        values = [60.0, 62.0, 58.0, 61.0, 63.0]
        result = rolling_baseline(values, window=28)
        assert result is not None


# ---------------------------------------------------------------------------
# format_seconds
# ---------------------------------------------------------------------------

class TestFormatSeconds:
    def test_minuti_e_secondi(self) -> None:
        assert format_seconds(185) == "3:05"

    def test_ore_minuti_secondi(self) -> None:
        assert format_seconds(3661) == "1:01:01"

    def test_zero(self) -> None:
        assert format_seconds(0) == "0:00"

    def test_un_ora_esatta(self) -> None:
        assert format_seconds(3600) == "1:00:00"
