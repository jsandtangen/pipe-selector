import pytest

from config import CSV_FIL
from data_io import (
    les_ror_csv,
    finn_sdr_liste_fra_katalog,
    filtrer_sdr_liste,
    sjekk_nodvendige_kolonner,
    er_veggtykkelse_rimelig,
    finn_duplikate_dn,
    sjekk_ingen_duplikate_dn,
    valider_rorkatalog,
)


MINI_CSV = (
    "DN/OD [mm];SDR 17 Veggtykkelse [mm];SDR 17 Vekt [kg/m];"
    "SDR 13,6 Veggtykkelse [mm];SDR 13,6 Vekt [kg/m]\n"
    "560;33,2;56,6;41,2;69,0\n"
    "600;35,6;60,0;44,1;73,0\n"
)


@pytest.fixture
def mini_katalog(tmp_path):
    filsti = tmp_path / "mini_ror.csv"
    filsti.write_text(MINI_CSV, encoding="utf-8")
    return filsti


def test_les_ror_csv_gir_kanonisk_dn_od_kolonne(mini_katalog):
    df = les_ror_csv(mini_katalog)
    assert "DN/OD" in df.columns
    assert list(df["DN/OD"]) == [560.0, 600.0]


def test_finn_sdr_liste_fra_katalog_finner_alle_klasser(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste = finn_sdr_liste_fra_katalog(df)

    sdr_verdier = [info["SDR"] for info in sdr_liste]
    assert sdr_verdier == [13.6, 17.0]  # sortert stigende

    for info in sdr_liste:
        assert info["veggtykkelse_kolonne"] in df.columns
        assert info["kg_per_m_kolonne"] in df.columns


def test_finn_sdr_liste_fra_katalog_ingen_sdr_gir_feil(tmp_path):
    filsti = tmp_path / "tom.csv"
    filsti.write_text("DN/OD [mm];Noe annet\n560;1\n", encoding="utf-8")
    df = les_ror_csv(filsti)

    with pytest.raises(ValueError):
        finn_sdr_liste_fra_katalog(df)


def test_filtrer_sdr_liste_velger_riktige_klasser(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste_full = finn_sdr_liste_fra_katalog(df)

    filtrert = filtrer_sdr_liste(sdr_liste_full, [17.0])
    assert len(filtrert) == 1
    assert filtrert[0]["SDR-navn"] == "SDR 17"


def test_filtrer_sdr_liste_ukjent_sdr_gir_feil(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste_full = finn_sdr_liste_fra_katalog(df)

    with pytest.raises(ValueError):
        filtrer_sdr_liste(sdr_liste_full, [99.0])


def test_filtrer_sdr_liste_tom_liste_gir_feil(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste_full = finn_sdr_liste_fra_katalog(df)

    with pytest.raises(ValueError):
        filtrer_sdr_liste(sdr_liste_full, [])


def test_sjekk_nodvendige_kolonner_ok(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste = finn_sdr_liste_fra_katalog(df)
    sjekk_nodvendige_kolonner(df=df, sdr_liste=sdr_liste)  # skal ikke kaste feil


def test_sjekk_nodvendige_kolonner_mangler_kolonne(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste = finn_sdr_liste_fra_katalog(df)
    sdr_liste[0]["veggtykkelse_kolonne"] = "Finnes ikke"

    with pytest.raises(ValueError):
        sjekk_nodvendige_kolonner(df=df, sdr_liste=sdr_liste)


def test_er_veggtykkelse_rimelig():
    # For DN560 SDR17 er forventet veggtykkelse 560/17 = 32,94 mm
    assert er_veggtykkelse_rimelig(DN=560.0, SDR=17.0, veggtykkelse=33.2) is True
    assert er_veggtykkelse_rimelig(DN=560.0, SDR=17.0, veggtykkelse=1.0) is False
    assert er_veggtykkelse_rimelig(DN=560.0, SDR=17.0, veggtykkelse=100.0) is False


def test_finn_duplikate_dn_ingen_duplikater(mini_katalog):
    df = les_ror_csv(mini_katalog)
    assert finn_duplikate_dn(df) == []


def test_finn_duplikate_dn_finner_duplikat(tmp_path):
    csv_med_duplikat = (
        "DN/OD [mm];SDR 17 Veggtykkelse [mm];SDR 17 Vekt [kg/m]\n"
        "560;33,2;56,6\n"
        "560;33,0;56,0\n"
        "600;35,6;60,0\n"
    )
    filsti = tmp_path / "dup.csv"
    filsti.write_text(csv_med_duplikat, encoding="utf-8")

    df = les_ror_csv(filsti)
    assert finn_duplikate_dn(df) == [560.0]


def test_sjekk_ingen_duplikate_dn_ok(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sjekk_ingen_duplikate_dn(df)  # skal ikke kaste feil


def test_sjekk_ingen_duplikate_dn_gir_feil_ved_duplikat(tmp_path):
    csv_med_duplikat = (
        "DN/OD [mm];SDR 17 Veggtykkelse [mm];SDR 17 Vekt [kg/m]\n"
        "560;33,2;56,6\n"
        "560;33,0;56,0\n"
    )
    filsti = tmp_path / "dup.csv"
    filsti.write_text(csv_med_duplikat, encoding="utf-8")
    df = les_ror_csv(filsti)

    with pytest.raises(ValueError):
        sjekk_ingen_duplikate_dn(df)


def test_valider_rorkatalog_ingen_avvik_for_gyldig_katalog(mini_katalog):
    df = les_ror_csv(mini_katalog)
    sdr_liste = finn_sdr_liste_fra_katalog(df)
    assert valider_rorkatalog(df, sdr_liste) == []


def test_valider_rorkatalog_flagger_urimelig_veggtykkelse(tmp_path):
    csv_urimelig = (
        "DN/OD [mm];SDR 17 Veggtykkelse [mm];SDR 17 Vekt [kg/m]\n"
        "560;1,0;56,6\n"  # veggtykkelse langt under forventet 560/17=32,9mm
    )
    filsti = tmp_path / "urimelig.csv"
    filsti.write_text(csv_urimelig, encoding="utf-8")
    df = les_ror_csv(filsti)
    sdr_liste = finn_sdr_liste_fra_katalog(df)

    avvik = valider_rorkatalog(df, sdr_liste)
    assert len(avvik) == 1
    assert avvik[0]["DN"] == 560.0


def test_valider_rorkatalog_glisne_kombinasjoner_er_ikke_avvik(mini_katalog):
    """
    En DN/SDR-kombinasjon som rett og slett ikke finnes i katalogen
    (begge celler tomme) skal ikke rapporteres som en feil.
    """
    df = les_ror_csv(mini_katalog)
    sdr_liste = finn_sdr_liste_fra_katalog(df)
    avvik = valider_rorkatalog(df, sdr_liste)
    assert avvik == []


def test_ekte_rorkatalog_leses_og_finner_sdr_klasser():
    """
    Integrasjonstest mot den faktiske data/RØR.csv, slik den er akkurat nå.
    Fanger opp fremtidig drift mellom katalogens kolonnenavn og koden.
    """
    df = les_ror_csv(CSV_FIL)
    sdr_liste = finn_sdr_liste_fra_katalog(df)

    sdr_navn = {info["SDR-navn"] for info in sdr_liste}
    assert "SDR 17" in sdr_navn
    assert "SDR 13,6" in sdr_navn

    sjekk_nodvendige_kolonner(df=df, sdr_liste=sdr_liste)  # skal ikke kaste feil
    sjekk_ingen_duplikate_dn(df)  # skal ikke kaste feil
