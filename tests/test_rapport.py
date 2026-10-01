import pytest

from config import CSV_FIL
from data_io import les_ror_csv
from modeller import BeregningsInput, RangeringsValg, RorValg
from rapport import lag_rapportdata
from tjenester import beregn_pumpeledning


@pytest.fixture(scope="module")
def katalog_df():
    return les_ror_csv(CSV_FIL)


@pytest.fixture
def beregningsresultat(katalog_df):
    return beregn_pumpeledning(
        parametere=BeregningsInput(
            qdim_l_s=300.0,
            lengde_m=10250.0,
            tillatte_sdr=[13.6, 17.0],
        ),
        rorkatalog=katalog_df,
        rangeringsvalg=RangeringsValg(strategi="billigste_godkjent"),
    )


def test_lag_rapportdata_fra_beregningsresultat(beregningsresultat):
    valgte_ror = [
        RorValg(dn_od_mm=630.0, sdr=13.6),
        RorValg(dn_od_mm=560.0, sdr=17.0),
    ]

    rapport = lag_rapportdata(beregningsresultat, valgte_ror=valgte_ror)

    assert rapport.input == beregningsresultat.input
    assert rapport.rangering == beregningsresultat.rangering
    assert rapport.antall_beregnet == len(beregningsresultat.alle_resultater)
    assert rapport.antall_godkjent == len(beregningsresultat.godkjente)
    assert rapport.antall_underkjent == len(beregningsresultat.underkjente)
    assert rapport.model_dump(mode="json")


def test_rapport_anbefaling_matcher_eksisterende_anbefaling(beregningsresultat):
    rapport = lag_rapportdata(beregningsresultat)

    assert rapport.anbefalt is not None
    assert beregningsresultat.anbefalt is not None
    assert rapport.anbefalt == beregningsresultat.anbefalt
    assert rapport.anbefalt is not beregningsresultat.anbefalt
    assert rapport.anbefalingsbegrunnelse == beregningsresultat.anbefalingsbegrunnelse


def test_rapport_inneholder_bare_valgte_sammenlignede_alternativer(
    beregningsresultat,
):
    valgte_ror = [
        RorValg(dn_od_mm=630.0, sdr=13.6),
        RorValg(dn_od_mm=560.0, sdr=17.0),
    ]

    rapport = lag_rapportdata(beregningsresultat, valgte_ror=valgte_ror)

    assert [
        (ror.dn_od_mm, ror.sdr) for ror in rapport.sammenlignede_alternativer
    ] == [(630.0, 13.6), (560.0, 17.0)]
    assert len(rapport.sammenlignede_alternativer) < len(beregningsresultat.godkjente)


def test_rapport_kopierer_viktige_beregnede_verdier(beregningsresultat):
    valgt = RorValg(dn_od_mm=560.0, sdr=17.0)
    rapport = lag_rapportdata(beregningsresultat, valgte_ror=[valgt])

    original = next(
        ror
        for ror in beregningsresultat.godkjente
        if ror.dn_od_mm == valgt.dn_od_mm and ror.sdr == valgt.sdr
    )
    rapport_ror = rapport.sammenlignede_alternativer[0]

    assert rapport_ror.indre_diameter_mm == pytest.approx(original.indre_diameter_mm)
    assert rapport_ror.vannhastighet_m_s == pytest.approx(original.vannhastighet_m_s)
    assert rapport_ror.skjaerspenning_pa == pytest.approx(original.skjaerspenning_pa)
    assert rapport_ror.friksjonstap_m == pytest.approx(original.friksjonstap_m)
    assert rapport_ror.singulaertap_m == pytest.approx(original.singulaertap_m)
    assert rapport_ror.totalt_tap_m == pytest.approx(original.totalt_tap_m)
    assert rapport_ror.trykk_fra_totalt_tap_bar == pytest.approx(
        original.trykk_fra_totalt_tap_bar
    )
    assert rapport_ror.tillatt_trykk_bar == pytest.approx(original.tillatt_trykk_bar)
    assert rapport_ror.vekt_lodd_kg_m == pytest.approx(original.vekt_lodd_kg_m)
    assert rapport_ror.pris_mnok == pytest.approx(original.pris_mnok)
    assert rapport_ror.godkjent is True
    assert rapport_ror.avviksarsaker == []


def test_lag_rapportdata_muterer_ikke_beregningsresultat(beregningsresultat):
    for_lag_rapportdata = beregningsresultat.model_dump()

    lag_rapportdata(
        beregningsresultat,
        valgte_ror=[RorValg(dn_od_mm=560.0, sdr=17.0)],
    )

    assert beregningsresultat.model_dump() == for_lag_rapportdata


def test_rapport_avviser_ror_utenfor_godkjent_resultatsett(beregningsresultat):
    underkjent = beregningsresultat.underkjente[0]

    with pytest.raises(ValueError, match="Bare godkjente rør"):
        lag_rapportdata(
            beregningsresultat,
            valgte_ror=[RorValg(dn_od_mm=underkjent.dn_od_mm, sdr=underkjent.sdr)],
        )
