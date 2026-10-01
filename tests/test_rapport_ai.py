import json

import httpx
import pytest
from fastapi.testclient import TestClient

import api
import rapport_ai
import rapport_pdf
from config import CSV_FIL
from data_io import les_ror_csv
from modeller import BeregningsInput, MAKS_VURDERING_TEGN, RangeringsValg, RorValg
from rapport import lag_rapportdata
from tjenester import beregn_pumpeledning


VURDERING = (
    "Det anbefalte røret oppfyller PipeSelectors krav og er valgt etter laveste beregnede kostnad.\n\n"
    "De valgte alternativene viser ulike hydrauliske resultater og kostnader. "
    "Prosjektspesifikke forhold må fortsatt vurderes av ansvarlig prosjekterende."
)


@pytest.fixture
def resultat():
    return beregn_pumpeledning(
        BeregningsInput(qdim_l_s=300, lengde_m=10250, tillatte_sdr=[13.6, 17]),
        les_ror_csv(CSV_FIL), RangeringsValg(strategi="billigste_godkjent"),
    )


@pytest.fixture
def rapport(resultat):
    return lag_rapportdata(resultat, [RorValg(dn_od_mm=630, sdr=13.6)])


@pytest.fixture
def aktivert(monkeypatch):
    monkeypatch.setenv("PIPESELECTOR_AI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-secret-for-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


def svar(tekst=VURDERING, status="completed"):
    return {"status": status, "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": tekst}]},
    ]}


def fake_ai(monkeypatch, data=None, status=200, feil=None, raatt_svar=None):
    mottatt = []
    original_client = httpx.Client

    def handler(request):
        mottatt.append(request)
        if feil:
            raise feil
        if raatt_svar is not None:
            return httpx.Response(status, content=raatt_svar)
        return httpx.Response(status, json=svar() if data is None else data)

    def client(**kwargs):
        assert kwargs["timeout"].read == 20
        assert kwargs["timeout"].connect == 5
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(rapport_ai.httpx, "Client", client)
    return mottatt


def test_prompt_bygges_fra_rapport_og_bare_valgte_ror(rapport, resultat):
    for_rapport = rapport.model_dump()
    prompt = rapport_ai.bygg_vurderingsprompt(rapport)
    grunnlag = json.loads(prompt["input"][0]["content"])
    assert grunnlag["forutsetninger"]["qdim_l_s"] == rapport.input.qdim_l_s
    assert grunnlag["forutsetninger"]["lengde_sjo_m"] == rapport.input.lengde_m
    assert grunnlag["rangering"] == rapport.rangering.model_dump(exclude_none=True)
    assert grunnlag["anbefalingsbegrunnelse"] == rapport.anbefalingsbegrunnelse
    a = grunnlag["anbefalt"]
    assert (a["dn_od_mm"], a["sdr"]) == (rapport.anbefalt.dn_od_mm, rapport.anbefalt.sdr)
    assert a["vannhastighet_m_s"] == rapport.anbefalt.vannhastighet_m_s
    assert a["pris_mnok"] == rapport.anbefalt.pris_mnok
    assert set(a["kravstatus"].values()) == {"oppfylt"}
    valgte = {(r["dn_od_mm"], r["sdr"]) for r in grunnlag["sammenlignede_alternativer"]}
    assert valgte == {(630, 13.6)}
    alle_sendte = valgte | {(a["dn_od_mm"], a["sdr"])}
    uvalgte = {(r.dn_od_mm, r.sdr) for r in resultat.godkjente} - alle_sendte
    assert uvalgte
    assert alle_sendte.isdisjoint(uvalgte)
    assert "alle_resultater" not in grunnlag
    assert "godkjente" not in grunnlag
    assert "faglig_vurdering" not in grunnlag
    assert rapport.model_dump() == for_rapport


