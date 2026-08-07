import math

from modeller import BeregningsInput


def beregn_excel_lodd(DN_mm, SDR, kg_per_m_csv, parametere: BeregningsInput):
    """
    Beregner loddvekt på samme måte som Excel-arket.

    DN_mm = ytre diameter i mm.
    SDR = SDR-verdi, for eksempel 17 eller 13.6.
    kg_per_m_csv = rørvekt fra CSV, brukes til kostnad.
    parametere = prosjektets BeregningsInput (tettheter, priser, lengder).
    """
    d_y = DN_mm / 1000.0
    d_i = d_y * (1.0 - 2.0 / SDR)
    d_i_mm = d_i * 1000.0

    vannfylling = 1.0 - parametere.luftfylling_andel

    vekt_pe_teoretisk = (
        parametere.rho_pe_kg_m3
        * math.pi / 4.0
        * (d_y**2 - d_i**2)
    )

    vekt_avlop = (
        parametere.rho_avlop_kg_m3
        * math.pi / 4.0
        * d_i**2
        * vannfylling
    )

    oppdrift = (
        parametere.rho_saltvann_kg_m3
        * math.pi / 4.0
        * d_y**2
    )

    netto_oppdrift = (
        oppdrift
        - vekt_pe_teoretisk
        - vekt_avlop
    )

    netto_oppdrift = max(0.0, netto_oppdrift)

    vekt_lodd = (
        netto_oppdrift
        * parametere.rho_lodd_kg_m3
        / (parametere.rho_lodd_kg_m3 - parametere.rho_saltvann_kg_m3)
    )

    rorkostnad_kr_m = kg_per_m_csv * parametere.pris_ror_kr_per_kg
    lodd_kr_m = vekt_lodd * parametere.pris_lodd_kr_per_kg
    legging_sjo_kr_m = kg_per_m_csv * parametere.pris_legging_sjo_kr_per_kg

    kostnad_sjo_kr_m = (
        rorkostnad_kr_m
        + lodd_kr_m
        + legging_sjo_kr_m
    )

    kostnad_land_kr_m = rorkostnad_kr_m

    kostnad_sjo_kr = kostnad_sjo_kr_m * parametere.hent_lengde_sjo_m()
    kostnad_land_kr = kostnad_land_kr_m * parametere.lengde_land_m

    total_kostnad_kr = kostnad_sjo_kr + kostnad_land_kr

    belastning_luft_excel = (
        vekt_pe_teoretisk
        + vekt_avlop
        + vekt_lodd
    )

    belastning_luft_katalogvekt = (
        kg_per_m_csv
        + vekt_avlop
        + vekt_lodd
    )

    return {
        "Indre diameter [mm]": d_i_mm,
        "Vekt PE teoretisk [kg/m]": vekt_pe_teoretisk,
        "Vekt rør CSV [kg/m]": kg_per_m_csv,
        "Vekt avløp [kg/m]": vekt_avlop,
        "Oppdrift [kg/m]": oppdrift,
        "Netto oppdrift [kg/m]": netto_oppdrift,
        "Vekt lodd [kg/m]": vekt_lodd,

        "Rørkostnad [kr/m]": rorkostnad_kr_m,
        "Lodd kr/m": lodd_kr_m,
        "Leggekostnad sjø [kr/m]": legging_sjo_kr_m,
        "Kostnad sjø [kr/m]": kostnad_sjo_kr_m,
        "Kostnad land [kr/m]": kostnad_land_kr_m,

        "Kostnad sjø [kr]": kostnad_sjo_kr,
        "Kostnad land [kr]": kostnad_land_kr,
        "Sum kostnad [kr]": total_kostnad_kr,
        "Sum kostnad [MNOK]": total_kostnad_kr / 1_000_000.0,

        "Belastning luft Excel [kg/m]": belastning_luft_excel,
        "Belastning luft katalogvekt [kg/m]": belastning_luft_katalogvekt,
    }