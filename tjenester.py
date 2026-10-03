"""Koordinerer katalogvalidering, beregning og rangering for API-et."""

import pandas as pd

from beregninger import beregn_alle_alternativer, finn_godkjente
from data_io import (
    filtrer_sdr_liste,
    finn_sdr_liste_fra_katalog,
    sjekk_ingen_duplikate_dn,
    sjekk_nodvendige_kolonner,
)
from modeller import BeregningsInput, BeregningsResultat, RangeringsValg, RorResultat
from rangering import velg_anbefaling


def _rad_til_ror_resultat(rad: pd.Series) -> RorResultat:
    return RorResultat(
        dn_od_mm=float(rad["DN"]),
        sdr=float(rad["SDR-verdi"]),
        sdr_navn=str(rad["SDR"]),
        indre_diameter_mm=float(rad["Indre diameter [mm]"]),
        vannhastighet_m_s=float(rad["Vannhastighet [m/s]"]),
        reynolds=float(rad["Reynolds [-]"]),
        friksjonsfaktor=float(rad["Friksjonsfaktor f [-]"]),
        friksjonstap_m=float(rad["Friksjonstap Hf [m]"]),
        singulaertap_m=float(rad["Singulærtap St [m]"]),
        totalt_tap_m=float(rad["Total løftehøyde [m]"]),
        skjaerspenning_pa=float(rad["Skjærspenning [Pa]"]),
        trykk_fra_totalt_tap_bar=float(rad["Trykk fra totalt tap [bar]"]),
        tillatt_trykk_bar=float(rad["Tillatt trykk SDR [bar]"]),
        maks_utvendig_diameter_mm=float(rad["Maks utvendig diameter [mm]"]),
        vekt_pe_teoretisk_kg_m=float(rad["Vekt PE teoretisk [kg/m]"]),
        vekt_avlop_kg_m=float(rad["Vekt avløp [kg/m]"]),
        oppdrift_kg_m=float(rad["Oppdrift [kg/m]"]),
        netto_oppdrift_kg_m=float(rad["Netto oppdrift [kg/m]"]),
        vekt_lodd_kg_m=float(rad["Vekt lodd pr. m [kg/m]"]),
        pris_kr=float(rad["Sum kostnad [kr]"]),
        pris_mnok=float(rad["Pris [MNOK]"]),
        godkjent=bool(rad["Godkjent"]),
        avviksarsaker=list(rad["Avviksårsaker"]),
    )


def beregn_pumpeledning(
    parametere: BeregningsInput,
    rorkatalog: pd.DataFrame,
    rangeringsvalg: RangeringsValg,
) -> BeregningsResultat:
    """Beregner alternativer; ugyldig katalog eller SDR-valg gir ValueError."""
    if rorkatalog.empty:
        raise ValueError("Rørkatalogen er tom - ingen rør å beregne.")

    sjekk_ingen_duplikate_dn(rorkatalog)

    sdr_liste_katalog = finn_sdr_liste_fra_katalog(rorkatalog)
    sdr_liste = filtrer_sdr_liste(sdr_liste_katalog, parametere.tillatte_sdr)

    sjekk_nodvendige_kolonner(df=rorkatalog, sdr_liste=sdr_liste)

    resultat_df = beregn_alle_alternativer(
        df=rorkatalog, sdr_liste=sdr_liste, parametere=parametere
    )

    if resultat_df.empty:
        raise ValueError(
            "Ingen gyldige DN/SDR-kombinasjoner ble funnet i rørkatalogen "
            "for de valgte SDR-klassene."
        )

    godkjente_df = finn_godkjente(resultat_df)
    underkjente_df = resultat_df[~resultat_df["Godkjent"]]

    alle_resultater = [_rad_til_ror_resultat(rad) for _, rad in resultat_df.iterrows()]
    godkjente = [_rad_til_ror_resultat(rad) for _, rad in godkjente_df.iterrows()]
    underkjente = [_rad_til_ror_resultat(rad) for _, rad in underkjente_df.iterrows()]

    anbefalt_rad, begrunnelse, _ = velg_anbefaling(godkjente_df, rangeringsvalg, parametere)
    anbefalt = _rad_til_ror_resultat(anbefalt_rad) if anbefalt_rad is not None else None

    return BeregningsResultat(
        input=parametere,
        rangering=rangeringsvalg,
        alle_resultater=alle_resultater,
        godkjente=godkjente,
        underkjente=underkjente,
        anbefalt=anbefalt,
        anbefalingsbegrunnelse=begrunnelse,
    )
