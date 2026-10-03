"""Beregner og eksporterer oppdrift/lodd-tabeller til CSV og Excel."""

import pandas as pd

from config import OUTPUT_MAPPE
from oppdrift_lodd import beregn_excel_lodd
from data_io import er_veggtykkelse_rimelig
from modeller import BeregningsInput


def lag_oppdrift_lodd_tabell(df, sdr_liste, parametere: BeregningsInput):
    """Lager oppdrift/lodd-tabell for katalogens gyldige DN/SDR-kombinasjoner."""

    rader = []

    for _, rad in df.iterrows():
        DN = rad["DN/OD"]

        if pd.isna(DN) or DN <= 0:
            continue

        for sdr_info in sdr_liste:
            SDR = sdr_info["SDR"]
            SDR_NAVN = sdr_info["SDR-navn"]

            veggtykkelse = rad[sdr_info["veggtykkelse_kolonne"]]
            kg_per_m = rad[sdr_info["kg_per_m_kolonne"]]

            if pd.isna(veggtykkelse) or pd.isna(kg_per_m):
                continue

            if veggtykkelse <= 0 or kg_per_m <= 0:
                continue

            if not er_veggtykkelse_rimelig(DN, SDR, veggtykkelse):
                continue

            beregnet = beregn_excel_lodd(
                DN_mm=DN,
                SDR=SDR,
                kg_per_m_csv=kg_per_m,
                parametere=parametere,
            )

            rad_resultat = {
                "DN": DN,
                "SDR": SDR_NAVN,
                "SDR-verdi": SDR,
                "Veggtykkelse CSV [mm]": veggtykkelse,
            }

            rad_resultat.update(beregnet)

            rader.append(rad_resultat)

    return pd.DataFrame(rader)


def eksporter_oppdrift_lodd_csv(df, sdr_liste, parametere: BeregningsInput, filnavn="oppdrift_lodd_resultater.csv"):
    """Eksporterer oppdrift/lodd-beregninger til resultater/ som norsk CSV."""

    OUTPUT_MAPPE.mkdir(parents=True, exist_ok=True)

    resultat_df = lag_oppdrift_lodd_tabell(df, sdr_liste, parametere)

    filsti = OUTPUT_MAPPE / filnavn

    resultat_df.to_csv(
        filsti,
        sep=";",
        decimal=",",
        index=False,
        encoding="utf-8-sig"
    )

    print(f"Oppdrift/lodd-resultater lagret til: {filsti}")

    return resultat_df


def eksporter_oppdrift_lodd_excel(df, sdr_liste, parametere: BeregningsInput, filnavn="oppdrift_lodd_resultater.xlsx"):
    """
    Eksporterer alle oppdrift/lodd-beregninger til Excel.
    Merk: Dette lager et Excel-ark med ferdig beregnede verdier,
    ikke levende Excel-formler.
    """

    OUTPUT_MAPPE.mkdir(parents=True, exist_ok=True)

    resultat_df = lag_oppdrift_lodd_tabell(df, sdr_liste, parametere)

    filsti = OUTPUT_MAPPE / filnavn

    resultat_df.to_excel(
        filsti,
        index=False,
        engine="openpyxl"
    )

    print(f"Oppdrift/lodd-resultater lagret til Excel: {filsti}")

    return resultat_df
