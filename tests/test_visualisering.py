import base64
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import api
import rapport_pdf
from config import CSV_FIL
from data_io import les_ror_csv
from grafeksport import GrafEksport
from modeller import BeregningsInput, RangeringsValg, RorGrafValg
from plotting import beregn_ledningskarakteristikk_data, finn_krysning_q
from rapport import lag_rapportdata
from tjenester import beregn_pumpeledning
from visualisering import lag_interaktive_grafer, lag_referansepunkter_for_rapport


@pytest.fixture
def resultat():
    return beregn_pumpeledning(
        BeregningsInput(qdim_l_s=300, lengde_m=10250, tillatte_sdr=[13.6, 17]),
        les_ror_csv(CSV_FIL), RangeringsValg(strategi="billigste_godkjent"),
    )


def png():
    with BytesIO() as buffer:
        # Deliberately asymmetric image stands in for manually moved annotations.
        image = Image.new("RGB", (900, 600), "white")
        image.paste("blue", (600, 40, 850, 130))
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


@pytest.mark.parametrize("antall", [1, 3, 5])
def test_interaktive_kurver_er_identiske_med_opprinnelige_data(resultat, antall):
    before = resultat.model_dump()
    ror = resultat.godkjente[:antall]
    valg = [RorGrafValg(dn_od_mm=r.dn_od_mm, sdr=r.sdr) for r in ror]
    grafer = lag_interaktive_grafer(resultat, valg)
    assert len(grafer) == antall + 2
    samlet = grafer[1]
    assert len(samlet["layout"]["annotations"]) >= antall
    for r in ror:
        navn = f"DN{r.dn_od_mm:g} {r.sdr_navn}"
        trace = next(t for t in samlet["data"] if t["name"] == navn and t.get("showlegend") is not False)
        q, v, h, tau = beregn_ledningskarakteristikk_data(r.dn_od_mm, r.sdr, resultat.input, q_maks=450, antall=450)
        np.testing.assert_array_equal(trace["x"], q)
        np.testing.assert_array_equal(trace["y"], h)
        np.testing.assert_array_equal(trace["customdata"], np.column_stack([v, tau]))
        qt = finn_krysning_q(q, tau, resultat.input.min_skjaerspenning_pa)
        qh = finn_krysning_q(q, h, resultat.input.maks_totalt_tap_m)
        valid = [t for t in samlet["data"] if t["name"] == navn and t.get("line", {}).get("width") == 4.5]
        if qt is not None and qh is not None and qt < qh:
            mask = (q >= qt) & (q <= qh)
            np.testing.assert_array_equal(valid[0]["x"], np.asarray(q)[mask])
        else:
            assert not valid
        annotations = [a for a in samlet["layout"]["annotations"] if a["name"] == trace["legendgroup"]]
        assert [a["x"] for a in annotations] == [x for x in (qt, qh) if x is not None]
    assert resultat.model_dump() == before


def test_ukjent_ror_avvises_og_tomt_utvalg_virker(resultat):
    with pytest.raises(ValueError):
        lag_interaktive_grafer(resultat, [RorGrafValg(dn_od_mm=99999, sdr=17)])
    assert [g["id"] for g in lag_interaktive_grafer(resultat, [])] == ["pris"]


@pytest.mark.parametrize("antall", [1, 3, 5])
def test_rapportreferanser_beholder_alle_markorverdier(resultat, antall):
    ror = resultat.godkjente[:antall]
    grafer = lag_interaktive_grafer(resultat, [RorGrafValg(dn_od_mm=r.dn_od_mm, sdr=r.sdr) for r in ror], False)
    forventet = []
    for graf in grafer:
        for trace in graf["data"]:
            if trace["mode"] == "markers":
                forventet.append((trace["name"], trace["text"][0], trace["x"][0], trace["y"][0], *trace["customdata"][0]))
    referanser = lag_referansepunkter_for_rapport(ror, resultat.input)
    assert sorted(tuple(r) for r in referanser) == sorted(forventet)


def test_pdf_bruker_eksakt_innsendt_bilde_uten_ny_graf(resultat, monkeypatch):
    rapport = lag_rapportdata(resultat, [RorGrafValg(dn_od_mm=560, sdr=17)])
    eksport = GrafEksport(id="samlet", tittel="Tilpasset graf", bilde=png())
    original = rapport_pdf.Image
    bilder = []

    def image(buffer):
        bilder.append(buffer.getvalue())
        return original(buffer)

    def uventet(*args):
        pytest.fail("Frontend-eksport skal ikke erstattes med ny standardgraf")

    monkeypatch.setattr(rapport_pdf, "Image", image)
    monkeypatch.setattr(rapport_pdf, "lag_ledningsgrafer_for_rapport", uventet)
    assert rapport_pdf.lag_rapport_pdf(rapport, grafer=[eksport]).startswith(b"%PDF-")
    assert eksport.png_bytes() in bilder


@pytest.mark.parametrize("bilde", ["https://example.com/graph.png", "data:image/svg+xml,<svg/>", "data:image/png;base64,invalid"])
def test_bare_gyldige_png_bilder_aksepteres(bilde):
    with pytest.raises(ValueError):
        GrafEksport(id="samlet", tittel="Graf", bilde=bilde)


