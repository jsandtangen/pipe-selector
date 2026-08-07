import math

import pytest

from oppdrift_lodd import beregn_excel_lodd
from modeller import BeregningsInput


@pytest.fixture
def parametere():
    return BeregningsInput(qdim_l_s=300.0, lengde_m=10250.0, tillatte_sdr=[13.6, 17.0])


def test_beregn_excel_lodd_kjente_verdier(parametere):
    DN_mm = 560.0
    SDR = 17.0
    kg_per_m_csv = 56.6

    resultat = beregn_excel_lodd(DN_mm=DN_mm, SDR=SDR, kg_per_m_csv=kg_per_m_csv, parametere=parametere)

    d_y = DN_mm / 1000.0
    d_i = d_y * (1.0 - 2.0 / SDR)
    vannfylling = 1.0 - parametere.luftfylling_andel

    vekt_pe = parametere.rho_pe_kg_m3 * math.pi / 4.0 * (d_y**2 - d_i**2)
    vekt_avlop = parametere.rho_avlop_kg_m3 * math.pi / 4.0 * d_i**2 * vannfylling
    oppdrift = parametere.rho_saltvann_kg_m3 * math.pi / 4.0 * d_y**2
    netto_oppdrift = max(0.0, oppdrift - vekt_pe - vekt_avlop)
    vekt_lodd = netto_oppdrift * parametere.rho_lodd_kg_m3 / (parametere.rho_lodd_kg_m3 - parametere.rho_saltvann_kg_m3)

    assert resultat["Indre diameter [mm]"] == pytest.approx(d_i * 1000.0, rel=1e-9)
    assert resultat["Vekt PE teoretisk [kg/m]"] == pytest.approx(vekt_pe, rel=1e-9)
    assert resultat["Netto oppdrift [kg/m]"] == pytest.approx(netto_oppdrift, rel=1e-9)
    assert resultat["Vekt lodd [kg/m]"] == pytest.approx(vekt_lodd, rel=1e-9)
    assert resultat["Rørkostnad [kr/m]"] == pytest.approx(kg_per_m_csv * parametere.pris_ror_kr_per_kg, rel=1e-9)
    assert resultat["Lodd kr/m"] == pytest.approx(vekt_lodd * parametere.pris_lodd_kr_per_kg, rel=1e-9)


def test_netto_oppdrift_kan_ikke_bli_negativ(parametere):
    # Svært lite rør: oppdriften kan i teorien bli mindre enn egenvekten.
    # Netto oppdrift skal da klippes til 0, ikke bli negativ.
    resultat = beregn_excel_lodd(DN_mm=20.0, SDR=41.0, kg_per_m_csv=0.05, parametere=parametere)
    assert resultat["Netto oppdrift [kg/m]"] >= 0.0


def test_pris_skalerer_lineaert_med_rorvekt(parametere):
    resultat_1 = beregn_excel_lodd(DN_mm=560.0, SDR=17.0, kg_per_m_csv=10.0, parametere=parametere)
    resultat_2 = beregn_excel_lodd(DN_mm=560.0, SDR=17.0, kg_per_m_csv=20.0, parametere=parametere)

    assert resultat_2["Rørkostnad [kr/m]"] == pytest.approx(
        2.0 * resultat_1["Rørkostnad [kr/m]"], rel=1e-9
    )


def test_lengde_sjo_default_er_hele_lengden():
    p = BeregningsInput(qdim_l_s=300.0, lengde_m=1000.0, tillatte_sdr=[17.0])
    assert p.hent_lengde_sjo_m() == pytest.approx(1000.0)


def test_lengde_sjo_kan_overstyres():
    p = BeregningsInput(
        qdim_l_s=300.0,
        lengde_m=1000.0,
        tillatte_sdr=[17.0],
        lengde_sjo_m=400.0,
        lengde_land_m=600.0,
    )
    assert p.hent_lengde_sjo_m() == pytest.approx(400.0)
