"""
Plotfunksjoner. Mottar beregnede data/rørlister som argumenter - henter ikke
globale beregningsresultater selv. Lagrer alltid til fil; åpner et
interaktivt vindu bare når show_plot=True (standard False, se README).
"""

import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from config import OUTPUT_MAPPE

from hydraulikk import (
    beregn_hastighet,
    beregn_reynolds,
    colebrook_white,
    beregn_friksjonstap,
    beregn_singulaertap,
    beregn_skjaerspenning,
)

from modeller import BeregningsInput, BeregningsResultat, RorGrafValg


_graf_laas = Lock()


def hent_output_filnavn(filnavn, output_mappe=None):
    mappe = OUTPUT_MAPPE if output_mappe is None else output_mappe
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe / filnavn


def _lag_figur(figsize, show_plot):
    if show_plot:
        return plt.subplots(figsize=figsize)
    # Separate figurer uten GUI eller global pyplot-tilstand for API-kall.
    fig = Figure(figsize=figsize)
    return fig, fig.subplots()


def plott_pris_vs_skjaerspenning(resultat_df, parametere: BeregningsInput, show_plot=False, output_mappe=None, skriv_ut=True):
    if resultat_df.empty:
        return

    plot_df = resultat_df.copy()
    plot_df["Rør"] = (
        plot_df["DN"].astype(int).astype(str).radd("DN")
        + " "
        + plot_df["SDR"].astype(str)
    )

    godkjente_plot = plot_df[plot_df["Godkjent"] == True].copy()

    if not godkjente_plot.empty:
        vis_df = godkjente_plot.sort_values("Pris [MNOK]").reset_index(drop=True)
        hovedtittel = "Godkjente sjøledningsalternativer med lodd og oppdrift"
    else:
        vis_df = plot_df.sort_values("Pris [MNOK]").reset_index(drop=True)
        hovedtittel = "Ingen godkjente alternativer – viser alle beregnede rør"

    fig, ax = _lag_figur((13, 8), show_plot)
    fig.suptitle(hovedtittel, fontsize=16, fontweight="bold")

    farger = vis_df["Total løftehøyde [m]"]
    storrelse = vis_df["Vannhastighet [m/s]"] * 260

    sc = ax.scatter(
        vis_df["Pris [MNOK]"],
        vis_df["Skjærspenning [Pa]"],
        c=farger,
        s=storrelse,
        alpha=0.85,
        edgecolor="black"
    )

    for _, rad in vis_df.iterrows():
        ax.annotate(
            rad["Rør"],
            (rad["Pris [MNOK]"], rad["Skjærspenning [Pa]"]),
            xytext=(0, -12),
            textcoords="offset points",
            fontsize=8,
            ha="center",
            va="top"
        )

    ax.axhline(
        parametere.min_skjaerspenning_pa,
        linestyle="--",
        color="gray",
        linewidth=1.4,
        label=f"Krav skjærspenning ≥ {parametere.min_skjaerspenning_pa:.1f} Pa"
    )

    ax.set_title("Pris vs. skjærspenning")
    ax.set_xlabel("Materialpris [MNOK]")
    ax.set_ylabel("Skjærspenning [Pa]")
    ax.grid(True, alpha=0.3)

    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Total løftehøyde [m]")

    ax.legend(markerscale=0.65, scatterpoints=1)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])

    filnavn = hent_output_filnavn("sjoledning_pris_vs_skjaerspenning.png", output_mappe)
    fig.savefig(filnavn, dpi=220)

    if show_plot:
        plt.show()
        plt.close(fig)

    if not skriv_ut:
        return filnavn

    print()
    print("============================================================")
    print("GRAF LAGRET")
    print("============================================================")
    print(filnavn)
    return filnavn


