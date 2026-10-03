"""Lokal kjøring med prosjektverdier, tabell-eksport og plott."""

from beregninger import beregn_alle_alternativer, finn_godkjente
from config import CSV_FIL
from data_io import (
    les_ror_csv,
    sjekk_nodvendige_kolonner,
    finn_sdr_liste_fra_katalog,
    filtrer_sdr_liste,
    sjekk_ingen_duplikate_dn,
    valider_rorkatalog,
)
from eksport import eksporter_oppdrift_lodd_csv, eksporter_oppdrift_lodd_excel
from modeller import BeregningsInput, RangeringsValg
from plotting import (
    plott_pris_vs_skjaerspenning,
    lag_ledningskarakteristikk,
    plott_samlet_ledningskarakteristikk,
)
from rangering import velg_anbefaling


def skriv_resultater(resultat_df, parametere: BeregningsInput, rangeringsvalg: RangeringsValg):
    if resultat_df.empty:
        print("Ingen rør ble beregnet for de gitte inndataene.")
        return

    print("Antall beregnede alternativer:", len(resultat_df))
    print()

    godkjente_df = finn_godkjente(resultat_df)

    visningskolonner = [
        "DN",
        "SDR",
        "Indre diameter [mm]",
        "Vannhastighet [m/s]",
        "Total løftehøyde [m]",
        "Skjærspenning [Pa]",
        "Pris [MNOK]",
    ]

    if godkjente_df.empty:
        print("Ingen rør er godkjent for de gitte kravene.")
        print()
        print("Alle beregnede alternativer, med avviksårsaker:")
        print()

        for _, rad in resultat_df.iterrows():
            print(f"  {rad['DN']:.0f} {rad['SDR']}: " + "; ".join(rad["Avviksårsaker"]))

    else:
        print("Godkjente rør:")
        print()

        print(godkjente_df[visningskolonner].to_string(index=False))

        _, begrunnelse, _ = velg_anbefaling(godkjente_df, rangeringsvalg, parametere)

        print()
        print(f"Anbefaling ({rangeringsvalg.strategi}):")
        print()
        print(begrunnelse)


def main():
    # Endre disse verdiene for prosjektet som skal beregnes.
    QDIM_L_S = 300.0
    LENGDE_M = 10250.0
    TILLATTE_SDR = [13.6, 17.0]

    parametere = BeregningsInput(
        qdim_l_s=QDIM_L_S,
        lengde_m=LENGDE_M,
        tillatte_sdr=TILLATTE_SDR,
    )

    rangeringsvalg = RangeringsValg(strategi="billigste_godkjent")

    df = les_ror_csv(CSV_FIL)

    sjekk_ingen_duplikate_dn(df)

    sdr_liste_katalog = finn_sdr_liste_fra_katalog(df)
    sdr_liste = filtrer_sdr_liste(sdr_liste_katalog, parametere.tillatte_sdr)

    sjekk_nodvendige_kolonner(
        df=df,
        sdr_liste=sdr_liste
    )

    avvik = valider_rorkatalog(df, sdr_liste)
    if avvik:
        print("Advarsel: mistenkte feil i rørkatalogen (raden brukes ikke i beregningen):")
        for rad in avvik:
            print(f"  DN{rad['DN']:.0f} {rad['SDR-navn']}: {rad['problem']}")
        print()

    resultat_df = beregn_alle_alternativer(
        df=df,
        sdr_liste=sdr_liste,
        parametere=parametere,
    )

    skriv_resultater(resultat_df, parametere=parametere, rangeringsvalg=rangeringsvalg)

    eksporter_oppdrift_lodd_csv(
        df=df,
        sdr_liste=sdr_liste,
        parametere=parametere,
    )

    eksporter_oppdrift_lodd_excel(
        df=df,
        sdr_liste=sdr_liste,
        parametere=parametere,
    )

    plott_pris_vs_skjaerspenning(resultat_df, parametere=parametere)

    godkjente_df = finn_godkjente(resultat_df)

    ror_a_plotte = [
        {"DN": rad["DN"], "SDR": rad["SDR-verdi"]}
        for _, rad in godkjente_df.iterrows()
    ]

    for ror in ror_a_plotte:
        lag_ledningskarakteristikk(
            DN=ror["DN"],
            SDR=ror["SDR"],
            parametere=parametere,
        )

    plott_samlet_ledningskarakteristikk(ror_a_plotte, parametere=parametere)


if __name__ == "__main__":
    main()
