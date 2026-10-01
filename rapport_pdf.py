"""Presenterer RapportData som en teknisk PDF, uten nye faglige beregninger."""

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modeller import RapportData, RorResultat
from plotting import lag_sammenligningsgraf_for_rapport


def _tall(verdi: float, desimaler: int = 2) -> str:
    return f"{verdi:,.{desimaler}f}".replace(",", " ").replace(".", ",")


def _rornavn(ror: RorResultat) -> str:
    return f"DN/OD {_tall(ror.dn_od_mm, 0)} SDR {ror.sdr:g}".replace(".", ",")


def _prosjektgrunnlag(rapport: RapportData) -> list[list[str]]:
    p = rapport.input
    rader = [["Prosjektgrunnlag", "Verdi"],
        ["Dimensjonerende vannmengde", f"{_tall(p.qdim_l_s)} l/s"],
        ["Total ledningslengde", f"{_tall(p.lengde_m)} m"],
        ["Lengde i sjø", f"{_tall(p.hent_lengde_sjo_m())} m"],
        ["Lengde på land", f"{_tall(p.lengde_land_m)} m"],
        ["Tillatte SDR-klasser", "; ".join(f"{s:g}".replace(".", ",") for s in p.tillatte_sdr)],
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


def _beregningsparametere(rapport: RapportData) -> list[list[str]]:
    p = rapport.input
    return [["Beregningsparameter", "Verdi"],
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


def _kriteriestatus(rapport: RapportData) -> list[list[str]]:
    a = rapport.anbefalt
    p = rapport.input
    # Godkjent betyr at samtlige eksisterende kriterier er bestått.
    # Ved manglende/underkjent anbefaling har vi ingen individuell kravstatus.
    status = "Ikke vurdert" if a is None else "Oppfylt" if a.godkjent else "Se avvik"

    def verdi(felt, enhet, desimaler=2):
        return "-" if a is None else f"{_tall(getattr(a, felt), desimaler)} {enhet}".strip()

    return [["Kriterium", "Resultat", "Krav", "Status"],
        ["Vannhastighet", verdi("vannhastighet_m_s", "m/s", 3), f"Min. {_tall(p.min_hastighet_m_s)} m/s", status],
        ["Skjærspenning", verdi("skjaerspenning_pa", "Pa", 3), f"Min. {_tall(p.min_skjaerspenning_pa)} Pa", status],
        ["Totalt tap", verdi("totalt_tap_m", "m"), f"Maks. {_tall(p.maks_totalt_tap_m)} m", status],
        ["SDR-trykk", verdi("trykk_fra_totalt_tap_bar", "bar"), f"Maks. {verdi('tillatt_trykk_bar', 'bar')}" if a else "-", status],
        ["Utvendig diameter", verdi("dn_od_mm", "mm", 0), f"Maks. {verdi('maks_utvendig_diameter_mm', 'mm', 1)}" if a else "-", status],
        ["SDR-klasse", verdi("sdr", "", 1), "Godkjent SDR-klasse", status],
    ]


def lag_rapport_pdf(rapport: RapportData, generert_tid: datetime | None = None) -> bytes:
    """Returnerer en PDF i minnet. Fast generert_tid gir en reproduserbar rapport."""
    generert_tid = generert_tid or datetime.now().astimezone()
    stiler = getSampleStyleSheet()
    stiler["BodyText"].fontSize = 9.5
    stiler["BodyText"].leading = 14
    stiler["BodyText"].spaceAfter = 6
    stiler["Heading2"].fontSize = 13
    stiler["Heading2"].spaceBefore = 18
    stiler["Heading2"].spaceAfter = 10
    stiler.add(ParagraphStyle("Rapporttittel", fontName="Helvetica-Bold", fontSize=22, leading=27, spaceAfter=12))
    stiler.add(ParagraphStyle("AnbefaltLosning", fontName="Helvetica-Bold", fontSize=18, leading=23, spaceAfter=10))
    stiler.add(ParagraphStyle("Nokkeltall", fontName="Helvetica", fontSize=12, leading=20))
    stiler.add(ParagraphStyle("Tabell", parent=stiler["BodyText"], fontSize=9, leading=12, spaceAfter=0))
    bredde = A4[0] - 40 * mm

    def tekst(verdi):
        return Paragraph(escape(str(verdi)), stiler["BodyText"])

    def tabell(rader, bredder):
        t = Table([[Paragraph(escape(str(celle)), stiler["Tabell"]) for celle in rad] for rad in rader],
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

    a = rapport.anbefalt
    innhold = [Paragraph("PipeSelector", stiler["Heading3"]),
               Paragraph("Hydraulisk dimensjoneringsrapport", stiler["Rapporttittel"]),
               tekst(f"Generert: {generert_tid.strftime('%d.%m.%Y %H:%M:%S %Z')}")]
    innhold.append(Paragraph("1. Resultatsammendrag", stiler["Heading2"]))
    losning = f"Anbefalt løsning: {_rornavn(a)}" if a else "Ingen anbefalt løsning"
    innhold.append(Paragraph(escape(losning), stiler["AnbefaltLosning"]))
    nokkeltall = [
        ("Dimensjonerende vannmengde", f"{_tall(rapport.input.qdim_l_s)} l/s"),
        ("Vannhastighet", f"{_tall(a.vannhastighet_m_s, 3)} m/s" if a else "-"),
        ("Skjærspenning", f"{_tall(a.skjaerspenning_pa, 3)} Pa" if a else "-"),
        ("Totalt tap", f"{_tall(a.totalt_tap_m)} m" if a else "-"),
        ("Kostnad", f"{_tall(a.pris_mnok)} MNOK" if a else "-"),
        ("Status", "Ingen anbefaling" if a is None else "Godkjent" if a.godkjent else "Underkjent"),
    ]
    celler = [Paragraph(f'<font size="9" color="#555555">{escape(navn)}</font><br/><b>{escape(verdi)}</b>',
                        stiler["Nokkeltall"]) for navn, verdi in nokkeltall]
    sammendrag = Table([celler[:3], celler[3:]], colWidths=[bredde / 3] * 3, hAlign="LEFT")
    sammendrag.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.grey),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    innhold += [sammendrag, Spacer(1, 4 * mm)]
    if rapport.anbefalingsbegrunnelse:
        innhold.append(tekst(rapport.anbefalingsbegrunnelse))
    elif a is None:
        innhold.append(tekst("Det foreligger ingen anbefaling for denne beregningen. Kravgrenser og beregningsstatus er oppgitt videre i rapporten."))
    innhold.append(tekst(f"{rapport.antall_beregnet} alternativer er vurdert; "
                         f"{rapport.antall_godkjent} er godkjent og {rapport.antall_underkjent} er underkjent."))
    innhold += [Paragraph("2. Prosjektgrunnlag", stiler["Heading2"]),
                tekst("Dimensjoneringen gjelder oppgitt vannmengde og ledningslengde. "
                      "Godkjente alternativer rangeres etter strategien nedenfor."),
                tabell(_prosjektgrunnlag(rapport), [bredde * 0.50, bredde * 0.50]),
                Spacer(1, 4 * mm),
                tekst("Totalt tap omfatter friksjons- og singulærtap. Statisk løftehøyde er ikke modellert."),
                PageBreak(), Paragraph("3. Anbefalt løsning: beregnede verdier", stiler["Heading2"])]
    if a is None:
        innhold.append(tekst("Ingen anbefaling foreligger for denne beregningen."))
    else:
        innhold.append(tekst(f"Tabellen utdyper det beregnede tapet, trykkapasiteten og ballastbehovet for {_rornavn(a)}."))
        innhold += [tabell([
            ["Beregnet verdi", "Resultat"],
            ["Innvendig diameter", f"{_tall(a.indre_diameter_mm, 1)} mm"],
            ["Friksjonstap", f"{_tall(a.friksjonstap_m)} m"],
            ["Singulærtap", f"{_tall(a.singulaertap_m)} m"],
            ["Trykk fra totalt tap / tillatt SDR-trykk", f"{_tall(a.trykk_fra_totalt_tap_bar)} / {_tall(a.tillatt_trykk_bar)} bar"],
            ["Maksimal utvendig diameter ved trykket", f"{_tall(a.maks_utvendig_diameter_mm, 1)} mm"],
            ["Vekt PE, teoretisk", f"{_tall(a.vekt_pe_teoretisk_kg_m)} kg/m"],
            ["Netto oppdrift", f"{_tall(a.netto_oppdrift_kg_m)} kg/m"],
            ["Vekt lodd", f"{_tall(a.vekt_lodd_kg_m)} kg/m"],
        ], [bredde * 0.60, bredde * 0.40])]

    if a is None:
        kravtekst = "Ingen anbefalt løsning foreligger. Sjekklisten viser kravgrensene, uten en vurdering av et anbefalt rør."
    elif a.godkjent:
        kravtekst = "Anbefalt løsning er godkjent i kravkontrollen. Sjekklisten viser beregnede verdier og tilhørende kravgrenser."
    else:
        kravtekst = "Sjekklisten viser beregnede verdier og tilgjengelige kravgrenser. Se avviksårsakene for krav som ikke er oppfylt."
    innhold += [Paragraph("4. Kravkontroll", stiler["Heading2"]),
                tekst(kravtekst),
                tabell(_kriteriestatus(rapport), [bredde * andel for andel in [0.28, 0.23, 0.29, 0.20]])]
    if a is not None:
        for avvik in a.avviksarsaker:
            innhold.append(tekst(avvik))

    sammenligning = [Paragraph("5. Sammenligning av valgte alternativer", stiler["Heading2"])]
    valgte = rapport.sammenlignede_alternativer
    if not valgte:
        sammenligning.append(tekst("Ingen alternativer er valgt til sammenligning."))
    else:
        sammenligning.append(tekst("Tabellen viser de valgte alternativene ved samme dimensjonerende vannmengde. "
                                  "Verdiene gjør det mulig å sammenligne hydrauliske resultater, ballastbehov og kostnad. "
                                  "Anbefalt løsning er merket når den inngår i utvalget."))
        rader = [["Rør", "Vurdering", "Hastighet [m/s]",
                  "Skjærspenning [Pa]", "Totalt tap [m]", "Lodd [kg/m]", "Pris [MNOK]"]]
        for r in valgte:
            anbefalt = a is not None and (r.dn_od_mm, r.sdr) == (a.dn_od_mm, a.sdr)
            rader.append([_rornavn(r), "Anbefalt" if anbefalt else "-",
                          _tall(r.vannhastighet_m_s, 3), _tall(r.skjaerspenning_pa, 3),
                          _tall(r.totalt_tap_m), _tall(r.vekt_lodd_kg_m), _tall(r.pris_mnok)])
        t = tabell(rader, [bredde * andel for andel in [0.22, 0.14, 0.12, 0.16, 0.12, 0.12, 0.12]])
        for i, r in enumerate(valgte, 1):
            if a is not None and (r.dn_od_mm, r.sdr) == (a.dn_od_mm, a.sdr):
                t.setStyle(TableStyle([("BACKGROUND", (0, i), (-1, i), colors.HexColor("#e8f0ea"))]))
        sammenligning.append(t)
    if len(valgte) <= 8:
        innhold.append(KeepTogether(sammenligning))
    else:
        innhold.extend(sammenligning)

    if rapport.faglig_vurdering:
        vurdering = [Paragraph("Faglig vurdering", stiler["Heading2"]),
                     tekst("Vurderingen er automatisk formulert fra rapportens beregningsdata.")]
        vurdering.extend(tekst(avsnitt) for avsnitt in rapport.faglig_vurdering.split("\n\n") if avsnitt.strip())
        innhold.append(KeepTogether(vurdering))

    if valgte:
        # Begrens antall etiketter per figur slik at store utvalg fortsatt er lesbare.
        for start in range(0, len(valgte), 10):
            utvalg = valgte[start:start + 10]
            for grafpar, tittel in [("hydraulikk", "Vannhastighet og skjærspenning"),
                                    ("tap_og_pris", "Totalt tap og kostnad")]:
                if not rapport.faglig_vurdering or start or grafpar == "tap_og_pris":
                    innhold.append(PageBreak())
                figurinnhold = [Paragraph("6. Sammenligningsgrafer", stiler["Heading2"]),
                                Paragraph(tittel, stiler["Heading3"]),
                                tekst("Figurene viser de valgte alternativene ved dimensjonerende vannmengde. "
                                      "Anbefalt løsning er merket i etiketten og med grønn stolpe når den er valgt.")]
                if len(valgte) > 10:
                    figurinnhold.append(tekst(f"Alternativ {start + 1}-{start + len(utvalg)} av {len(valgte)} i valgt rekkefølge."))
                bilde = lag_sammenligningsgraf_for_rapport(utvalg, a, grafpar=grafpar)
                graf = Image(BytesIO(bilde))
                graf.drawHeight *= bredde / graf.drawWidth
                graf.drawWidth = bredde
                figurinnhold += [Spacer(1, 3 * mm), graf]
                innhold.append(KeepTogether(figurinnhold))
    else:
        innhold += [Paragraph("6. Sammenligningsgrafer", stiler["Heading2"]),
                    tekst("Ingen sammenligningsgrafer er tatt med, siden ingen alternativer er valgt.")]

    innhold += [Paragraph("7. Forbehold", stiler["Heading2"]),
                tekst("Rapporten er automatisk generert fra beregningsresultater i PipeSelector og er ment som beslutningsstøtte. "
                      "Resultatene må vurderes opp mot prosjektspesifikke forhold og erstatter ikke prosjekteringsansvar."),
                PageBreak(), Paragraph("Vedlegg A. Beregningsparametere", stiler["Heading2"]),
                tekst("Parametrene nedenfor dokumenterer grunnlaget for hydraulikk-, oppdrifts- og kostnadsberegningene."),
                tabell(_beregningsparametere(rapport), [bredde * 0.55, bredde * 0.45])]

    with BytesIO() as buffer:
        dokument = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm,
                                    leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=22 * mm,
                                    title="PipeSelector - Hydraulisk dimensjoneringsrapport", author="PipeSelector",
                                    invariant=1)
        dokument.build(innhold, onFirstPage=sidefot, onLaterPages=sidefot)
        return buffer.getvalue()
