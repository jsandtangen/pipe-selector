# Pumpeledningskalkulator

Verktøy for hydraulisk dimensjonering og anbefaling av pumpeledninger (typisk
sjøledninger for avløp). Beregner vannhastighet, friksjonstap, singulærtap,
skjærspenning og pris for alle DN/SDR-kombinasjoner i en rørkatalog, og
anbefaler et rør blant de som oppfyller kravene.

Finnes som:

- et lokalt kommandolinjeprogram (`main.py`)
- et lokalt HTTP-API (`api.py`, FastAPI) - tenkt som grunnlag for en senere
  nettleserbasert frontend

## Innhold

- [Installasjon](#installasjon)
- [Kjøre kommandolinjeprogrammet](#kjøre-kommandolinjeprogrammet)
- [Kjøre API-et](#kjøre-apiet)
- [Kjøre testene](#kjøre-testene)
- [Prosjektstruktur](#prosjektstruktur)
- [Formler og enheter](#formler-og-enheter)
- [Inndata: obligatorisk, standardverdi eller systemverdi](#inndata-obligatorisk-standardverdi-eller-systemverdi)
- [Rørkatalogens format](#rørkatalogens-format)
- [Rangeringsstrategier](#rangeringsstrategier)
- [Kjente begrensninger og videre arbeid](#kjente-begrensninger-og-videre-arbeid)
- [Fremtidig frontend](#fremtidig-frontend)

## Installasjon

Krever Python 3.10 eller nyere.

```bash
pip install -r requirements.txt
```

## Kjøre kommandolinjeprogrammet

```bash
python main.py
```

Leser `data/RØR.csv`, beregner alle DN/SDR-kombinasjoner for SDR-klassene og
prosjektverdiene som er satt øverst i `main()`, skriver resultatet til
terminalen, eksporterer oppdrift/lodd-tabeller til `resultater/`, og lagrer
plott (uten å åpne interaktive vinduer som standard - se
[Kjente begrensninger](#kjente-begrensninger-og-videre-arbeid)).

Qdim, ledningslengde og tillatte SDR-klasser har **ingen standardverdi** i
koden og må settes eksplisitt i `main()` for hver kjøring/hvert prosjekt -
se [Inndata](#inndata-obligatorisk-standardverdi-eller-systemverdi).

## Kjøre API-et

```bash
uvicorn api:app --reload
```

**Enkelt brukergrensesnitt** (skjema med avkrysning for SDR-klasser, valg av
rangeringsstrategi, resultatvisning):

```text
http://127.0.0.1:8000/ui/
```

Én statisk HTML-fil (`static/index.html`, ren HTML/CSS/JavaScript, ingen
byggverktøy) som henter standardverdier og rørkatalogens SDR-klasser fra
API-et og kaller `POST /api/calculations`.

Teknisk dokumentasjon og utprøving av rå JSON (Swagger UI):

```text
http://127.0.0.1:8000/docs
```

### Endepunkter

| Metode | Sti | Beskrivelse |
|---|---|---|
| GET | `/` | Grunnleggende info |
| GET | `/health` | Helsesjekk |
| GET | `/api/defaults` | Faglige standardverdier + hvilke felt som er obligatoriske |
| GET | `/api/pipe-catalog/options` | DN- og SDR-verdier som faktisk finnes i rørkatalogen |
| POST | `/api/calculations` | Kjør en beregning |

Eksempel på request-body til `POST /api/calculations`:

```json
{
  "input": {
    "qdim_l_s": 300.0,
    "lengde_m": 10250.0,
    "tillatte_sdr": [13.6, 17.0]
  },
  "rangering": {
    "strategi": "billigste_godkjent"
  }
}
```

`input` følger `modeller.BeregningsInput` og `rangering` følger
`modeller.RangeringsValg` - se [Rangeringsstrategier](#rangeringsstrategier)
for de fire strategiene og deres felt.

## Kjøre testene

```bash
pytest
```

72+ tester dekker hydraulikkformlene, rørkatalog-innlesing/validering,
referansetilfellet (Qdim=300 l/s, L=10250 m → DN560 SDR17), alle fire
rangeringsstrategiene, tjenestelaget og API-et.

## Prosjektstruktur

```text
APPLICATION/
├── data/
│   └── RØR.csv                  Rørkatalog (kildedata)
├── resultater/                  Genererte plott/eksporter (ikke versjonert)
├── tests/                       Automatiske tester (pytest)
├── modeller.py                  Datamodeller (BeregningsInput, RangeringsValg, RorResultat, ...)
├── hydraulikk.py                Rene hydrauliske formler
├── oppdrift_lodd.py             Oppdrift, betonglodd og pris per DN/SDR
├── data_io.py                   Innlesing, kolonnekanonisering og validering av rørkatalogen
├── beregninger.py               Beregner + kravkontrollerer alle DN/SDR-alternativer
├── rangering.py                 Velger anbefalt rør blant de godkjente
├── tjenester.py                 Koordinerer katalog + beregning + rangering til ett resultat
├── eksport.py                   CSV/Excel-eksport av oppdrift/lodd-tabeller
├── plotting.py                  Alle plott
├── config.py                    Filstier (CSV_FIL, OUTPUT_MAPPE)
├── main.py                      Lokalt kommandolinjeprogram
├── api.py                       FastAPI-api
└── requirements.txt
```

## Formler og enheter

Alle formler er implementert i `hydraulikk.py` som rene funksjoner (ingen
fil-I/O, ingen globale variabler).

**Vannhastighet** `v = Q / (π · d_i² / 4)` — `v` [m/s], `Q` [m³/s], `d_i` innvendig diameter [m]

**Reynolds-tall** `Re = v · d_i / ν` — `ν` kinematisk viskositet [m²/s]

**Friksjonsfaktor (Colebrook-White)**, løst iterativt for turbulent strømning (`Re ≥ 2300`):

```text
1/√f = -2·log10( (k/d_i)/3.7 + 2.51/(Re·√f) )
```

For laminær strømning (`Re < 2300`) brukes `f = 64/Re`.

**Friksjonstap** `Hf = f · L/d_i · v² / (2g)` — [m]

**Singulærtap** `St = Tk · v² / (2g)` — [m], `Tk` = sum singulærtapskoeffisienter

**Totalt tap** `H_total = Hf + St` — [m]. Statisk løftehøyde inngår **ikke** i denne verdien.

**Skjærspenning** `τ = γ · d_i · Hf / (4·L)` — [Pa] (= [N/m²])

**Tillatt trykk (trykklasse)** `p = 2σ / (SDR - 1)` — [MPa], `σ` = dimensjonerende ringspenning/materialspenning [MPa]. Trykket fra totalt tap (`γ · H_total`, konvertert til bar) må ikke overstige dette - se [Absolutte krav](#rangeringsstrategier).

**Trykkavhengig maks. utvendig diameter** `D_max = 100 mm · (1 + 2 · 6,3 MPa / p_design)` — `p_design` beregnes fra kandidatens totale tap og konverteres fra bar til MPa. Kandidater med `DN/OD > D_max` forkastes. Denne grensen er et eget absolutt krav; den erstatter ikke SDR-trykklassekontrollen.

**Pris** (mer detaljert enn en enkel `kg/m × pris`-formel - se `oppdrift_lodd.py`):
rørkostnad (`kg/m fra katalog × pris_ror_kr_per_kg`) + loddkostnad (beregnet
nødvendig betongloddvekt fra netto oppdrift × `pris_lodd_kr_per_kg`) +
sjøleggekostnad, fordelt på lengde i sjø og på land.

## Inndata: obligatorisk, standardverdi eller systemverdi

`modeller.BeregningsInput` skiller mellom tre kategorier felt:

**A. Obligatorisk prosjektinput (ingen standardverdi)** - må oppgis eksplisitt for hvert prosjekt:

| Felt | Beskrivelse |
|---|---|
| `qdim_l_s` | Dimensjonerende vannmengde [l/s] |
| `lengde_m` | Total ledningslengde [m] |
| `tillatte_sdr` | Hvilke SDR-klasser som er tillatt å vurdere |

`tillatte_sdr` har bevisst ingen standardverdi: hvilke SDR-/trykklasser som
er strukturelt egnet varierer fra prosjekt til prosjekt, og en fast
systemstandard ville silently kunne anbefale et rør med feil trykklasse
for et gitt prosjekt.

**B. Faglige standardverdier** (forhåndsutfylt, kan overstyres per prosjekt):

| Felt | Standardverdi |
|---|---|
| `ruhet_mm` | 0,5 mm |
| `kinematisk_viskositet_m2_s` | 0,000001309 m²/s |
| `sum_singulaertapskoeffisienter` (Tk) | 5,0 |
| `maks_totalt_tap_m` | 70 m |
| `min_hastighet_m_s` | 1,0 m/s |
| `min_skjaerspenning_pa` | 2,0 Pa |
| `pris_ror_kr_per_kg` | 60 kr/kg |
| `pris_lodd_kr_per_kg` | 8 kr/kg |
| `pris_legging_sjo_kr_per_kg` | 0 kr/kg |
| `lengde_land_m` | 0 m |
| `qdim_kilde` | `"manual"` |
| `dimensjonerende_ringspenning_mpa` (σ) | 8,0 MPa (PE100, C=1,25 iht. EN 12201) |

**C. Systemverdier** (avanserte fysiske konstanter, sjelden endret):
`gravitasjon_m_s2` (9,81), `spesifikk_vekt_vann_n_m3` (9806,65),
`rho_avlop_kg_m3` (1000), `rho_pe_kg_m3` (980), `rho_saltvann_kg_m3` (1030),
`rho_lodd_kg_m3` (2360), `luftfylling_andel` (0,60).

Kjør `GET /api/defaults` for å hente standardverdiene og listen over
obligatoriske felt maskinlesbart.

## Rørkatalogens format

`data/RØR.csv` er semikolonseparert med norsk desimaltegn (komma). Første
kolonne må hete `DN/OD` (eller `DN/OD <enhet>`, f.eks. `DN/OD [mm]`).
Deretter ett kolonnepar per SDR-klasse:

```text
SDR <verdi> Veggtykkelse [mm]   (eller "(mm)")
SDR <verdi> Vekt [kg/m]         (eller "kg/m")
```

SDR-klassene leses dynamisk fra kolonnenavnene (`data_io.finn_sdr_liste_fra_katalog`)
- ingen SDR-verdi eller DN-verdi er hardkodet i beregningslogikken. Katalogen
kan derfor utvides med nye rør eller SDR-klasser uten kodeendring.

Katalogen valideres ved innlesing:

- **Duplikate DN-verdier stopper beregningen** (`data_io.sjekk_ingen_duplikate_dn`) - tvetydig hvilken rad som er riktig.
- **Mistenkte feilrader rapporteres, men stopper ikke beregningen** (`data_io.valider_rorkatalog`) - f.eks. urimelig veggtykkelse for en gitt DN/SDR, eller at bare én av veggtykkelse/vekt er oppgitt. Manglende DN/SDR-kombinasjoner (katalogen kan være glissen) regnes ikke som en feil.

> **Kjent begrensning:** `er_veggtykkelse_rimelig()` sin plausibilitetssjekk
> (± 50 % av `DN/SDR`) er ikke kalibrert for små DN (≤ 40 mm), hvor PE-rør har
> en produksjonsteknisk minste veggtykkelse som gjør at DN/SDR-formelen
> undervurderer forventet veggtykkelse. Dette filtrerer i praksis bort disse
> radene fra beregningen. Uten betydning for dimensjoner som faktisk er
> aktuelle for pumpeledninger (DN500+), men bør kalibreres bedre dersom
> katalogen skal brukes til mindre DN.

## Rangeringsstrategier

Absolutte krav avgjør godkjent/underkjent i `beregninger.py`:

- `vannhastighet ≥ min_hastighet_m_s`
- `τ ≥ min_skjaerspenning_pa`
- `totalt tap ≤ maks_totalt_tap_m`
- **utvendig diameter ≤ trykkavhengig D_max** (`D_max = 100 mm · (1 + 2 · 6,3 MPa / p_design)`), der dimensjonerende trykk fra kandidatens totale tap konverteres fra bar til MPa.
- **trykket fra totalt tap ≤ rørets tillatte trykk** (`p = 2σ/(SDR-1)`, se
  [Formler og enheter](#formler-og-enheter)) - hindrer at et rør som er
  hydraulisk godkjent, men fysisk uegnet (f.eks. et tynnvegget høy-SDR-rør
  som ikke tåler trykket fra beregnet løftehøyde), likevel anbefales. Lagt
  til 2026-08-06 etter at brukeren observerte at et DN500 SDR41-rør ble
  foreslått selv om det bare tåler ca. 4 bar.

Underkjente rør får eksplisitte `avviksarsaker`. Blant de **godkjente**
rørene velger `rangering.velg_anbefaling` anbefalt rør etter valgt strategi
(`modeller.RangeringsValg.strategi`):

| Strategi | Oppførsel |
|---|---|
| `billigste_godkjent` | Laveste pris blant godkjente rør. |
| `best_hydraulisk` | Leksikografisk sortering på en brukervalgt, prioritert rekkefølge av hydrauliske marginer (`hydraulisk_prioritet`: `margin_totalt_tap`, `margin_skjaerspenning`, `margin_hastighet`). Ingen innebygd definisjon av "best" - brukeren velger selv hvilke mål som teller og i hvilken rekkefølge. |
| `balansert` | Vektet score med fast forhåndsutfylt vekting: 50 % pris, 25 % hastighet, 25 % skjærspenning. |
| `egendefinert_vekting` | Samme vektede scoremodell, med brukervalgte vekter (`vekter`). Vilkårlige positive vekter normaliseres automatisk - trenger ikke summere til 1,0 eller 100 %. |

**Normaliseringsmetode** for vektet score (`balansert`/`egendefinert_vekting`):
hvert mål skaleres til [0, 1] med min-maks-normalisering *innenfor settet av
godkjente rør* i den aktuelle beregningen (dårligste = 0, beste = 1). Gir
0,5 til alle dersom alle verdier er like (unngår 0/0). Total score er en
vektet sum av delscorene. **Totalt tap inngår bevisst ikke** som et vektet
mål i denne versjonen - kun som absolutt krav.

## Kjente begrensninger og videre arbeid

Bevisst ikke bygget i denne fasen (se `CLAUDE_CODE_PLAN_PUMPELEDNINGSAPP.md` §16):

- Automatisk Qdim fra kommunale Excel-filer, kartbasert Qdim, matrikkel-/adresseoppslag
- Microsoft Entra ID, produksjonsserver/Azure-oppsett
- Database for prosjektlagring, flerbrukertilgang
- Full frontend (se [Fremtidig frontend](#fremtidig-frontend))
- Trykklasse håndteres nå som et absolutt krav (`p = 2σ/(SDR-1)`, se over),
  med `σ` som en overstyrbar standardverdi (ikke hardkodet materiale/prosjekt-
  antakelse) - i tillegg til at brukeren fortsatt velger `tillatte_sdr` selv
  per prosjekt.
- Interaktiv flytting av informasjonsbokser i plott (planens §11.3) - plottene
  har automatisk (roterende) plassering av annotasjoner, men ikke
  drag-and-drop. Sannsynligvis bedre løst i en fremtidig nettleser-frontend
  enn i lokal Matplotlib.
- Lokalisering av strukturell inndatavalidering i API-et: `POST /api/calculations`
  returnerer pydantic/FastAPIs standard (engelske) 422-feilmeldinger ved
  ugyldig/manglende JSON-felt. Forretningsfeil (f.eks. ukjent SDR-klasse)
  returneres derimot alltid på norsk (HTTP 400).
- `main.py` bruker fortsatt `beregninger.py`/`rangering.py` direkte i stedet
  for `tjenester.beregn_pumpeledning` - en liten gjenværende duplisering
  mellom CLI- og API-veien som trygt kan ryddes opp i senere.

## Fremtidig frontend

Tenkt dataflyt (jf. planens §4), ikke implementert i denne fasen:

```text
Bruker/frontend → FastAPI-endepunkt → validering (pydantic) →
tjenester.beregn_pumpeledning → hydraulikk.py + rørkatalog →
strukturert, JSON-kompatibelt resultat (modeller.BeregningsResultat)
```

`api.py` er allerede tynt (kun validering + kall til tjenestelaget), og
`modeller.py` sine pydantic-modeller er delt mellom CLI, API og tester - en
frontend kan bygges direkte mot `POST /api/calculations` uten endringer i
beregningsmotoren.
#   p i p e - s e l e c t o r 
 
 