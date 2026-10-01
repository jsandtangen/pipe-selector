"""Bygger strukturert rapportdata fra eksisterende beregningsresultater."""

from modeller import BeregningsResultat, RapportData, RorResultat, RorValg


def _kopier_ror(ror: RorResultat | None) -> RorResultat | None:
    if ror is None:
        return None
    return ror.model_copy(deep=True)


def _hent_sammenlignede_alternativer(
    resultat: BeregningsResultat,
    valgte_ror: list[RorValg] | None,
) -> list[RorResultat]:
    if valgte_ror is None:
        return []

    godkjente = {(ror.dn_od_mm, ror.sdr): ror for ror in resultat.godkjente}
    sammenlignede = []
    sett = set()

    for valg in valgte_ror:
        nokkel = (valg.dn_od_mm, valg.sdr)
        if nokkel not in godkjente:
            raise ValueError(
                "Bare godkjente rør fra denne beregningen kan velges til rapportdata."
            )
        if nokkel not in sett:
            sammenlignede.append(godkjente[nokkel].model_copy(deep=True))
            sett.add(nokkel)

    return sammenlignede


def lag_rapportdata(
    resultat: BeregningsResultat,
    valgte_ror: list[RorValg] | None = None,
) -> RapportData:
    """
    Lager rapportgrunnlag uten nye hydrauliske beregninger eller rangering.

    Sammenlignede alternativer er bare de rørene brukeren eksplisitt har valgt
    fra de godkjente resultatene i denne beregningen.
    """
    return RapportData(
        input=resultat.input.model_copy(deep=True),
        rangering=resultat.rangering.model_copy(deep=True),
        antall_beregnet=len(resultat.alle_resultater),
        antall_godkjent=len(resultat.godkjente),
        antall_underkjent=len(resultat.underkjente),
        anbefalt=_kopier_ror(resultat.anbefalt),
        anbefalingsbegrunnelse=resultat.anbefalingsbegrunnelse,
        sammenlignede_alternativer=_hent_sammenlignede_alternativer(
            resultat, valgte_ror
        ),
    )
