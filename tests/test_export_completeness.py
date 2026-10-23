"""A progressively disclosed webpage must still produce a complete report."""

import base64
from io import BytesIO

import pytest
from PIL import Image

import rapport_pdf
from config import CSV_FIL
from data_io import les_ror_csv
from grafeksport import GrafEksport
from modeller import BeregningsInput, RangeringsValg, RorValg
from rapport import lag_rapportdata
from tjenester import beregn_pumpeledning
from visualisering import lag_referansepunkter_for_rapport


@pytest.mark.parametrize("antall", [1, 5])
def test_rapport_beholder_referanser_og_krav_uten_synlige_grafdetaljer(antall, monkeypatch):
    resultat = beregn_pumpeledning(
        BeregningsInput(qdim_l_s=300, lengde_m=10250, tillatte_sdr=[13.6, 17]),
        les_ror_csv(CSV_FIL), RangeringsValg(strategi="billigste_godkjent"),
    )
    ror = resultat.godkjente[:antall]
    rapport = lag_rapportdata(resultat, [RorValg(dn_od_mm=r.dn_od_mm, sdr=r.sdr) for r in ror])
    # An intentionally blank image models a view with curves/details hidden.
    # Report completeness must come from calculation data, not image content.
    buffer = BytesIO()
    Image.new("RGB", (900, 600), "white").save(buffer, format="PNG")
    image = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    ids = ["pris", "samlet", *(f"ror-{r.dn_od_mm:g}-{r.sdr:g}" for r in ror)]
    exports = [GrafEksport(id=id_, tittel=id_, bilde=image) for id_ in ids]
    tables = []
    original_table = rapport_pdf.Table

    def capture(rows, *args, **kwargs):
        tables.append([[cell.getPlainText() for cell in row] for row in rows])
        return original_table(rows, *args, **kwargs)

    monkeypatch.setattr(rapport_pdf, "Table", capture)
    pdf = rapport_pdf.lag_rapport_pdf(rapport, grafer=exports)
    assert pdf.startswith(b"%PDF-")
    references = next(t for t in tables if t[0] == ["Rør", "Referanse", "Q [l/s]", "Tap [m]", "v [m/s]", "τ [Pa]"])
    expected = [
        [name, label, rapport_pdf._tall(q, 1), rapport_pdf._tall(h),
         rapport_pdf._tall(v, 3), rapport_pdf._tall(tau, 3)]
        for name, label, q, h, v, tau in lag_referansepunkter_for_rapport(ror, resultat.input)
    ]
    assert references[1:] == expected
    # Both fixed individual references and boundary intersections must survive.
    assert sum(row[1] == "Referanse" for row in references[1:]) == antall * 2
    assert any(row[1].startswith("τ =") for row in references[1:])
    assert any(row[1].startswith("H =") for row in references[1:])
    requirements = next(t for t in tables if t[0] == ["Kriterium", "Resultat", "Krav", "Status"])
    assert next(row for row in requirements if row[0] == "Skjærspenning")[2] == f"Min. {rapport_pdf._tall(resultat.input.min_skjaerspenning_pa)} Pa"
    assert next(row for row in requirements if row[0] == "Totalt tap")[2] == f"Maks. {rapport_pdf._tall(resultat.input.maks_totalt_tap_m)} m"
