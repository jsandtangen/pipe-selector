"""
FastAPI-api for pumpeledningskalkulatoren.

Tynt api-lag: validerer og oversetter HTTP-data, kaller tjenestelaget
(tjenester.beregn_pumpeledning) og returnerer et strukturert resultat.
Ingen faglige beregninger skal ligge her - se hydraulikk.py, beregninger.py,
oppdrift_lodd.py og rangering.py for selve fagligheten.

Kjør lokalt med:
    uvicorn api:app --reload

Enkelt brukergrensesnitt:
    http://127.0.0.1:8000/ui/

Teknisk dokumentasjon (Swagger UI):
    http://127.0.0.1:8000/docs
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import CSV_FIL
from data_io import DN_OD_KOLONNE, finn_sdr_liste_fra_katalog, les_ror_csv
from modeller import BeregningsInput, BeregningsResultat, RangeringsValg
from plotting import lag_grafer_for_ui
from tjenester import beregn_pumpeledning

logger = logging.getLogger("pumpeledningskalkulator")

app = FastAPI(
    title="Pumpeledningskalkulator",
    description="API for hydraulisk dimensjonering av pumpeledninger",
    version="0.1.0",
)

STATIC_MAPPE = Path(__file__).resolve().parent / "static"
app.mount("/ui", StaticFiles(directory=STATIC_MAPPE, html=True), name="ui")


@app.get("/")
def forside():
    return {
        "navn": "Pumpeledningskalkulator",
        "status": "API-et kjører",
        "brukergrensesnitt": "/ui/",
        "dokumentasjon": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/defaults")
def hent_standardverdier():
    """
    Returnerer faglige standardverdier for beregningsparametere.

    Feltene qdim_l_s, lengde_m og tillatte_sdr har bevisst ingen
    standardverdi i systemet - de er obligatorisk prosjektinput og listes i
    obligatoriske_felt, ikke i standardverdier. Se prosjektavklaring
    2026-08-06: hvilke SDR-/trykklasser som er egnet varierer fra prosjekt
    til prosjekt og kan derfor ikke ha en fast systemstandard.
    """
    standardverdier = {}
    obligatoriske_felt = []

    for navn, felt in BeregningsInput.model_fields.items():
        if felt.is_required():
            obligatoriske_felt.append(navn)
        else:
            standardverdier[navn] = felt.default

    return {
        "standardverdier": standardverdier,
        "obligatoriske_felt": obligatoriske_felt,
    }


@app.get("/api/pipe-catalog/options")
def hent_rorkatalog_valg():
    """Returnerer hvilke DN- og SDR-verdier som faktisk finnes i rørkatalogen."""
    try:
        df = les_ror_csv(CSV_FIL)
        sdr_liste = finn_sdr_liste_fra_katalog(df)
    except FileNotFoundError:
        logger.exception("Fant ikke rørkatalogfilen")
        raise HTTPException(status_code=500, detail="Fant ikke rørkatalogfilen på serveren.")
    except ValueError as feil:
        raise HTTPException(status_code=500, detail=str(feil))

    dn_verdier = sorted(
        float(v) for v in df[DN_OD_KOLONNE].dropna().unique().tolist() if v > 0
    )

    return {
        "tilgjengelige_dn_mm": dn_verdier,
        "tilgjengelige_sdr": [info["SDR"] for info in sdr_liste],
    }


class BeregningsRequest(BaseModel):
    input: BeregningsInput
    rangering: RangeringsValg


class BeregningsSammendrag(BaseModel):
    antall_beregnet: int
    antall_godkjent: int
    antall_underkjent: int


class BeregningsResponse(BaseModel):
    status: str = "success"
    sammendrag: BeregningsSammendrag
    resultat: BeregningsResultat


def _utfor_beregning(forespørsel: BeregningsRequest):
    try:
        df = les_ror_csv(CSV_FIL)
    except FileNotFoundError:
        logger.exception("Fant ikke rørkatalogfilen")
        raise HTTPException(status_code=500, detail="Fant ikke rørkatalogfilen på serveren.")

    try:
        resultat = beregn_pumpeledning(
            parametere=forespørsel.input,
            rorkatalog=df,
            rangeringsvalg=forespørsel.rangering,
        )
    except ValueError as feil:
        # ValueError fra tjenester.py/data_io.py er allerede skrevet med
        # brukervennlig norsk tekst - trygt å sende videre til klienten.
        raise HTTPException(status_code=400, detail=str(feil))
    except Exception:
        logger.exception("Uventet feil under beregning")
        raise HTTPException(
            status_code=500, detail="En uventet feil oppstod under beregningen."
        )

    return resultat


@app.post("/api/calculations", response_model=BeregningsResponse)
def opprett_beregning(forespørsel: BeregningsRequest):
    resultat = _utfor_beregning(forespørsel)
    return BeregningsResponse(
        sammendrag=BeregningsSammendrag(
            antall_beregnet=len(resultat.alle_resultater),
            antall_godkjent=len(resultat.godkjente),
            antall_underkjent=len(resultat.underkjente),
        ),
        resultat=resultat,
    )


@app.post("/api/calculations/plots")
def opprett_grafer(forespørsel: BeregningsRequest):
    resultat = _utfor_beregning(forespørsel)
    try:
        return {"grafer": lag_grafer_for_ui(resultat)}
    except Exception:
        logger.exception("Uventet feil under generering av grafer")
        raise HTTPException(status_code=500, detail="Kunne ikke lage grafene for beregningen.")