def beregn_ledningskarakteristikk_data(DN, SDR, parametere: BeregningsInput, q_min=1, q_maks=400, antall=400):
    """
    Beregner data for ledningskarakteristikk.
    Returnerer Q, hastighet, total løftehøyde og skjærspenning.
    """
    d_i = (DN * (1.0 - 2.0 / SDR)) / 1000.0
    ruhet_m = parametere.ruhet_mm / 1000.0

    Q_ls = np.linspace(q_min, q_maks, antall)
    Q_m3s = Q_ls / 1000.0

    hastigheter = []
    totalt_tap = []
    skjaerspenninger = []

    for q in Q_m3s:
        v = beregn_hastighet(q, d_i)
        Re = beregn_reynolds(v, d_i, parametere.kinematisk_viskositet_m2_s)
        f = colebrook_white(Re, ruhet_m, d_i)

        Hf = beregn_friksjonstap(f, parametere.lengde_m, v, d_i, parametere.gravitasjon_m_s2)
        St = beregn_singulaertap(parametere.sum_singulaertapskoeffisienter, v, parametere.gravitasjon_m_s2)

        H_total = Hf + St
        tau = beregn_skjaerspenning(parametere.spesifikk_vekt_vann_n_m3, d_i, Hf, parametere.lengde_m)

        hastigheter.append(v)
        totalt_tap.append(H_total)
        skjaerspenninger.append(tau)

    return Q_ls, hastigheter, totalt_tap, skjaerspenninger


