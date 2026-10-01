import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import plotting
from api import app

client = TestClient(app)


def test_forside():
    respons = client.get("/")
    assert respons.status_code == 200
    assert respons.json()["status"] == "API-et kjører"


def test_health():
    respons = client.get("/health")
    assert respons.status_code == 200
    assert respons.json() == {"status": "ok"}


def test_ui_serveres():
    respons = client.get("/ui/")
    assert respons.status_code == 200
    assert "text/html" in respons.headers["content-type"]
    assert "Pumpeledningskalkulator" in respons.text
    assert "Maks. utvendig diameter ved trykket" in respons.text


def test_hent_standardverdier():
    respons = client.get("/api/defaults")
    assert respons.status_code == 200

    data = respons.json()
    assert "qdim_l_s" in data["obligatoriske_felt"]
    assert "lengde_m" in data["obligatoriske_felt"]
    assert "tillatte_sdr" in data["obligatoriske_felt"]
    assert data["standardverdier"]["maks_totalt_tap_m"] == 70.0
    assert data["standardverdier"]["ruhet_mm"] == 0.5


def test_hent_rorkatalog_valg():
    respons = client.get("/api/pipe-catalog/options")
    assert respons.status_code == 200

    data = respons.json()
    assert 17.0 in data["tilgjengelige_sdr"]
    assert 13.6 in data["tilgjengelige_sdr"]
    assert 560.0 in data["tilgjengelige_dn_mm"]


def test_post_calculations_referansetilfelle():
    body = {
        "input": {
            "qdim_l_s": 300.0,
            "lengde_m": 10250.0,
            "tillatte_sdr": [13.6, 17.0],
        },
        "rangering": {"strategi": "billigste_godkjent"},
    }

    respons = client.post("/api/calculations", json=body)
    assert respons.status_code == 200

    data = respons.json()
    assert data["status"] == "success"
    assert data["resultat"]["anbefalt"]["dn_od_mm"] == pytest.approx(560.0)
    assert data["resultat"]["anbefalt"]["sdr_navn"] == "SDR 17"
    assert data["resultat"]["anbefalt"]["maks_utvendig_diameter_mm"] > 560.0
    assert data["sammendrag"]["antall_godkjent"] > 0


@pytest.mark.parametrize("sti", ["/api/calculations", "/api/calculations/plots"])
def test_post_calculations_ugyldig_qdim_gir_422(sti):
    body = {
        "input": {
            "qdim_l_s": -300.0,
            "lengde_m": 10250.0,
            "tillatte_sdr": [17.0],
        },
        "rangering": {"strategi": "billigste_godkjent"},
    }

    respons = client.post(sti, json=body)
    assert respons.status_code == 422  # pydantic-validering feiler før tjenestelaget nås


@pytest.mark.parametrize("sti", ["/api/calculations", "/api/calculations/plots"])
def test_post_calculations_ukjent_sdr_gir_400(sti):
    body = {
        "input": {
            "qdim_l_s": 300.0,
            "lengde_m": 10250.0,
            "tillatte_sdr": [999.0],
        },
        "rangering": {"strategi": "billigste_godkjent"},
    }

    respons = client.post(sti, json=body)
    assert respons.status_code == 400
    assert "999" in respons.json()["detail"]


def test_post_calculations_manglende_tillatte_sdr_gir_422():
    body = {
        "input": {"qdim_l_s": 300.0, "lengde_m": 10250.0},
        "rangering": {"strategi": "billigste_godkjent"},
    }

    respons = client.post("/api/calculations", json=body)
    assert respons.status_code == 422


def test_post_calculations_egendefinert_vekting_uten_vekter_gir_422():
    body = {
        "input": {"qdim_l_s": 300.0, "lengde_m": 10250.0, "tillatte_sdr": [17.0]},
        "rangering": {"strategi": "egendefinert_vekting"},
    }

    respons = client.post("/api/calculations", json=body)
    assert respons.status_code == 422


def test_post_calculations_egendefinert_vekting_vilkarlige_vekter():
    body = {
        "input": {"qdim_l_s": 300.0, "lengde_m": 10250.0, "tillatte_sdr": [13.6, 17.0]},
        "rangering": {
            "strategi": "egendefinert_vekting",
            "vekter": {"pris": 3, "hastighet": 1, "skjaerspenning": 1},
        },
    }

    respons = client.post("/api/calculations", json=body)
    assert respons.status_code == 200
    assert respons.json()["resultat"]["anbefalt"] is not None


