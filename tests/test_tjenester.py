import pandas as pd
import pytest

from config import CSV_FIL
from data_io import les_ror_csv
from modeller import BeregningsInput, RangeringsValg
from tjenester import beregn_pumpeledning


@pytest.fixture(scope="module")
def katalog_df():
    return les_ror_csv(CSV_FIL)


@pytest.fixture
def referanse_parametere():
    return BeregningsInput(qdim_l_s=300.0, lengde_m=10250.0, tillatte_sdr=[13.6, 17.0])


def test_beregn_pumpeledning_referansetilfelle(katalog_df, referanse_parametere):
    resultat = beregn_pumpeledning(
        parametere=referanse_parametere,
        rorkatalog=katalog_df,
        rangeringsvalg=RangeringsValg(strategi="billigste_godkjent"),
    )

    assert resultat.anbefalt is not None
    assert resultat.anbefalt.dn_od_mm == pytest.approx(560.0)
    assert resultat.anbefalt.sdr_navn == "SDR 17"
    assert resultat.anbefalt.pris_mnok == pytest.approx(52.783653, rel=1e-5)
    assert len(resultat.godkjente) + len(resultat.underkjente) == len(resultat.alle_resultater)


def test_beregn_pumpeledning_tom_katalog_gir_feil(referanse_parametere):
    with pytest.raises(ValueError):
        beregn_pumpeledning(
            parametere=referanse_parametere,
            rorkatalog=pd.DataFrame(),
            rangeringsvalg=RangeringsValg(strategi="billigste_godkjent"),
        )


def test_beregn_pumpeledning_ukjent_sdr_gir_feil(katalog_df):
    parametere = BeregningsInput(qdim_l_s=300.0, lengde_m=10250.0, tillatte_sdr=[999.0])

    with pytest.raises(ValueError):
        beregn_pumpeledning(
            parametere=parametere,
            rorkatalog=katalog_df,
            rangeringsvalg=RangeringsValg(strategi="billigste_godkjent"),
        )


def test_beregn_pumpeledning_med_balansert_rangering(katalog_df, referanse_parametere):
    resultat = beregn_pumpeledning(
        parametere=referanse_parametere,
        rorkatalog=katalog_df,
        rangeringsvalg=RangeringsValg(strategi="balansert"),
    )

    assert resultat.anbefalt is not None
    assert resultat.rangering.strategi == "balansert"


def test_underkjente_ror_har_avviksarsaker_i_resultatmodell(katalog_df, referanse_parametere):
    resultat = beregn_pumpeledning(
        parametere=referanse_parametere,
        rorkatalog=katalog_df,
        rangeringsvalg=RangeringsValg(strategi="billigste_godkjent"),
    )

    assert len(resultat.underkjente) > 0
    for ror in resultat.underkjente:
        assert len(ror.avviksarsaker) > 0

    for ror in resultat.godkjente:
        assert ror.avviksarsaker == []