def lag_ledningskarakteristikk(DN, SDR, parametere: BeregningsInput, q_markeringer=None, show_plot=False, output_mappe=None, skriv_ut=True):
    if q_markeringer is None:
        q_markeringer = [150, 300]

    Q_ls, hastigheter, totalt_tap, skjaerspenninger = beregn_ledningskarakteristikk_data(
        DN=DN,
        SDR=SDR,
        parametere=parametere,
    )

    sdr_tekst = str(SDR).replace(".", ",")

    fig, ax = _lag_figur((14, 8), show_plot)

    ax.plot(
        Q_ls,
        totalt_tap,
        color="steelblue",
        linewidth=3,
        label=f"DN{int(DN)} SDR{sdr_tekst}"
    )

    for q_mark in q_markeringer:
        idx = np.argmin(np.abs(Q_ls - q_mark))

        loftehoyde = totalt_tap[idx]
        v = hastigheter[idx]
        tau = skjaerspenninger[idx]

        ax.plot(
            [q_mark, q_mark],
            [0, loftehoyde],
            linestyle="--",
            color="black",
            linewidth=1.5
        )

        ax.plot(
            [0, q_mark],
            [loftehoyde, loftehoyde],
            linestyle="--",
            color="black",
            linewidth=1.5
        )

        ax.scatter(
            q_mark,
            loftehoyde,
            color="black",
            s=45,
            zorder=5
        )

        ax.annotate(
            f"Q = {q_mark:.0f} l/s\n"
            f"Total løftehøyde = {loftehoyde:.2f} m\n"
            f"v = {v:.2f} m/s\n"
            f"τ = {tau:.2f} Pa",
            xy=(q_mark, loftehoyde),
            xytext=(-140, 35),
            textcoords="offset points",
            fontsize=10,
            bbox=dict(
                boxstyle="round,pad=0.4",
                facecolor="white",
                edgecolor="black",
                linewidth=1.2
            ),
            arrowprops=dict(
                arrowstyle="-",
                color="black",
                linewidth=1.2
            )
        )

    ax.set_xlim(0, 400)
    ax.set_ylim(bottom=0)

    ax.set_xlabel("Vannmengde Q [l/s]", fontsize=12)
    ax.set_ylabel("Total løftehøyde [m]", fontsize=12)

    ax.set_title(
        f"Ledningskarakteristikk for DN{int(DN)} SDR{sdr_tekst}\n"
        "Total løftehøyde som funksjon av vannføring",
        fontsize=15,
        fontweight="bold"
    )

    ax.minorticks_on()

    ax.grid(
        which="major",
        linestyle="-",
        linewidth=0.8,
        alpha=0.5
    )

    ax.grid(
        which="minor",
        linestyle="-",
        linewidth=0.4,
        alpha=0.2
    )

    ax.legend()

    fig.tight_layout()

    filnavn = hent_output_filnavn(
        f"ledningskarakteristikk_DN{int(DN)}_SDR{str(SDR).replace('.', '_')}.png",
        output_mappe,
    )

    fig.savefig(
        filnavn,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plot:
        plt.show()
        plt.close(fig)

    if not skriv_ut:
        return filnavn

    print()
    print("============================================================")
    print("GRAF LAGRET")
    print("============================================================")
    print(filnavn)
    return filnavn


def finn_krysning_q(Q_ls, verdier, grense):
    """
    Finner omtrent vannføring Q der en kurve krysser en gitt grense.
    Bruker lineær interpolasjon mellom to nærmeste punkter.

    Returnerer None hvis grensen ikke krysses.
    """
    Q_ls = np.asarray(Q_ls)
    verdier = np.asarray(verdier)

    # Hvis første punkt allerede er over grensen
    if verdier[0] >= grense:
        return Q_ls[0]

    for i in range(1, len(verdier)):
        y1 = verdier[i - 1]
        y2 = verdier[i]

        q1 = Q_ls[i - 1]
        q2 = Q_ls[i]

        # Sjekker om grensen ligger mellom y1 og y2
        if y1 < grense <= y2:
            if y2 == y1:
                return q2

            q_kryss = q1 + (grense - y1) * (q2 - q1) / (y2 - y1)
            return q_kryss

    return None


# Roterende sett med faste offset-retninger (i punkter) for annotasjonsbokser.
# Gir en enkel, automatisk kollisjonsreduksjon: hver ny boks (tau- og
# løftehøyde-annotasjon for hvert rør) får neste offset i rotasjonen, i
# stedet for håndplasserte posisjoner per DN/SDR. Ikke garantert
# overlappfritt for svært mange rør samtidig - se §11.3 i prosjektplanen
# for videre arbeid med interaktiv/kollisjonsfri plassering.
_OFFSET_ROTASJON = [
    (-180, 25), (25, 75), (-90, 115), (-10, 115),
    (-150, 75), (-70, -75), (-290, 125), (-80, -160),
]


def _hent_automatisk_offset(rekkefolge_indeks):
    return _OFFSET_ROTASJON[rekkefolge_indeks % len(_OFFSET_ROTASJON)]


def plott_samlet_ledningskarakteristikk(ror_liste, parametere: BeregningsInput, q_maks=450, show_plot=False, output_mappe=None, skriv_ut=True):
    """
    Lager samlet ledningskarakteristikk for en liste med rør.

    ror_liste: liste med {"DN": float, "SDR": float} - ingen faste
    DN/SDR-verdier eller annotasjonsposisjoner er hardkodet. Kall f.eks.
    med de godkjente rørene fra en beregning.

    Hele kurven vises svakt.

    Gyldig område mellom:
    - τ >= min_skjaerspenning_pa
    - total løftehøyde <= maks_totalt_tap_m

    vises med tykkere linje.
    """
    if not ror_liste:
        if skriv_ut:
            print("Ingen rør å plotte i plott_samlet_ledningskarakteristikk - hopper over.")
        return

    min_skjaerspenning = parametere.min_skjaerspenning_pa
    maks_totalt_tap = parametere.maks_totalt_tap_m

    fig, ax = _lag_figur((16, 8), show_plot)

    grense_data = []

    for indeks, ror in enumerate(ror_liste):
        DN = ror["DN"]
        SDR = ror["SDR"]
        navn = f"DN{int(DN)} SDR{str(SDR).replace('.', ',')}"

        offset_tau = _hent_automatisk_offset(indeks * 2)
        offset_loftehoyde = _hent_automatisk_offset(indeks * 2 + 1)

        Q_ls, hastigheter, totalt_tap, skjaerspenninger = beregn_ledningskarakteristikk_data(
            DN=DN,
            SDR=SDR,
            parametere=parametere,
            q_min=1,
            q_maks=q_maks,
            antall=q_maks
        )

        Q_ls = np.asarray(Q_ls)
        totalt_tap = np.asarray(totalt_tap)
        skjaerspenninger = np.asarray(skjaerspenninger)
        hastigheter = np.asarray(hastigheter)

        # ----------------------------------------------------
        # Finn grensepunkter
        # ----------------------------------------------------

        q_tau_2 = finn_krysning_q(
            Q_ls=Q_ls,
            verdier=skjaerspenninger,
            grense=min_skjaerspenning
        )

        q_loftehoyde_maks = finn_krysning_q(
            Q_ls=Q_ls,
            verdier=totalt_tap,
            grense=maks_totalt_tap
        )

        # Interpoler verdier ved tau = 2 Pa
        if q_tau_2 is not None:
            loftehoyde_ved_tau_2 = np.interp(q_tau_2, Q_ls, totalt_tap)
            v_ved_tau_2 = np.interp(q_tau_2, Q_ls, hastigheter)
        else:
            loftehoyde_ved_tau_2 = None
            v_ved_tau_2 = None

        # Interpoler verdier ved maksimal total løftehøyde
        if q_loftehoyde_maks is not None:
            tau_ved_loftehoyde_maks = np.interp(q_loftehoyde_maks, Q_ls, skjaerspenninger)
            v_ved_loftehoyde_maks = np.interp(q_loftehoyde_maks, Q_ls, hastigheter)
        else:
            tau_ved_loftehoyde_maks = None
            v_ved_loftehoyde_maks = None

        grense_data.append(
            {
                "Rør": navn,
                f"Q ved tau = {min_skjaerspenning:.1f} Pa [l/s]": q_tau_2,
                f"Total løftehøyde ved tau = {min_skjaerspenning:.1f} Pa [m]": loftehoyde_ved_tau_2,
                f"Q ved total løftehøyde = {maks_totalt_tap:.0f} m [l/s]": q_loftehoyde_maks,
                f"Tau ved total løftehøyde = {maks_totalt_tap:.0f} m [Pa]": tau_ved_loftehoyde_maks,
            }
        )

        # ----------------------------------------------------
        # Plot hele kurven svakt
        # ----------------------------------------------------

        linje, = ax.plot(
            Q_ls,
            totalt_tap,
            linewidth=1.5,
            alpha=0.25,
            label=f"{navn} - hele kurven"
        )

        farge = linje.get_color()

        # ----------------------------------------------------
        # Plot gyldig område med tykkere linje
        # ----------------------------------------------------

        if (
            q_tau_2 is not None
            and q_loftehoyde_maks is not None
            and q_tau_2 < q_loftehoyde_maks
        ):
            gyldig_maske = (
                (Q_ls >= q_tau_2)
                & (Q_ls <= q_loftehoyde_maks)
            )

            ax.plot(
                Q_ls[gyldig_maske],
                totalt_tap[gyldig_maske],
                color=farge,
                linewidth=4.5,
                alpha=1.0,
                label=f"{navn} - gyldig område"
            )

        # ----------------------------------------------------
        # Marker punkt der skjærspenning = 2 Pa
        # ----------------------------------------------------

        if q_tau_2 is not None:
            ax.axvline(
                q_tau_2,
                linestyle="--",
                color=farge,
                linewidth=1.2,
                alpha=0.55
            )

            ax.scatter(
                q_tau_2,
                loftehoyde_ved_tau_2,
                color=farge,
                s=70,
                zorder=5
            )

        # ----------------------------------------------------
        # Marker punkt der total løftehøyde = grense
        # ----------------------------------------------------

        if q_loftehoyde_maks is not None:
            ax.scatter(
                q_loftehoyde_maks,
                maks_totalt_tap,
                color=farge,
                s=90,
                marker="x",
                linewidths=2.2,
                zorder=5
            )

        # ----------------------------------------------------
        # Tekstbokser nær punktene
        # ----------------------------------------------------

        if q_tau_2 is not None:
            tekst_tau = (
                f"{navn}\n"
                f"Ved τ = {min_skjaerspenning:.1f} Pa:\n"
                f"Q ≈ {q_tau_2:.0f} l/s\n"
                f"Total løftehøyde ≈ {loftehoyde_ved_tau_2:.2f} m\n"
                f"v ≈ {v_ved_tau_2:.2f} m/s"
            )

            ax.annotate(
                tekst_tau,
                xy=(q_tau_2, loftehoyde_ved_tau_2),
                xytext=offset_tau,
                textcoords="offset points",
                fontsize=9,
                ha="left",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.4",
                    facecolor="white",
                    edgecolor=farge,
                    linewidth=1.4,
                    alpha=0.95
                ),
                arrowprops=dict(
                    arrowstyle="-",
                    color=farge,
                    linewidth=1.2,
                    alpha=0.8
                )
            )

        if q_loftehoyde_maks is not None:
            tekst_loftehoyde = (
                f"{navn}\n"
                f"Ved total løftehøyde = {maks_totalt_tap:.0f} m:\n"
                f"Q ≈ {q_loftehoyde_maks:.0f} l/s\n"
                f"τ ≈ {tau_ved_loftehoyde_maks:.2f} Pa\n"
                f"v ≈ {v_ved_loftehoyde_maks:.2f} m/s"
            )

            ax.annotate(
                tekst_loftehoyde,
                xy=(q_loftehoyde_maks, maks_totalt_tap),
                xytext=offset_loftehoyde,
                textcoords="offset points",
                fontsize=9,
                ha="left",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.4",
                    facecolor="white",
                    edgecolor=farge,
                    linewidth=1.4,
                    linestyle="--",
                    alpha=0.95
                ),
                arrowprops=dict(
                    arrowstyle="-",
                    color=farge,
                    linewidth=1.2,
                    alpha=0.8
                )
            )

    # --------------------------------------------------------
    # Øvre grense for total løftehøyde
    # --------------------------------------------------------

    ax.axhline(
        maks_totalt_tap,
        linestyle="--",
        color="black",
        linewidth=1.8,
        label=f"Maks total løftehøyde = {maks_totalt_tap:.0f} m"
    )

    ax.text(
        8,
        maks_totalt_tap + 1.5,
        f"Øvre grense: {maks_totalt_tap:.0f} m",
        fontsize=10,
        color="black"
    )

    # --------------------------------------------------------
    # Akser og layout
    # --------------------------------------------------------

    ax.set_xlim(0, q_maks)
    ax.set_ylim(bottom=0)

    ax.set_xlabel("Vannmengde Q [l/s]", fontsize=12)
    ax.set_ylabel("Total løftehøyde [m]", fontsize=12)

    ax.set_title(
        f"Samlet ledningskarakteristikk for {len(ror_liste)} rør\n"
        f"Tykk linje viser området der τ ≥ {min_skjaerspenning:.1f} Pa "
        f"og total løftehøyde ≤ {maks_totalt_tap:.0f} m",
        fontsize=15,
        fontweight="bold"
    )

    ax.minorticks_on()

    ax.grid(
        which="major",
        linestyle="-",
        linewidth=0.8,
        alpha=0.45
    )

    ax.grid(
        which="minor",
        linestyle="-",
        linewidth=0.4,
        alpha=0.2
    )

    ax.legend(fontsize=9, loc="upper left")

    fig.tight_layout()

    filnavn = hent_output_filnavn(
        f"samlet_ledningskarakteristikk_{len(ror_liste)}_ror.png",
        output_mappe,
    )

    fig.savefig(
        filnavn,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plot:
        plt.show()
        plt.close(fig)

    if not skriv_ut:
        return filnavn

    print()
    print("============================================================")
    print("SAMLET GRAF LAGRET")
    print("============================================================")
    print(filnavn)

    print()
    print("Grenseverdier:")

    for rad in grense_data:
        q_tau = rad[f"Q ved tau = {min_skjaerspenning:.1f} Pa [l/s]"]
        loftehoyde_tau = rad[f"Total løftehøyde ved tau = {min_skjaerspenning:.1f} Pa [m]"]
        q_loftehoyde = rad[f"Q ved total løftehøyde = {maks_totalt_tap:.0f} m [l/s]"]
        tau_loftehoyde = rad[f"Tau ved total løftehøyde = {maks_totalt_tap:.0f} m [Pa]"]

        q_tau_tekst = f"{q_tau:.1f} l/s" if q_tau is not None else "ikke funnet"
        loftehoyde_tau_tekst = f"{loftehoyde_tau:.2f} m" if loftehoyde_tau is not None else "ikke funnet"
        q_loftehoyde_tekst = f"{q_loftehoyde:.1f} l/s" if q_loftehoyde is not None else "ikke funnet"
        tau_loftehoyde_tekst = f"{tau_loftehoyde:.2f} Pa" if tau_loftehoyde is not None else "ikke funnet"

        print(
            f"{rad['Rør']}: "
            f"Q ved τ = {min_skjaerspenning:.1f} Pa ≈ {q_tau_tekst}, "
            f"total løftehøyde da ≈ {loftehoyde_tau_tekst}, "
            f"Q ved total løftehøyde = {maks_totalt_tap:.0f} m ≈ {q_loftehoyde_tekst}, "
            f"τ da ≈ {tau_loftehoyde_tekst}"
        )

    return filnavn


def lag_grafer_for_ui(
    resultat: BeregningsResultat,
    valgte_ror: list[RorGrafValg] | None = None,
    vis_prisgraf: bool = True,
):
    """Gjenbruk CLI-grafene og returner PNG-bilder for denne beregningen."""
    ror_til_plotting = resultat.godkjente
    if valgte_ror is not None:
        valgte = {(r.dn_od_mm, r.sdr) for r in valgte_ror}
        godkjente = {(r.dn_od_mm, r.sdr) for r in resultat.godkjente}
        if not valgte.issubset(godkjente):
            raise ValueError("Bare godkjente rør fra denne beregningen kan velges til ledningskarakteristikk.")
        ror_til_plotting = [r for r in resultat.godkjente if (r.dn_od_mm, r.sdr) in valgte]

    plot_df = pd.DataFrame([
        {
            "DN": ror.dn_od_mm,
            "SDR": ror.sdr_navn,
            "Godkjent": ror.godkjent,
            "Pris [MNOK]": ror.pris_mnok,
            "Vannhastighet [m/s]": ror.vannhastighet_m_s,
            "Total løftehøyde [m]": ror.totalt_tap_m,
            "Skjærspenning [Pa]": ror.skjaerspenning_pa,
        }
        for ror in resultat.alle_resultater
    ])
    ror_liste = [{"DN": r.dn_od_mm, "SDR": r.sdr} for r in ror_til_plotting]

    # Matplotlib er ikke trådsikkert. Hvert kall har egne filer som slettes
    # etter at bildene er lest, slik at samtidige beregninger ikke blandes.
    with _graf_laas:
        OUTPUT_MAPPE.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=OUTPUT_MAPPE, prefix="ui_grafer_") as mappe:
            output_mappe = Path(mappe)
            grafer = []

            def legg_til(tittel, filnavn):
                if filnavn is not None:
                    bilde = base64.b64encode(filnavn.read_bytes()).decode("ascii")
                    grafer.append({"tittel": tittel, "bilde": f"data:image/png;base64,{bilde}"})

            if vis_prisgraf:
                legg_til("Pris mot skjærspenning", plott_pris_vs_skjaerspenning(
                    plot_df, resultat.input, output_mappe=output_mappe, skriv_ut=False,
                ))
            if ror_liste:
                legg_til("Samlet ledningskarakteristikk", plott_samlet_ledningskarakteristikk(
                    ror_liste, resultat.input, output_mappe=output_mappe, skriv_ut=False,
                ))
            for ror in ror_til_plotting:
                legg_til(f"Ledningskarakteristikk DN{ror.dn_od_mm:g} {ror.sdr_navn}",
                         lag_ledningskarakteristikk(
                             ror.dn_od_mm, ror.sdr, resultat.input,
                             output_mappe=output_mappe, skriv_ut=False,
                         ))

            return grafer
