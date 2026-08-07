import pandas as pd
import pytest

from config import CSV_FIL
from data_io import les_ror_csv, finn_sdr_liste_fra_katalog, filtrer_sdr_liste
from beregninger import beregn_alle_alternativer, finn_godkjente
from modeller import BeregningsInput


@pytest.fixture(scope="module")
def katalog_df():
    return les_ror_csv(CSV_FIL)


@pytest.fixture(scope="module")
def sdr_liste_full(katalog_df):
    return finn_sdr_liste_fra_katalog(katalog_df)


@pytest.fixture
def referanse_parametere():
    """Standardscenariet: Qdim=300 l/s, L=10250 m, dagens standardverdier."""
    return BeregningsInput(
        qdim_l_s=300.0,
        lengde_m=10250.0,
        tillatte_sdr=[13.6, 17.0],
    )


def test_finn_godkjente_tom_dataframe_gir_tom_dataframe():
    tom_df = pd.DataFrame()
    resultat = finn_godkjente(tom_df)
    assert resultat.empty


def test_finn_godkjente_sorterer_stigende_pa_pris():
    df = pd.DataFrame([
        {"Pris [MNOK]": 30.0, "Godkjent": True},
        {"Pris [MNOK]": 10.0, "Godkjent": True},
        {"Pris [MNOK]": 20.0, "Godkjent": False},
    ])
    godkjente = finn_godkjente(df)
    assert list(godkjente["Pris [MNOK]"]) == [10.0, 30.0]


def test_referansetilfelle_dn560_sdr17_anbefales(katalog_df, sdr_liste_full, referanse_parametere):
    """
    Referansetest for standardscenariet (Qdim=300 l/s, L=10250 m) med dagens
    standardverdier (modeller.BeregningsInput) og tillatte_sdr=[13.6, 17.0].

    Bekreftet med bruker 2026-08-06 etter at rørkatalogen ble lest dynamisk:
    DN560 SDR17 skal fortsatt være billigst godkjent rør, uendret fra før
    katalogen ble utvidet til 9 SDR-klasser.
    """
    sdr_liste = filtrer_sdr_liste(sdr_liste_full, referanse_parametere.tillatte_sdr)

    resultat_df = beregn_alle_alternativer(df=katalog_df, sdr_liste=sdr_liste, parametere=referanse_parametere)
    godkjente_df = finn_godkjente(resultat_df)

    assert not godkjente_df.empty

    billigst = godkjente_df.iloc[0]

    assert billigst["DN"] == pytest.approx(560.0)
    assert billigst["SDR"] == "SDR 17"
    assert billigst["Indre diameter [mm]"] == pytest.approx(494.117647, rel=1e-6)
    assert billigst["Vannhastighet [m/s]"] == pytest.approx(1.564482, rel=1e-5)
    assert billigst["Total løftehøyde [m]"] == pytest.approx(52.897696, rel=1e-5)
    assert billigst["Skjærspenning [Pa]"] == pytest.approx(6.178065, rel=1e-5)
    assert billigst["Pris [MNOK]"] == pytest.approx(52.783653, rel=1e-5)


def test_underkjente_ror_har_falske_kravflagg(katalog_df, sdr_liste_full, referanse_parametere):
    sdr_liste = filtrer_sdr_liste(sdr_liste_full, referanse_parametere.tillatte_sdr)
    resultat_df = beregn_alle_alternativer(df=katalog_df, sdr_liste=sdr_liste, parametere=referanse_parametere)

    tap_kolonne = f"Krav total løftehøyde <= {referanse_parametere.maks_totalt_tap_m:.0f} m"

    underkjente_df = resultat_df[resultat_df["Godkjent"] == False]
    assert not underkjente_df.empty

    for _, rad in underkjente_df.iterrows():
        krav_oppfylt = (
            rad["Krav hastighet >= 1 m/s"]
            and rad["Krav skjærspenning >= 2 Pa"]
            and rad[tap_kolonne]
            and rad["Krav trykklasse (SDR)"]
        )
        assert krav_oppfylt is False


def test_tynnvegget_ror_underkjennes_pa_trykklasse(katalog_df, sdr_liste_full):
    """
    Regresjonstest for det brukeren faktisk rapporterte: et tynnvegget rør
    (høy SDR) kan være hydraulisk godkjent, men fysisk uegnet fordi trykket
    fra totalt tap overstiger hva rørets trykklasse tåler. DN500 SDR41 med
    default sigma (PE100, 8 MPa) tåler 4,0 bar.
    """
    parametere = BeregningsInput(
        qdim_l_s=300.0,
        lengde_m=10250.0,
        tillatte_sdr=[41.0],
        maks_totalt_tap_m=200.0,  # høyt nok til at trykkravet er det avgjørende, ikke tap-grensen
    )
    sdr_liste = filtrer_sdr_liste(sdr_liste_full, parametere.tillatte_sdr)
    resultat_df = beregn_alle_alternativer(df=katalog_df, sdr_liste=sdr_liste, parametere=parametere)

    rad = resultat_df[resultat_df["DN"] == 500.0].iloc[0]

    assert rad["Tillatt trykk SDR [bar]"] == pytest.approx(4.0, rel=1e-6)
    assert rad["Trykk fra totalt tap [bar]"] > rad["Tillatt trykk SDR [bar]"]
    assert rad["Krav trykklasse (SDR)"] == False
    assert rad["Godkjent"] == False
    assert any("trykket fra totalt tap" in arsak for arsak in rad["Avviksårsaker"])


def test_underkjente_ror_har_avviksarsaker(katalog_df, sdr_liste_full, referanse_parametere):
    sdr_liste = filtrer_sdr_liste(sdr_liste_full, referanse_parametere.tillatte_sdr)
    resultat_df = beregn_alle_alternativer(df=katalog_df, sdr_liste=sdr_liste, parametere=referanse_parametere)

    underkjente_df = resultat_df[resultat_df["Godkjent"] == False]
    godkjente_df = resultat_df[resultat_df["Godkjent"] == True]

    assert not underkjente_df.empty
    for arsaker in underkjente_df["Avviksårsaker"]:
        assert len(arsaker) > 0

    for arsaker in godkjente_df["Avviksårsaker"]:
        assert arsaker == []
