"""Presenterer RapportData som en teknisk PDF, uten nye faglige beregninger."""

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modeller import RapportData, RorResultat
from plotting import lag_sammenligningsgraf_for_rapport


def _tall(verdi: float, desimaler: int = 2) -> str:
    return f"{verdi:,.{desimaler}f}".replace(",", " ").replace(".", ",")


def _rornavn(ror: RorResultat) -> str:
    return f"DN/OD {_tall(ror.dn_od_mm, 0)} / SDR {ror.sdr:g}".replace(".", ",")


def _forutsetninger(rapport: RapportData) -> list[list[str]]:
    p = rapport.input
    rader = [["Forutsetning", "Verdi"],
        ["Dimensjonerende vannmengde", f"{_tall(p.qdim_l_s)} l/s"],
        ["Total ledningslengde", f"{_tall(p.lengde_m)} m"],
        ["Lengde i sjø", f"{_tall(p.hent_lengde_sjo_m())} m"],
        ["Lengde på land", f"{_tall(p.lengde_land_m)} m"],
        ["Tillatte SDR-klasser", "; ".join(f"{s:g}".replace(".", ",") for s in p.tillatte_sdr)],
        ["Ruhet", f"{_tall(p.ruhet_mm, 3)} mm"],
        ["Kinematisk viskositet", f"{_tall(p.kinematisk_viskositet_m2_s, 9)} m²/s"],
        ["Sum singulærtapskoeffisienter", _tall(p.sum_singulaertapskoeffisienter)],
        ["Minimum vannhastighet", f"{_tall(p.min_hastighet_m_s)} m/s"],
        ["Minimum skjærspenning", f"{_tall(p.min_skjaerspenning_pa)} Pa"],
        ["Maksimalt totalt tap", f"{_tall(p.maks_totalt_tap_m)} m"],
        ["Dimensjonerende ringspenning", f"{_tall(p.dimensjonerende_ringspenning_mpa)} MPa"],
        ["Rørpris", f"{_tall(p.pris_ror_kr_per_kg)} kr/kg"],
        ["Loddpris", f"{_tall(p.pris_lodd_kr_per_kg)} kr/kg"],
        ["Leggekostnad sjø", f"{_tall(p.pris_legging_sjo_kr_per_kg)} kr/kg"],
        ["Luftfylling, andel", _tall(p.luftfylling_andel)],
        ["Tetthet avløp / PE", f"{_tall(p.rho_avlop_kg_m3)} / {_tall(p.rho_pe_kg_m3)} kg/m³"],
        ["Tetthet saltvann / lodd", f"{_tall(p.rho_saltvann_kg_m3)} / {_tall(p.rho_lodd_kg_m3)} kg/m³"],
        ["Tyngdeakselerasjon", f"{_tall(p.gravitasjon_m_s2)} m/s²"],
        ["Spesifikk vekt vann", f"{_tall(p.spesifikk_vekt_vann_n_m3)} N/m³"],
    ]
    strategier = {
        "billigste_godkjent": "Billigste godkjente",
        "best_hydraulisk": "Best hydraulisk",
        "balansert": "Balansert (50 % pris, 25 % hastighet, 25 % skjærspenning)",
        "egendefinert_vekting": "Egendefinert vekting",
    }
    rader.append(["Rangeringsstrategi", strategier[rapport.rangering.strategi]])
    if rapport.rangering.strategi == "best_hydraulisk":
        navn = {"margin_totalt_tap": "Margin til maksimalt totalt tap",
                "margin_skjaerspenning": "Margin over minimum skjærspenning",
                "margin_hastighet": "Margin over minimum vannhastighet"}
        rader.append(["Hydraulisk prioritet", "; ".join(
            f"{i}. {navn[mal]}" for i, mal in enumerate(rapport.rangering.hydraulisk_prioritet, 1)
        )])
    if rapport.rangering.strategi == "egendefinert_vekting":
        navn = {"pris": "Pris", "hastighet": "Hastighet", "skjaerspenning": "Skjærspenning"}
        rader.append(["Oppgitte rangeringsvekter", "; ".join(
            f"{navn[k]}: {_tall(v)}" for k, v in rapport.rangering.vekter.items()
        )])
    return rader


