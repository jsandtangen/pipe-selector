import math

import pytest

from hydraulikk import (
    beregn_hastighet,
    beregn_reynolds,
    colebrook_white,
    beregn_friksjonstap,
    beregn_singulaertap,
    beregn_skjaerspenning,
    beregn_indre_diameter,
    beregn_tillatt_trykk_bar,
    beregn_trykk_fra_lofte,
    beregn_maks_utvendig_diameter_mm,
)


def test_beregn_hastighet_kjent_verdi():
    # v = Q / (pi * d^2 / 4). Q=1 m3/s, d=1 m -> v = 4/pi
    v = beregn_hastighet(q=1.0, d=1.0)
    assert v == pytest.approx(4.0 / math.pi, rel=1e-9)


def test_beregn_hastighet_skalerer_med_q():
    v1 = beregn_hastighet(q=0.3, d=0.5)
    v2 = beregn_hastighet(q=0.6, d=0.5)
    assert v2 == pytest.approx(2.0 * v1, rel=1e-9)


def test_beregn_reynolds_kjent_verdi():
    # Re = v*d/nu
    Re = beregn_reynolds(v=2.0, d=0.5, nu=0.000001309)
    assert Re == pytest.approx(2.0 * 0.5 / 0.000001309, rel=1e-9)


def test_colebrook_white_laminaer_stromning():
    # Re < 2300 skal gi f = 64/Re (laminært uttrykk)
    f = colebrook_white(Re=1000.0, k=0.0005, d=0.5)
    assert f == pytest.approx(64.0 / 1000.0, rel=1e-9)


def test_colebrook_white_turbulent_konvergerer():
    f = colebrook_white(Re=500_000.0, k=0.0005, d=0.5)

    # Sjekk at f faktisk løser Colebrook-White-ligningen (residual ~ 0)
    Re = 500_000.0
    k = 0.0005
    d = 0.5
    venstre = 1.0 / math.sqrt(f)
    hoyre = -2.0 * math.log10((k / d) / 3.7 + 2.51 / (Re * math.sqrt(f)))
    assert venstre == pytest.approx(hoyre, rel=1e-6)


def test_colebrook_white_ugyldig_input_gir_nan():
    assert math.isnan(colebrook_white(Re=0.0, k=0.0005, d=0.5))
    assert math.isnan(colebrook_white(Re=1000.0, k=0.0005, d=0.0))


def test_beregn_friksjonstap_kjent_verdi():
    # Hf = f * L/d * v^2 / (2g)
    Hf = beregn_friksjonstap(f=0.02, L=1000.0, v=1.5, d=0.5, g=9.81)
    forventet = 0.02 * 1000.0 / 0.5 * 1.5**2 / (2.0 * 9.81)
    assert Hf == pytest.approx(forventet, rel=1e-9)


def test_beregn_singulaertap_kjent_verdi():
    # St = Tk * v^2 / (2g)
    St = beregn_singulaertap(Tk=5.0, v=1.5, g=9.81)
    forventet = 5.0 * 1.5**2 / (2.0 * 9.81)
    assert St == pytest.approx(forventet, rel=1e-9)


def test_beregn_skjaerspenning_kjent_verdi():
    # tau = gamma * d * Hf / (4L)
    tau = beregn_skjaerspenning(gamma=9806.65, d=0.5, Hf=50.0, L=10000.0)
    forventet = 9806.65 * 0.5 * 50.0 / (4.0 * 10000.0)
    assert tau == pytest.approx(forventet, rel=1e-9)


def test_beregn_indre_diameter_kjent_verdi():
    # d_i = DN * (1 - 2/SDR)
    d_i = beregn_indre_diameter(DN_mm=560.0, SDR=17.0)
    assert d_i == pytest.approx(560.0 * (1.0 - 2.0 / 17.0), rel=1e-9)


def test_beregn_tillatt_trykk_bar_sdr41_pe100():
    # p = 2*sigma/(SDR-1). SDR41, sigma=8 MPa -> 16/40 = 0.4 MPa = 4 bar.
    p_bar = beregn_tillatt_trykk_bar(SDR=41.0, sigma_mpa=8.0)
    assert p_bar == pytest.approx(4.0, rel=1e-9)


def test_beregn_tillatt_trykk_bar_sdr17_pe100():
    # SDR17, sigma=8 MPa -> 16/16 = 1.0 MPa = 10 bar.
    p_bar = beregn_tillatt_trykk_bar(SDR=17.0, sigma_mpa=8.0)
    assert p_bar == pytest.approx(10.0, rel=1e-9)


def test_beregn_tillatt_trykk_bar_lavere_sdr_gir_hoyere_trykk():
    p_sdr41 = beregn_tillatt_trykk_bar(SDR=41.0, sigma_mpa=8.0)
    p_sdr17 = beregn_tillatt_trykk_bar(SDR=17.0, sigma_mpa=8.0)
    assert p_sdr17 > p_sdr41


def test_beregn_trykk_fra_lofte_kjent_verdi():
    # 64 m vannsøyle med gamma=9806,65 N/m3 -> ca 6,28 bar
    p_bar = beregn_trykk_fra_lofte(H_total_m=64.0, gamma_n_m3=9806.65)
    assert p_bar == pytest.approx(9806.65 * 64.0 / 100_000.0, rel=1e-9)
    assert p_bar == pytest.approx(6.276, abs=0.01)


def test_beregn_maks_utvendig_diameter_ved_0_7_mpa():
    assert beregn_maks_utvendig_diameter_mm(0.7) == pytest.approx(1900.0)


def test_beregn_maks_utvendig_diameter_er_monoton_med_trykk():
    assert beregn_maks_utvendig_diameter_mm(1.0) < beregn_maks_utvendig_diameter_mm(0.7)
    assert beregn_maks_utvendig_diameter_mm(0.5) > beregn_maks_utvendig_diameter_mm(0.7)


@pytest.mark.parametrize("trykk_mpa", [0.0, -0.7])
def test_beregn_maks_utvendig_diameter_avviser_ugyldig_trykk(trykk_mpa):
    with pytest.raises(ValueError, match="større enn 0 MPa"):
        beregn_maks_utvendig_diameter_mm(trykk_mpa)