def test_interaktiv_api_og_rapport_sjekker_utvalg(monkeypatch):
    body = {"input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [13.6, 17]},
            "rangering": {"strategi": "billigste_godkjent"}, "valgte_ror": [{"dn_od_mm": 560, "sdr": 17}]}
    client = TestClient(api.app)
    grafer = client.post("/api/calculations/interactive-plots", json=body).json()["grafer"]
    assert [g["id"] for g in grafer] == ["pris", "samlet", "ror-560-17"]
    monkeypatch.setattr(api, "generer_faglig_vurdering", lambda _: None)
    mottatt = []

    def pdf(rapport, *, grafer):
        mottatt.extend(grafer)
        return b"%PDF-test"

    monkeypatch.setattr(api, "lag_rapport_pdf", pdf)
    body["grafer"] = [{"id": g["id"], "tittel": g["tittel"], "bilde": png()} for g in grafer]
    assert client.post("/api/calculations/report", json=body).status_code == 200
    assert [g.id for g in mottatt] == ["pris", "samlet", "ror-560-17"]
    body["grafer"].pop()
    assert client.post("/api/calculations/report", json=body).status_code == 400


def test_standardutsnitt_passes_til_relevante_punkter_uten_a_kutte_data(resultat):
    r = resultat.godkjente[0]
    valg = [RorGrafValg(dn_od_mm=r.dn_od_mm, sdr=r.sdr)]
    grafer = lag_interaktive_grafer(resultat, valg, False)
    samlet = grafer[0]
    assert samlet["layout"]["xaxis"]["range"][1] < 450
    for graf in grafer:
        xmin, xmax = graf["layout"]["xaxis"]["range"]
        ymin, ymax = graf["layout"]["yaxis"]["range"]
        assert xmin == ymin == 0
        assert xmin <= resultat.input.qdim_l_s < xmax
        assert ymin <= resultat.input.maks_totalt_tap_m < ymax
        for trace in graf["data"]:
            assert max(trace["x"]) <= graf["fullRange"]["x"][1]
            assert max(trace["y"]) < graf["fullRange"]["y"][1]
            if trace["mode"] == "markers":
                assert xmin <= trace["x"][0] < xmax
                assert ymin <= trace["y"][0] < ymax
        assert graf["data"][0]["x"][-1] == (450 if graf["id"] == "samlet" else 400)


@pytest.mark.parametrize("antall", [1, 3, 5])
def test_inspektordata_stemmer_med_beregninger_og_markorer(resultat, antall):
    ror = resultat.godkjente[:antall]
    valg = [RorGrafValg(dn_od_mm=r.dn_od_mm, sdr=r.sdr) for r in ror]
    grafer = lag_interaktive_grafer(resultat, valg)
    by_id = {f"{r.dn_od_mm:g}-{r.sdr:g}": r for r in resultat.godkjente}
    for graf in grafer:
        assert len({p["id"] for p in graf["pipes"]}) == len(graf["pipes"])
        for pipe in graf["pipes"]:
            r = by_id[pipe["id"]]
            assert pipe["values"] == {"q": resultat.input.qdim_l_s, "h": r.totalt_tap_m,
                                      "v": r.vannhastighet_m_s, "tau": r.skjaerspenning_pa,
                                      "price": r.pris_mnok}
            for punkt in pipe["points"]:
                trace = graf["data"][punkt["traceIndex"]]
                assert trace["legendgroup"] == pipe["id"]
                assert trace["marker"]["color"] == pipe["color"]
                if graf["id"] != "pris":
                    assert (punkt["q"], punkt["h"], punkt["v"], punkt["tau"]) == (
                        trace["x"][0], trace["y"][0], *trace["customdata"][0])
                    annotation = graf["layout"]["annotations"][punkt["annotationIndex"]]
                    assert (annotation["x"], annotation["y"]) == (punkt["q"], punkt["h"])


def test_terskler_er_synlige_uavhengig_av_festede_bokser(resultat):
    r = resultat.godkjente[0]
    grafer = lag_interaktive_grafer(resultat, [RorGrafValg(dn_od_mm=r.dn_od_mm, sdr=r.sdr)])
    for graf in grafer:
        assert graf["thresholdAnnotations"]
        assert all(a["showarrow"] is False for a in graf["thresholdAnnotations"])
        assert not any(a in graf["layout"]["annotations"] for a in graf["thresholdAnnotations"])
        labels = " ".join(a["text"] for a in graf["thresholdAnnotations"])
        assert "τ min = 2 Pa" in labels
        if graf["id"] != "pris":
            assert "H max = 70 m" in labels
            assert "Qdim = 300 l/s" in labels


def test_prisutsnitt_beholder_null_skjarkrav_og_data_uten_godkjente(resultat):
    # The fallback comparison must also provide uniquely identifiable inspector
    # entries when no pipe satisfies the project constraints.
    fallback = resultat.model_copy(update={"godkjente": []})
    graf = lag_interaktive_grafer(fallback, [])[0]
    assert len(graf["pipes"]) == len(resultat.alle_resultater)
    assert len({p["id"] for p in graf["pipes"]}) == len(graf["pipes"])
    assert len(graf["pipes"]) >= 12
    assert len({p["color"] for p in graf["pipes"][:12]}) == 12
    assert graf["layout"]["yaxis"]["range"][0] == 0
    for trace in graf["data"]:
        for axis, value in (("xaxis", trace["x"][0]), ("yaxis", trace["y"][0])):
            lo, hi = graf["layout"][axis]["range"]
            assert lo <= value < hi
