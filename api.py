"""HTTP-endepunkter og statisk brukergrensesnitt for PipeSelector."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import BASE_DIR, CSV_FIL
from data_io import DN_OD_KOLONNE, finn_sdr_liste_fra_katalog, les_ror_csv
from modeller import BeregningsInput, BeregningsResultat, RangeringsValg, RorGrafValg, RorValg
from plotting import lag_grafer_for_ui
from rapport import lag_rapportdata
from rapport_ai import generer_faglig_vurdering
from rapport_pdf import lag_rapport_pdf
from grafeksport import GrafEksport
from visualisering import lag_interaktive_grafer
from tjenester import beregn_pumpeledning

logger = logging.getLogger("pumpeledningskalkulator")

app = FastAPI(
    title="Pumpeledningskalkulator",
    description="API for hydraulisk dimensjonering av pumpeledninger",
    version="0.1.0",
)

STATIC_MAPPE = BASE_DIR / "static"
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
    """Returnerer standardverdier og navnene på obligatoriske prosjektfelt."""
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


class GrafRequest(BeregningsRequest):
    vis_prisgraf: bool = True
    valgte_ror: list[RorGrafValg] | None = None


class RapportRequest(BeregningsRequest):
    valgte_ror: list[RorValg] = Field(default_factory=list)
    grafer: list[GrafEksport] | None = Field(default=None, max_length=64)


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
def opprett_grafer(forespørsel: GrafRequest):
    resultat = _utfor_beregning(forespørsel)
    try:
        return {"grafer": lag_grafer_for_ui(
            resultat,
            valgte_ror=forespørsel.valgte_ror,
            vis_prisgraf=forespørsel.vis_prisgraf,
        )}
    except ValueError as feil:
        raise HTTPException(status_code=400, detail=str(feil))
    except Exception:
        logger.exception("Uventet feil under generering av grafer")
        raise HTTPException(status_code=500, detail="Kunne ikke lage grafene for beregningen.")


@app.post("/api/calculations/interactive-plots")
def interaktive_grafer(foresporsel: GrafRequest):
    resultat = _utfor_beregning(foresporsel)
    try:
        return {"grafer": lag_interaktive_grafer(resultat, foresporsel.valgte_ror, foresporsel.vis_prisgraf)}
    except ValueError as feil:
        raise HTTPException(status_code=400, detail=str(feil))


@app.post("/api/calculations/report", response_class=Response,
          responses={200: {"content": {"application/pdf": {}}}})
def last_ned_rapport(foresporsel: RapportRequest):
    resultat = _utfor_beregning(foresporsel)
    try:
        rapportdata = lag_rapportdata(resultat, valgte_ror=foresporsel.valgte_ror)
        if foresporsel.grafer is not None:
            forventet = {"pris"}
            if rapportdata.sammenlignede_alternativer:
                forventet.add("samlet")
                forventet.update(f"ror-{r.dn_od_mm:g}-{r.sdr:g}" for r in rapportdata.sammenlignede_alternativer)
            ids = [graf.id for graf in foresporsel.grafer]
            if set(ids) != forventet or len(ids) != len(forventet):
                raise ValueError("Grafeksporten må inneholde alle grafene for det valgte rørutvalget.")
    except ValueError as feil:
        raise HTTPException(status_code=400, detail=str(feil))

    rapportdata.faglig_vurdering = generer_faglig_vurdering(rapportdata)
    try:
        pdf = (lag_rapport_pdf(rapportdata, grafer=foresporsel.grafer)
               if foresporsel.grafer is not None else lag_rapport_pdf(rapportdata))
    except Exception:
        logger.exception("Uventet feil under generering av rapport")
        raise HTTPException(status_code=500, detail="Kunne ikke lage rapporten for beregningen.")

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="pipeselector-rapport.pdf"'},
    )
