from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import api
import rapport_pdf
from config import CSV_FIL
from data_io import les_ror_csv
from modeller import BeregningsInput, RangeringsValg, RorValg
from rapport import lag_rapportdata
from tjenester import beregn_pumpeledning


@pytest.fixture
def resultat():
    return beregn_pumpeledning(
        BeregningsInput(qdim_l_s=300, lengde_m=10250, tillatte_sdr=[13.6, 17]),
        les_ror_csv(CSV_FIL),
        RangeringsValg(strategi="billigste_godkjent"),
    )


@pytest.fixture
def foresporsel():
    return {
        "input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [13.6, 17]},
        "rangering": {"strategi": "billigste_godkjent"},
        "valgte_ror": [{"dn_od_mm": 630, "sdr": 13.6}],
    }


def sjekk_pdf(pdf):
    assert len(pdf) > 1000
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")


@pytest.mark.parametrize("med_utvalg", [False, True])
def test_pdf_fra_rapportdata_uten_mutasjon(resultat, med_utvalg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for_resultat = resultat.model_dump()
    utvalg = [RorValg(dn_od_mm=630, sdr=13.6)] if med_utvalg else []
    rapport = lag_rapportdata(resultat, utvalg)
    for_rapport = rapport.model_dump()

    sjekk_pdf(rapport_pdf.lag_rapport_pdf(rapport))

    assert rapport.model_dump() == for_rapport
    assert resultat.model_dump() == for_resultat
    assert list(tmp_path.iterdir()) == []


def test_pdf_er_reproduserbar_med_fast_tid(resultat):
    rapport = lag_rapportdata(resultat, [RorValg(dn_od_mm=630, sdr=13.6)])
    tidspunkt = datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)
    assert rapport_pdf.lag_rapport_pdf(rapport, tidspunkt) == rapport_pdf.lag_rapport_pdf(rapport, tidspunkt)


def test_pdf_uten_godkjente_ror():
    resultat = beregn_pumpeledning(
        BeregningsInput(qdim_l_s=300, lengde_m=10250, tillatte_sdr=[17], min_hastighet_m_s=1000),
        les_ror_csv(CSV_FIL), RangeringsValg(strategi="billigste_godkjent"),
    )
    assert resultat.anbefalt is None
    sjekk_pdf(rapport_pdf.lag_rapport_pdf(lag_rapportdata(resultat)))


def test_grafene_viser_bare_valgte_alternativer(resultat, monkeypatch):
    valgt = resultat.godkjente[-1]
    rapport = lag_rapportdata(resultat, [RorValg(dn_od_mm=valgt.dn_od_mm, sdr=valgt.sdr)])
    viste = []
    original = rapport_pdf.lag_sammenligningsgraf_for_rapport

    def graf(ror, anbefalt):
        viste.extend((r.dn_od_mm, r.sdr) for r in ror)
        return original(ror, anbefalt)

    monkeypatch.setattr(rapport_pdf, "lag_sammenligningsgraf_for_rapport", graf)
    sjekk_pdf(rapport_pdf.lag_rapport_pdf(rapport))
    assert viste == [(valgt.dn_od_mm, valgt.sdr)]
    assert (resultat.anbefalt.dn_od_mm, resultat.anbefalt.sdr) not in viste


def test_tomt_utvalg_lager_ikke_graf(resultat, monkeypatch):
    def uventet(*args):
        pytest.fail("Ingen graf skal genereres uten valgte alternativer")

    monkeypatch.setattr(rapport_pdf, "lag_sammenligningsgraf_for_rapport", uventet)
    sjekk_pdf(rapport_pdf.lag_rapport_pdf(lag_rapportdata(resultat)))


def test_rapport_endpoint_returnerer_pdf(foresporsel):
    with TestClient(api.app) as client:
        respons = client.post("/api/calculations/report", json=foresporsel)
    assert respons.status_code == 200
    assert respons.headers["content-type"] == "application/pdf"
    assert respons.headers["content-disposition"] == 'attachment; filename="pipeselector-rapport.pdf"'
    sjekk_pdf(respons.content)


@pytest.mark.parametrize("utvalg", [[], [{"dn_od_mm": 630, "sdr": 13.6}]])
def test_endpoint_bruker_rapportbygger_og_bare_onsket_utvalg(resultat, foresporsel, utvalg, monkeypatch):
    for_resultat = resultat.model_dump()
    mottatt = []

    def pdf(rapport):
        mottatt.append(rapport)
        return b"%PDF-test"

    monkeypatch.setattr(api, "_utfor_beregning", lambda request: resultat)
    monkeypatch.setattr(api, "lag_rapport_pdf", pdf)
    # Dupliser valget: eksisterende rapportbygger skal inkludere det bare én gang.
    foresporsel["valgte_ror"] = utvalg * 2
    with TestClient(api.app) as client:
        respons = client.post("/api/calculations/report", json=foresporsel)
    assert respons.status_code == 200
    rapport = mottatt[0]
    assert [(r.dn_od_mm, r.sdr) for r in rapport.sammenlignede_alternativer] == [
        (v["dn_od_mm"], v["sdr"]) for v in utvalg
    ]
    assert rapport.anbefalt == resultat.anbefalt
    assert rapport.input == resultat.input
    assert rapport.rangering == resultat.rangering
    assert resultat.model_dump() == for_resultat


def test_endpoint_utelatt_utvalg_er_tomt(foresporsel, monkeypatch):
    del foresporsel["valgte_ror"]

    def pdf(rapport):
        assert rapport.sammenlignede_alternativer == []
        return b"%PDF-test"

    monkeypatch.setattr(api, "lag_rapport_pdf", pdf)
    with TestClient(api.app) as client:
        assert client.post("/api/calculations/report", json=foresporsel).status_code == 200


@pytest.mark.parametrize("dn", [110, 9999])
def test_rapportvalg_ma_vaere_godkjent_ror(foresporsel, dn):
    foresporsel["valgte_ror"] = [{"dn_od_mm": dn, "sdr": 17}]
    with TestClient(api.app) as client:
        respons = client.post("/api/calculations/report", json=foresporsel)
    assert respons.status_code == 400
    assert "Bare godkjente rør" in respons.json()["detail"]


@pytest.mark.parametrize("utvalg", [[{"dn_od_mm": -1, "sdr": 17}], [{"dn_od_mm": 560, "sdr": 0}], None])
def test_rapportvalg_strukturfeil_gir_422(foresporsel, utvalg):
    foresporsel["valgte_ror"] = utvalg
    with TestClient(api.app) as client:
        assert client.post("/api/calculations/report", json=foresporsel).status_code == 422


def test_pdf_feil_gir_norsk_500_uten_a_endre_beregning(resultat, foresporsel, monkeypatch):
    for_resultat = resultat.model_dump()

    def feil(rapport):
        raise RuntimeError("Testfeil")

    monkeypatch.setattr(api, "_utfor_beregning", lambda request: resultat)
    monkeypatch.setattr(api, "lag_rapport_pdf", feil)
    with TestClient(api.app) as client:
        respons = client.post("/api/calculations/report", json=foresporsel)
        assert client.post("/api/calculations", json=foresporsel).status_code == 200
    assert respons.status_code == 500
    assert respons.json()["detail"] == "Kunne ikke lage rapporten for beregningen."
    assert resultat.model_dump() == for_resultat
