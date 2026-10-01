import pytest
from fastapi.testclient import TestClient

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


def test_post_calculations_ugyldig_qdim_gir_422():
    body = {
        "input": {
            "qdim_l_s": -300.0,
            "lengde_m": 10250.0,
            "tillatte_sdr": [17.0],
        },
        "rangering": {"strategi": "billigste_godkjent"},
    }

    respons = client.post("/api/calculations", json=body)
    assert respons.status_code == 422  # pydantic-validering feiler før tjenestelaget nås


def test_post_calculations_ukjent_sdr_gir_400():
    body = {
        "input": {
            "qdim_l_s": 300.0,
            "lengde_m": 10250.0,
            "tillatte_sdr": [999.0],
        },
        "rangering": {"strategi": "billigste_godkjent"},
    }

    respons = client.post("/api/calculations", json=body)
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