def test_prompt_har_sprak_og_faglige_begrensninger(rapport):
    instruks = rapport_ai.bygg_vurderingsprompt(rapport)["instructions"]
    for fragment in ["norsk bokmål", "2-4 korte avsnitt", "Ikke utfør beregninger",
                     "finn på tall", "Ikke endre, velg eller ranger", "standarder", "optimal"]:
        assert fragment in instruks


def test_prompt_tomt_utvalg_og_annen_rangeringsstrategi(resultat):
    rapport = lag_rapportdata(resultat)
    rapport.rangering = RangeringsValg(strategi="egendefinert_vekting", vekter={"pris": 3, "hastighet": 1})
    grunnlag = json.loads(rapport_ai.bygg_vurderingsprompt(rapport)["input"][0]["content"])
    assert grunnlag["sammenlignede_alternativer"] == []
    assert grunnlag["rangering"]["vekter"] == {"pris": 3, "hastighet": 1}


def test_ai_kall_bruker_konfigurasjon_uten_a_mutere_resultater(rapport, resultat, aktivert, monkeypatch):
    for_rapport = rapport.model_dump()
    for_resultat = resultat.model_dump()
    mottatt = fake_ai(monkeypatch)
    monkeypatch.setenv("OPENAI_MODEL", "konfigurert-testmodell")
    assert rapport_ai.generer_faglig_vurdering(rapport) == VURDERING
    assert len(mottatt) == 1
    assert str(mottatt[0].url) == "https://api.openai.com/v1/responses"
    assert mottatt[0].headers["authorization"] == "Bearer fake-secret-for-test"
    body = json.loads(mottatt[0].content)
    assert body["model"] == "konfigurert-testmodell"
    assert body["store"] is False
    assert body["max_output_tokens"] == 900
    assert "tools" not in body
    assert rapport.model_dump() == for_rapport
    assert resultat.model_dump() == for_resultat


def test_standardmodell(rapport, aktivert, monkeypatch):
    mottatt = fake_ai(monkeypatch)
    rapport_ai.generer_faglig_vurdering(rapport)
    assert json.loads(mottatt[0].content)["model"] == "gpt-4.1-mini"


@pytest.mark.parametrize("tilfelle", ["avslatt", "mangler_nokkel", "ingen_anbefaling"])
def test_ai_hoppes_over_uten_nettverkskall(rapport, aktivert, monkeypatch, tilfelle):
    mottatt = fake_ai(monkeypatch)
    if tilfelle == "avslatt":
        monkeypatch.setenv("PIPESELECTOR_AI_ENABLED", "false")
    elif tilfelle == "mangler_nokkel":
        monkeypatch.delenv("OPENAI_API_KEY")
    else:
        rapport.anbefalt = None
    assert rapport_ai.generer_faglig_vurdering(rapport) is None
    assert mottatt == []


@pytest.mark.parametrize("http_status", [401, 429, 500])
def test_http_feil_utelater_vurdering_uten_nokkel_i_logg(rapport, aktivert, monkeypatch, caplog, http_status):
    mottatt = fake_ai(monkeypatch, data={"error": "fake-secret-for-test"}, status=http_status)
    assert rapport_ai.generer_faglig_vurdering(rapport) is None
    assert len(mottatt) == 1
    assert "fake-secret-for-test" not in caplog.text


@pytest.mark.parametrize("feil", [httpx.ReadTimeout("Testtimeout"), httpx.ConnectError("Testfeil")])
def test_timeout_og_tilkoblingsfeil_utelater_vurdering(rapport, aktivert, monkeypatch, feil):
    fake_ai(monkeypatch, feil=feil)
    assert rapport_ai.generer_faglig_vurdering(rapport) is None


@pytest.mark.parametrize("data", [
    svar(""), svar("  \n\n "), svar(VURDERING, "incomplete"), {},
    {"status": "completed", "output": None},
    {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "Avvist"}]}]},
])
def test_ugyldige_og_ufullstendige_svar_utelates(rapport, aktivert, monkeypatch, data):
    fake_ai(monkeypatch, data=data)
    assert rapport_ai.generer_faglig_vurdering(rapport) is None


