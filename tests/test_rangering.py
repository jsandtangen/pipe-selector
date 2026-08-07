import pandas as pd
import pytest
from pydantic import ValidationError

from modeller import BeregningsInput, RangeringsValg
from rangering import velg_anbefaling


@pytest.fixture
def parametere():
    return BeregningsInput(
        qdim_l_s=300.0,
        lengde_m=10000.0,
        tillatte_sdr=[13.6, 17.0],
        maks_totalt_tap_m=70.0,
        min_hastighet_m_s=1.0,
        min_skjaerspenning_pa=2.0,
    )


@pytest.fixture
def godkjente_df():
    # Tre syntetiske godkjente rør med bevisst ulike styrker:
    # A: billigst, men svakest hydraulisk margin
    # B: dyrest, men best hydraulisk margin (mest tap-margin og skjærspenning)
    # C: midt på treet, best på vannhastighet
    return pd.DataFrame([
        {
            "DN": 560, "SDR": "SDR 17",
            "Pris [MNOK]": 50.0,
            "Vannhastighet [m/s]": 1.1,
            "Total løftehøyde [m]": 65.0,
            "Skjærspenning [Pa]": 2.5,
        },
        {
            "DN": 630, "SDR": "SDR 17",
            "Pris [MNOK]": 70.0,
            "Vannhastighet [m/s]": 1.3,
            "Total løftehøyde [m]": 30.0,
            "Skjærspenning [Pa]": 4.0,
        },
        {
            "DN": 600, "SDR": "SDR 13,6",
            "Pris [MNOK]": 60.0,
            "Vannhastighet [m/s]": 1.6,
            "Total løftehøyde [m]": 45.0,
            "Skjærspenning [Pa]": 3.0,
        },
    ])


def test_billigste_godkjent_velger_lavest_pris(godkjente_df, parametere):
    valg = RangeringsValg(strategi="billigste_godkjent")
    anbefalt, begrunnelse, _ = velg_anbefaling(godkjente_df, valg, parametere)

    assert anbefalt["DN"] == 560
    assert "lavest pris" in begrunnelse


def test_best_hydraulisk_leksikografisk_prioritet(godkjente_df, parametere):
    valg = RangeringsValg(
        strategi="best_hydraulisk",
        hydraulisk_prioritet=["margin_totalt_tap", "margin_skjaerspenning"],
    )
    anbefalt, begrunnelse, _ = velg_anbefaling(godkjente_df, valg, parametere)

    # DN630 har mest margin til maks tap (70-30=40) av de tre
    assert anbefalt["DN"] == 630
    assert "best hydraulisk" in begrunnelse


def test_best_hydraulisk_krever_prioritet():
    with pytest.raises(ValidationError):
        RangeringsValg(strategi="best_hydraulisk")


def test_best_hydraulisk_avviser_duplikater():
    with pytest.raises(ValidationError):
        RangeringsValg(
            strategi="best_hydraulisk",
            hydraulisk_prioritet=["margin_hastighet", "margin_hastighet"],
        )


def test_balansert_bruker_fast_vekting(godkjente_df, parametere):
    valg = RangeringsValg(strategi="balansert")
    anbefalt, begrunnelse, _ = velg_anbefaling(godkjente_df, valg, parametere)

    assert "50% pris" in begrunnelse or "50%" in begrunnelse
    assert anbefalt is not None


def test_egendefinert_vekting_krever_vekter():
    with pytest.raises(ValidationError):
        RangeringsValg(strategi="egendefinert_vekting")


def test_egendefinert_vekting_normaliserer_vilkarlige_positive_vekter(godkjente_df, parametere):
    # Vekter som ikke summerer til 1,0 eller 100 skal normaliseres automatisk,
    # ikke avvises.
    valg = RangeringsValg(
        strategi="egendefinert_vekting",
        vekter={"pris": 2.0, "hastighet": 1.0, "skjaerspenning": 1.0},
    )
    anbefalt, begrunnelse, _ = velg_anbefaling(godkjente_df, valg, parametere)

    assert anbefalt is not None
    assert "50% pris" in begrunnelse  # 2/(2+1+1) = 50%


def test_egendefinert_vekting_avviser_negativ_vekt():
    with pytest.raises(ValidationError):
        RangeringsValg(
            strategi="egendefinert_vekting",
            vekter={"pris": -1.0, "hastighet": 1.0},
        )


def test_velg_anbefaling_tom_dataframe_gir_ingen_anbefaling(parametere):
    valg = RangeringsValg(strategi="billigste_godkjent")
    anbefalt, begrunnelse, rangert = velg_anbefaling(pd.DataFrame(), valg, parametere)

    assert anbefalt is None
    assert "ingen anbefaling" in begrunnelse.lower()


def test_alle_like_verdier_gir_ikke_krasj(parametere):
    """Regresjonstest for 0/0-tilfellet i min-maks-normalisering."""
    df = pd.DataFrame([
        {"DN": 560, "SDR": "SDR 17", "Pris [MNOK]": 50.0, "Vannhastighet [m/s]": 1.2,
         "Total løftehøyde [m]": 40.0, "Skjærspenning [Pa]": 3.0},
        {"DN": 600, "SDR": "SDR 17", "Pris [MNOK]": 50.0, "Vannhastighet [m/s]": 1.2,
         "Total løftehøyde [m]": 40.0, "Skjærspenning [Pa]": 3.0},
    ])
    valg = RangeringsValg(strategi="balansert")
    anbefalt, begrunnelse, _ = velg_anbefaling(df, valg, parametere)
    assert anbefalt is not None
