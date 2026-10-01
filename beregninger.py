"""
Beregner alle DN/SDR-alternativer i en rørkatalog og kontrollerer de
absolutte kravene (hastighet, skjærspenning, totalt tap). Rangering blant
de godkjente alternativene skjer i rangering.py, ikke her.
"""

import pandas as pd

from hydraulikk import (
    beregn_hastighet,
    beregn_reynolds,
    colebrook_white,
    beregn_friksjonstap,
    beregn_singulaertap,
    beregn_skjaerspenning,
    beregn_tillatt_trykk_bar,
    beregn_trykk_fra_lofte,
    beregn_maks_utvendig_diameter_mm,
)

from oppdrift_lodd import beregn_excel_lodd
from data_io import er_veggtykkelse_rimelig
from modeller import BeregningsInput


def beregn_alle_alternativer(df, sdr_liste, parametere: BeregningsInput):
    resultater = []

    q_dim_m3_s = parametere.qdim_l_s / 1000.0
    ruhet_m = parametere.ruhet_mm / 1000.0

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

            excel_data = beregn_excel_lodd(
                DN_mm=DN,
                SDR=SDR,
                kg_per_m_csv=kg_per_m,
                parametere=parametere,
            )

            d_i_mm = excel_data["Indre diameter [mm]"]
            d_i = d_i_mm / 1000.0

            v = beregn_hastighet(q_dim_m3_s, d_i)
            Re = beregn_reynolds(v, d_i, parametere.kinematisk_viskositet_m2_s)
            f = colebrook_white(Re, ruhet_m, d_i)

            Hf = beregn_friksjonstap(f, parametere.lengde_m, v, d_i, parametere.gravitasjon_m_s2)
            St = beregn_singulaertap(parametere.sum_singulaertapskoeffisienter, v, parametere.gravitasjon_m_s2)

            H_total = Hf + St

            tau = beregn_skjaerspenning(parametere.spesifikk_vekt_vann_n_m3, d_i, Hf, parametere.lengde_m)

            tillatt_trykk_bar = beregn_tillatt_trykk_bar(SDR, parametere.dimensjonerende_ringspenning_mpa)
            trykk_totalt_tap_bar = beregn_trykk_fra_lofte(H_total, parametere.spesifikk_vekt_vann_n_m3)
            trykk_design_mpa = trykk_totalt_tap_bar / 10.0
            maks_utvendig_diameter_mm = beregn_maks_utvendig_diameter_mm(trykk_design_mpa)

            oppfyller_skjaerspenning = tau >= parametere.min_skjaerspenning_pa
            oppfyller_hastighet = v >= parametere.min_hastighet_m_s
            oppfyller_tap = H_total <= parametere.maks_totalt_tap_m
            oppfyller_trykklasse = trykk_totalt_tap_bar <= tillatt_trykk_bar
            oppfyller_maks_diameter = DN <= maks_utvendig_diameter_mm

            godkjent = (
                oppfyller_skjaerspenning
                and oppfyller_hastighet
                and oppfyller_tap
                and oppfyller_trykklasse
                and oppfyller_maks_diameter
            )

            avviksarsaker = []

            if not oppfyller_hastighet:
                avviksarsaker.append(
                    f"vannhastigheten ({v:.2f} m/s) er lavere enn minstekravet ({parametere.min_hastighet_m_s:.2f} m/s)"
                )

            if not oppfyller_skjaerspenning:
                avviksarsaker.append(
                    f"skjærspenningen ({tau:.2f} Pa) er lavere enn minstekravet ({parametere.min_skjaerspenning_pa:.2f} Pa)"
                )

            if not oppfyller_tap:
                avviksarsaker.append(
                    f"totalt tap ({H_total:.2f} m) overstiger maksgrensen ({parametere.maks_totalt_tap_m:.2f} m)"
                )

            if not oppfyller_trykklasse:
                avviksarsaker.append(
                    f"trykket fra totalt tap ({trykk_totalt_tap_bar:.2f} bar) overstiger hva SDR {SDR} tåler "
                    f"({tillatt_trykk_bar:.2f} bar, basert på p = 2σ/(SDR-1) med σ = "
                    f"{parametere.dimensjonerende_ringspenning_mpa:.1f} MPa)"
                )

            if not oppfyller_maks_diameter:
                avviksarsaker.append(
                    f"utvendig diameter ({DN:.0f} mm) overstiger maksimal diameter "
                    f"({maks_utvendig_diameter_mm:.0f} mm) ved dimensjonerende trykk "
                    f"({trykk_design_mpa:.3f} MPa)"
                )

            resultater.append({
                "DN": DN,
                "SDR": SDR_NAVN,
                "SDR-verdi": SDR,
                "Veggtykkelse CSV [mm]": veggtykkelse,
                "Indre diameter [mm]": d_i_mm,

                "Vannmengde [l/s]": parametere.qdim_l_s,
                "Lengde sjø [m]": parametere.hent_lengde_sjo_m(),
                "Lengde land [m]": parametere.lengde_land_m,
                "Total lengde [m]": parametere.lengde_m,

                "Kg/m CSV": kg_per_m,
                "Vekt PE teoretisk [kg/m]": excel_data["Vekt PE teoretisk [kg/m]"],
                "Vekt avløp [kg/m]": excel_data["Vekt avløp [kg/m]"],
                "Oppdrift [kg/m]": excel_data["Oppdrift [kg/m]"],
                "Netto oppdrift [kg/m]": excel_data["Netto oppdrift [kg/m]"],
                "Vekt lodd pr. m [kg/m]": excel_data["Vekt lodd [kg/m]"],

                "Rørkostnad [kr/m]": excel_data["Rørkostnad [kr/m]"],
                "Lodd kr/m": excel_data["Lodd kr/m"],
                "Leggekostnad sjø [kr/m]": excel_data["Leggekostnad sjø [kr/m]"],
                "Kostnad sjø [kr/m]": excel_data["Kostnad sjø [kr/m]"],

                "Kostnad sjø [kr]": excel_data["Kostnad sjø [kr]"],
                "Kostnad land [kr]": excel_data["Kostnad land [kr]"],
                "Sum kostnad [kr]": excel_data["Sum kostnad [kr]"],
                "Pris [MNOK]": excel_data["Sum kostnad [MNOK]"],

                "Belastning luft Excel [kg/m]": excel_data["Belastning luft Excel [kg/m]"],
                "Belastning luft katalogvekt [kg/m]": excel_data["Belastning luft katalogvekt [kg/m]"],

                "Vannhastighet [m/s]": v,
                "Reynolds [-]": Re,
                "Friksjonsfaktor f [-]": f,
                "Friksjonstap Hf [m]": Hf,
                "Singulærtap St [m]": St,
                "Total løftehøyde [m]": H_total,
                "Skjærspenning [Pa]": tau,
                "Trykk fra totalt tap [bar]": trykk_totalt_tap_bar,
                "Tillatt trykk SDR [bar]": tillatt_trykk_bar,
                "Dimensjonerende trykk [MPa]": trykk_design_mpa,
                "Maks utvendig diameter [mm]": maks_utvendig_diameter_mm,

                "Krav hastighet >= 1 m/s": oppfyller_hastighet,
                "Krav skjærspenning >= 2 Pa": oppfyller_skjaerspenning,
                f"Krav total løftehøyde <= {parametere.maks_totalt_tap_m:.0f} m": oppfyller_tap,
                "Krav trykklasse (SDR)": oppfyller_trykklasse,
                "Krav maksimal utvendig diameter": oppfyller_maks_diameter,
                "Godkjent": godkjent,
                "Avviksårsaker": avviksarsaker,
            })

    return pd.DataFrame(resultater)


def finn_godkjente(resultat_df):
    """
    Returnerer godkjente alternativer sortert etter pris.
    """
    if resultat_df.empty:
        return resultat_df

    godkjente_df = resultat_df[resultat_df["Godkjent"] == True].copy()
    return godkjente_df.sort_values("Pris [MNOK]")