@pytest.mark.parametrize("min_hastighet", [0.8, 1000.0])
def test_grafer_for_beregningen(min_hastighet, tmp_path, monkeypatch):
    monkeypatch.setattr(plotting, "OUTPUT_MAPPE", tmp_path)
    body = {
        "input": {
            "qdim_l_s": 300.0,
            "lengde_m": 10250.0,
            "tillatte_sdr": [13.6, 17.0],
            "min_hastighet_m_s": min_hastighet,
        },
        "rangering": {"strategi": "billigste_godkjent"},
    }
    beregning = client.post("/api/calculations", json=body).json()
    respons = client.post("/api/calculations/plots", json=body)
    assert respons.status_code == 200
    grafer = respons.json()["grafer"]
    godkjente = beregning["resultat"]["godkjente"]
    assert len(grafer) == (2 + len(godkjente) if godkjente else 1)
    assert grafer[0]["tittel"] == "Pris mot skjærspenning"
    if godkjente:
        assert grafer[1]["tittel"] == "Samlet ledningskarakteristikk"
        for graf, ror in zip(grafer[2:], godkjente):
            assert graf["tittel"] == f"Ledningskarakteristikk DN{ror['dn_od_mm']:g} {ror['sdr_navn']}"
    for graf in grafer:
        assert graf["bilde"].startswith("data:image/png;base64,")
        with Image.open(io.BytesIO(base64.b64decode(graf["bilde"].split(",", 1)[1]))) as bilde:
            assert bilde.format == "PNG"
            assert bilde.width > 1000 and bilde.height > 1000
            assert any(lav < hoy for lav, hoy in bilde.convert("RGB").getextrema())
    assert list(tmp_path.iterdir()) == []


def test_graffeil_beholder_beregning(monkeypatch):
    def feiler(resultat, **kwargs):
        raise RuntimeError("Testfeil")

    monkeypatch.setattr("api.lag_grafer_for_ui", feiler)
    body = {
        "input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [17]},
        "rangering": {"strategi": "billigste_godkjent"},
    }
    assert client.post("/api/calculations", json=body).status_code == 200
    respons = client.post("/api/calculations/plots", json=body)
    assert respons.status_code == 500
    assert respons.json()["detail"] == "Kunne ikke lage grafene for beregningen."


def test_prisgraf_for_alle_godkjente_uten_ledningskarakteristikker(tmp_path, monkeypatch):
    monkeypatch.setattr(plotting, "OUTPUT_MAPPE", tmp_path)
    vist = []
    original = plotting.plott_pris_vs_skjaerspenning

    def prisgraf(resultat_df, *args, **kwargs):
        vist.extend(resultat_df[resultat_df["Godkjent"]]["DN"].tolist())
        return original(resultat_df, *args, **kwargs)

    def uventet(*args, **kwargs):
        pytest.fail("Ledningskarakteristikk skal ikke lages før rør er valgt")

    monkeypatch.setattr(plotting, "plott_pris_vs_skjaerspenning", prisgraf)
    monkeypatch.setattr(plotting, "plott_samlet_ledningskarakteristikk", uventet)
    monkeypatch.setattr(plotting, "lag_ledningskarakteristikk", uventet)
    body = {
        "input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [13.6, 17]},
        "rangering": {"strategi": "billigste_godkjent"},
        "valgte_ror": [],
    }
    godkjente = client.post("/api/calculations", json=body).json()["resultat"]["godkjente"]
    respons = client.post("/api/calculations/plots", json=body)
    assert respons.status_code == 200
    assert [g["tittel"] for g in respons.json()["grafer"]] == ["Pris mot skjærspenning"]
    assert sorted(vist) == sorted(r["dn_od_mm"] for r in godkjente)
    assert list(tmp_path.iterdir()) == []


def test_ledningskarakteristikker_bare_for_valgte_ror(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(plotting, "OUTPUT_MAPPE", tmp_path)
    samlet_utvalg = []
    original = plotting.plott_samlet_ledningskarakteristikk

    def samlet(ror_liste, *args, **kwargs):
        samlet_utvalg.extend(ror_liste)
        return original(ror_liste, *args, **kwargs)

    monkeypatch.setattr(plotting, "plott_samlet_ledningskarakteristikk", samlet)
    body = {
        "input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [13.6, 17]},
        "rangering": {"strategi": "billigste_godkjent"},
        "vis_prisgraf": False,
        "valgte_ror": [{"dn_od_mm": 560, "sdr": 17}, {"dn_od_mm": 630, "sdr": 13.6}],
    }
    respons = client.post("/api/calculations/plots", json=body)
    assert respons.status_code == 200
    assert [g["tittel"] for g in respons.json()["grafer"]] == [
        "Samlet ledningskarakteristikk",
        "Ledningskarakteristikk DN560 SDR 17",
        "Ledningskarakteristikk DN630 SDR 13,6",
    ]
    assert samlet_utvalg == [{"DN": 560, "SDR": 17}, {"DN": 630, "SDR": 13.6}]
    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("dn", [110, 9999])
def test_grafvalg_ma_vaere_godkjent_ror(dn, tmp_path, monkeypatch):
    monkeypatch.setattr(plotting, "OUTPUT_MAPPE", tmp_path)
    body = {
        "input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [17]},
        "rangering": {"strategi": "billigste_godkjent"},
        "valgte_ror": [{"dn_od_mm": dn, "sdr": 17}],
    }
    respons = client.post("/api/calculations/plots", json=body)
    assert respons.status_code == 400
    assert "Bare godkjente rør" in respons.json()["detail"]
    assert list(tmp_path.iterdir()) == []


def test_grafvalg_ugyldig_dn_gir_422():
    body = {
        "input": {"qdim_l_s": 300, "lengde_m": 10250, "tillatte_sdr": [17]},
        "rangering": {"strategi": "billigste_godkjent"},
        "valgte_ror": [{"dn_od_mm": -560, "sdr": 17}],
    }
    assert client.post("/api/calculations/plots", json=body).status_code == 422