def lag_rapport_pdf(rapport: RapportData, generert_tid: datetime | None = None) -> bytes:
    """Returnerer en PDF i minnet. Fast generert_tid gir en reproduserbar rapport."""
    generert_tid = generert_tid or datetime.now().astimezone()
    stiler = getSampleStyleSheet()
    stiler["BodyText"].fontSize = 9
    stiler["BodyText"].leading = 12
    stiler["Heading2"].fontSize = 13
    stiler["Heading2"].spaceBefore = 12
    stiler["Heading2"].spaceAfter = 8
    bredde = A4[0] - 40 * mm

    def tekst(verdi):
        return Paragraph(escape(str(verdi)), stiler["BodyText"])

    def tabell(rader, bredder):
        t = Table([[tekst(celle) for celle in rad] for rad in rader],
                  colWidths=bredder, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.grey),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    def sidefot(canvas, dokument):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(20 * mm, 13 * mm, "PipeSelector | Hydraulisk dimensjoneringsrapport")
        canvas.drawRightString(A4[0] - 20 * mm, 13 * mm, f"Side {dokument.page}")
        canvas.restoreState()

    innhold = [Paragraph("PipeSelector", stiler["Title"]),
               Paragraph("Hydraulisk dimensjoneringsrapport", stiler["Heading1"]),
               tekst(f"Generert: {generert_tid.strftime('%d.%m.%Y %H:%M:%S %Z')}")]
    innhold += [Paragraph("1. Beregningsforutsetninger", stiler["Heading2"]),
                tabell(_forutsetninger(rapport), [bredde * 0.55, bredde * 0.45]),
                Spacer(1, 6 * mm),
                tekst("Totalt tap omfatter friksjons- og singulærtap. Statisk løftehøyde er ikke modellert."),
                PageBreak(), Paragraph("2. Anbefalt rør", stiler["Heading2"])]
    a = rapport.anbefalt
    if a is None:
        innhold.append(tekst("Ingen anbefaling foreligger for denne beregningen."))
    else:
        innhold.append(Paragraph(escape(_rornavn(a)), stiler["Heading3"]))
        if rapport.anbefalingsbegrunnelse:
            innhold.append(tekst(rapport.anbefalingsbegrunnelse))
        innhold += [Spacer(1, 3 * mm), tabell([
            ["Beregnet verdi", "Resultat"],
            ["Innvendig diameter", f"{_tall(a.indre_diameter_mm, 1)} mm"],
            ["Vannhastighet", f"{_tall(a.vannhastighet_m_s, 3)} m/s"],
            ["Skjærspenning", f"{_tall(a.skjaerspenning_pa, 3)} Pa"],
            ["Friksjonstap", f"{_tall(a.friksjonstap_m)} m"],
            ["Singulærtap", f"{_tall(a.singulaertap_m)} m"],
            ["Totalt tap", f"{_tall(a.totalt_tap_m)} m"],
            ["Trykk fra totalt tap / tillatt SDR-trykk", f"{_tall(a.trykk_fra_totalt_tap_bar)} / {_tall(a.tillatt_trykk_bar)} bar"],
            ["Maksimal utvendig diameter ved trykket", f"{_tall(a.maks_utvendig_diameter_mm, 1)} mm"],
            ["Vekt PE, teoretisk", f"{_tall(a.vekt_pe_teoretisk_kg_m)} kg/m"],
            ["Netto oppdrift", f"{_tall(a.netto_oppdrift_kg_m)} kg/m"],
            ["Vekt lodd", f"{_tall(a.vekt_lodd_kg_m)} kg/m"],
            ["Kostnad", f"{_tall(a.pris_mnok)} MNOK"],
        ], [bredde * 0.60, bredde * 0.40])]

    innhold.append(Paragraph("3. Sammenligning av valgte alternativer", stiler["Heading2"]))
    valgte = rapport.sammenlignede_alternativer
    if not valgte:
        innhold.append(tekst("Ingen alternativer er valgt til sammenligning."))
    else:
        rader = [["DN/OD / SDR", "Indre diameter [mm]", "Hastighet [m/s]",
                  "Skjærspenning [Pa]", "Totalt tap [m]", "Lodd [kg/m]", "Pris [MNOK]"]]
        for r in valgte:
            rader.append([_rornavn(r), _tall(r.indre_diameter_mm, 1),
                          _tall(r.vannhastighet_m_s, 3), _tall(r.skjaerspenning_pa, 3),
                          _tall(r.totalt_tap_m), _tall(r.vekt_lodd_kg_m), _tall(r.pris_mnok)])
        t = tabell(rader, [bredde * andel for andel in [0.22, 0.12, 0.13, 0.16, 0.13, 0.12, 0.12]])
        for i, r in enumerate(valgte, 1):
            if a is not None and (r.dn_od_mm, r.sdr) == (a.dn_od_mm, a.sdr):
                t.setStyle(TableStyle([("BACKGROUND", (0, i), (-1, i), colors.HexColor("#e8f0ea"))]))
        innhold += [t, Spacer(1, 3 * mm), tekst("Anbefalt rør er markert med grønn bakgrunn når det er valgt.")]

    innhold += [PageBreak(), Paragraph("4. Grafer", stiler["Heading2"])]
    if not valgte:
        innhold.append(tekst("Ingen sammenligningsgraf: ingen alternativer er valgt."))
    else:
        innhold.append(tekst("Lagrede beregningsverdier ved dimensjonerende vannmengde. Grønn stolpe markerer anbefalt rør når det er valgt."))
        # Begrens antall etiketter per figur slik at store utvalg fortsatt er lesbare.
        for start in range(0, len(valgte), 10):
            if start:
                innhold.append(PageBreak())
                innhold.append(Paragraph("4. Grafer (forts.)", stiler["Heading2"]))
            utvalg = valgte[start:start + 10]
            bilde = lag_sammenligningsgraf_for_rapport(utvalg, a)
            graf = Image(BytesIO(bilde))
            graf.drawHeight *= bredde / graf.drawWidth
            graf.drawWidth = bredde
            innhold += [Spacer(1, 3 * mm), graf]

    innhold.append(Paragraph("5. Beregningsstatus / kriterier", stiler["Heading2"]))
    innhold.append(tekst(f"{rapport.antall_beregnet} alternativer beregnet, "
                         f"{rapport.antall_godkjent} godkjent, {rapport.antall_underkjent} underkjent."))
    if a is not None:
        innhold.append(tekst(f"Anbefalt rør: {'Godkjent' if a.godkjent else 'Underkjent'}."))
        for avvik in a.avviksarsaker:
            innhold.append(tekst(avvik))
    innhold.append(tekst("Kravkontrollen omfatter minimum vannhastighet, minimum skjærspenning, "
                         "maksimalt totalt tap, SDR-trykkapasitet og maksimal utvendig diameter ved beregnet trykk. "
                         "Status er hentet fra beregningen."))
    innhold += [Paragraph("6. Forbehold", stiler["Heading2"]),
                tekst("Rapporten er automatisk generert fra beregningsresultater i PipeSelector og er ment som beslutningsstøtte. "
                      "Resultatene må vurderes opp mot prosjektspesifikke forhold og erstatter ikke prosjekteringsansvar.")]

    with BytesIO() as buffer:
        dokument = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm,
                                    leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=22 * mm,
                                    title="PipeSelector - Hydraulisk dimensjoneringsrapport", author="PipeSelector",
                                    invariant=1)
        dokument.build(innhold, onFirstPage=sidefot, onLaterPages=sidefot)
        return buffer.getvalue()