def test_ikke_json_svar_utelates(rapport, aktivert, monkeypatch):
    fake_ai(monkeypatch, raatt_svar=b"ikke json")
    assert rapport_ai.generer_faglig_vurdering(rapport) is None


def test_lang_tekst_begrenses_til_hele_avsnitt():
    avsnitt = "En nøktern faglig formulering."
    resultat = rapport_ai._begrens_vurdering("\n\n".join([avsnitt] * 10))
    assert resultat.split("\n\n") == [avsnitt] * 4
    lang = "\n\n".join([avsnitt, avsnitt, "Tekst " * 1000])
    resultat = rapport_ai._begrens_vurdering(lang)
    assert resultat == f"{avsnitt}\n\n{avsnitt}"
    assert len(resultat) <= MAKS_VURDERING_TEGN
    assert rapport_ai._begrens_vurdering("x" * (MAKS_VURDERING_TEGN + 1)) is None


@pytest.mark.parametrize("tekst", ["# Overskrift\n\nAvsnitt.", "- Punkt\n\nAvsnitt.", "| Tabell |\n\nAvsnitt.", "**Fet tekst**\n\nAvsnitt."])
def test_markdown_utelates(tekst):
    assert rapport_ai._begrens_vurdering(tekst) is None


def test_pdf_presenterer_vurderingen_mellom_sammenligning_og_grafer(rapport, monkeypatch):
    for_rapport = rapport.model_dump()
    rapport.faglig_vurdering = VURDERING
    tekster = []
    original = rapport_pdf.Paragraph

    def paragraph(tekst, stil):
        tekster.append(tekst)
        return original(tekst, stil)

    monkeypatch.setattr(rapport_pdf, "Paragraph", paragraph)
    pdf = rapport_pdf.lag_rapport_pdf(rapport)
    assert pdf.startswith(b"%PDF-")
    assert tekster.index("5. Sammenligning av valgte alternativer") < tekster.index("Faglig vurdering")
    assert tekster.index("Faglig vurdering") < tekster.index("6. Sammenligningsgrafer")
    assert all(a in tekster for a in VURDERING.split("\n\n"))
    rapport.faglig_vurdering = None
    assert rapport.model_dump() == for_rapport


@pytest.mark.parametrize("modus", ["tilgjengelig", "timeout", "avslatt"])
def test_endpoint_med_valgfri_ai_gir_pdf_og_bevarer_beregningen(resultat, aktivert, monkeypatch, modus):
    for_resultat = resultat.model_dump()
    mottatt = fake_ai(monkeypatch, feil=httpx.ReadTimeout("Testtimeout") if modus == "timeout" else None)
    if modus == "avslatt":
        monkeypatch.setenv("PIPESELECTOR_AI_ENABLED", "false")
    sendt_til_pdf = []
    original_pdf = api.lag_rapport_pdf

    def pdf(rapport):
        sendt_til_pdf.append(rapport.model_dump())
        return original_pdf(rapport)

    monkeypatch.setattr(api, "_utfor_beregning", lambda request: resultat)
    monkeypatch.setattr(api, "lag_rapport_pdf", pdf)
    with TestClient(api.app) as client:
        respons = client.post("/api/calculations/report", json={
            "input": resultat.input.model_dump(), "rangering": resultat.rangering.model_dump(),
            "valgte_ror": [{"dn_od_mm": 630, "sdr": 13.6}],
        })
    assert respons.status_code == 200
    assert respons.headers["content-type"] == "application/pdf"
    assert respons.content.startswith(b"%PDF-")
    rapport = sendt_til_pdf[0]
    assert rapport["faglig_vurdering"] == (VURDERING if modus == "tilgjengelig" else None)
    assert rapport["anbefalt"] == for_resultat["anbefalt"]
    assert [(r["dn_od_mm"], r["sdr"]) for r in rapport["sammenlignede_alternativer"]] == [(630, 13.6)]
    assert len(mottatt) == (0 if modus == "avslatt" else 1)
    assert resultat.model_dump() == for_resultat
