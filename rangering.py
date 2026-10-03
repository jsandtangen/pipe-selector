"""Rangerer godkjente rør etter pris, hydrauliske marginer eller vektet score."""

import pandas as pd

from modeller import RangeringsValg, BeregningsInput

BALANSERT_VEKTER = {"pris": 0.5, "hastighet": 0.25, "skjaerspenning": 0.25}

_MARGIN_BESKRIVELSE = {
    "margin_totalt_tap": "margin til maks totalt tap",
    "margin_skjaerspenning": "margin over minstekrav til skjærspenning",
    "margin_hastighet": "margin over minstekrav til vannhastighet",
}


def _ror_navn(rad):
    return f"DN{int(rad['DN'])} {rad['SDR']}"


def _normaliser_vekter(vekter):
    total = sum(vekter.values())

    if total <= 0:
        raise ValueError("Summen av vektene må være positiv.")

    return {navn: verdi / total for navn, verdi in vekter.items()}


def _min_maks_normaliser(verdier):
    """Skalerer til [0, 1], størst er best; like verdier får alle 0,5."""
    minimum = min(verdier)
    maksimum = max(verdier)

    if maksimum == minimum:
        return [0.5 for _ in verdier]

    return [(v - minimum) / (maksimum - minimum) for v in verdier]


def _beregn_vektet_score(godkjente_df, vekter):
    vekter_norm = _normaliser_vekter(vekter)

    score = pd.Series(0.0, index=godkjente_df.index)

    if "pris" in vekter_norm:
        delscore = _min_maks_normaliser((-godkjente_df["Pris [MNOK]"]).tolist())
        score = score + vekter_norm["pris"] * pd.Series(delscore, index=godkjente_df.index)

    if "hastighet" in vekter_norm:
        delscore = _min_maks_normaliser(godkjente_df["Vannhastighet [m/s]"].tolist())
        score = score + vekter_norm["hastighet"] * pd.Series(delscore, index=godkjente_df.index)

    if "skjaerspenning" in vekter_norm:
        delscore = _min_maks_normaliser(godkjente_df["Skjærspenning [Pa]"].tolist())
        score = score + vekter_norm["skjaerspenning"] * pd.Series(delscore, index=godkjente_df.index)

    return score, vekter_norm


def velg_anbefaling(godkjente_df, rangeringsvalg: RangeringsValg, parametere: BeregningsInput):
    """Returnerer anbefalt rad (eller None), begrunnelse og rangert tabell."""
    if godkjente_df.empty:
        return None, "Ingen rør oppfyller kravene, ingen anbefaling kan gis.", godkjente_df

    strategi = rangeringsvalg.strategi

    if strategi == "billigste_godkjent":
        rangert = godkjente_df.sort_values("Pris [MNOK]")
        anbefalt = rangert.iloc[0]

        begrunnelse = (
            f"{_ror_navn(anbefalt)} anbefales fordi røret oppfyller alle krav "
            f"og har lavest pris ({anbefalt['Pris [MNOK]']:.2f} MNOK) blant de godkjente alternativene."
        )
        return anbefalt, begrunnelse, rangert

    if strategi == "best_hydraulisk":
        df = godkjente_df.copy()
        df["_margin_totalt_tap"] = parametere.maks_totalt_tap_m - df["Total løftehøyde [m]"]
        df["_margin_skjaerspenning"] = df["Skjærspenning [Pa]"] - parametere.min_skjaerspenning_pa
        df["_margin_hastighet"] = df["Vannhastighet [m/s]"] - parametere.min_hastighet_m_s

        kolonne_for_mal = {
            "margin_totalt_tap": "_margin_totalt_tap",
            "margin_skjaerspenning": "_margin_skjaerspenning",
            "margin_hastighet": "_margin_hastighet",
        }
        sorteringskolonner = [kolonne_for_mal[mal] for mal in rangeringsvalg.hydraulisk_prioritet]

        rangert = df.sort_values(sorteringskolonner, ascending=[False] * len(sorteringskolonner))
        anbefalt = rangert.iloc[0]

        prioritetstekst = ", deretter ".join(
            _MARGIN_BESKRIVELSE[mal] for mal in rangeringsvalg.hydraulisk_prioritet
        )
        begrunnelse = (
            f"{_ror_navn(anbefalt)} anbefales som best hydraulisk alternativ, "
            f"rangert etter {prioritetstekst}."
        )
        return anbefalt, begrunnelse, rangert.drop(columns=list(kolonne_for_mal.values()))

    if strategi in ("balansert", "egendefinert_vekting"):
        vekter = BALANSERT_VEKTER if strategi == "balansert" else rangeringsvalg.vekter

        score, vekter_norm = _beregn_vektet_score(godkjente_df, vekter)

        df = godkjente_df.copy()
        df["_score"] = score
        rangert = df.sort_values("_score", ascending=False)
        anbefalt = rangert.iloc[0]

        vekttekst = ", ".join(
            f"{round(v * 100)}% {navn}" for navn, v in vekter_norm.items()
        )
        begrunnelse = (
            f"{_ror_navn(anbefalt)} anbefales med samlet score {anbefalt['_score']:.2f} "
            f"basert på {vekttekst}."
        )
        return anbefalt, begrunnelse, rangert.drop(columns=["_score"])

    raise ValueError(f"Ukjent rangeringsstrategi: {strategi}")
