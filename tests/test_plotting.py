import matplotlib
matplotlib.use("Agg")  # ikke-interaktiv backend - garanterer at plt.show() aldri kan blokkere i tester

import pandas as pd
import pytest

import plotting
from modeller import BeregningsInput


@pytest.fixture
def parametere():
    return BeregningsInput(qdim_l_s=300.0, lengde_m=10000.0, tillatte_sdr=[13.6, 17.0])


@pytest.fixture(autouse=True)
def midlertidig_output_mappe(tmp_path, monkeypatch):
    monkeypatch.setattr(plotting, "OUTPUT_MAPPE", tmp_path)
    return tmp_path


def test_lag_ledningskarakteristikk_lager_fil_uten_a_blokkere(parametere, midlertidig_output_mappe):
    plotting.lag_ledningskarakteristikk(DN=560.0, SDR=17.0, parametere=parametere, show_plot=False)

    filer = list(midlertidig_output_mappe.glob("ledningskarakteristikk_*.png"))
    assert len(filer) == 1


def test_plott_samlet_ledningskarakteristikk_ingen_ror_hopper_over(parametere, midlertidig_output_mappe, capsys):
    plotting.plott_samlet_ledningskarakteristikk([], parametere=parametere)

    filer = list(midlertidig_output_mappe.glob("samlet_ledningskarakteristikk_*.png"))
    assert filer == []


def test_plott_samlet_ledningskarakteristikk_flere_ror_ingen_hardkoding(parametere, midlertidig_output_mappe, capsys):
    ror_liste = [
        {"DN": 560.0, "SDR": 17.0},
        {"DN": 630.0, "SDR": 13.6},
        {"DN": 710.0, "SDR": 13.6},
    ]

    plotting.plott_samlet_ledningskarakteristikk(ror_liste, parametere=parametere, show_plot=False)

    filer = list(midlertidig_output_mappe.glob("samlet_ledningskarakteristikk_3_ror.png"))
    assert len(filer) == 1
    utskrift = capsys.readouterr().out
    assert "Q ved tau =" in utskrift
    utskrift.encode("cp1252")


def test_plott_pris_vs_skjaerspenning_tom_dataframe_hopper_over(parametere, midlertidig_output_mappe):
    plotting.plott_pris_vs_skjaerspenning(pd.DataFrame(), parametere=parametere)
    assert list(midlertidig_output_mappe.glob("*.png")) == []
