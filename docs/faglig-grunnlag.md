# Faglig grunnlag

Dette dokumentet beskriver beregningene i `hydraulikk.py`, `oppdrift_lodd.py`,
`beregninger.py` og `rangering.py`. Standardverdier og valideringsregler
ligger i `modeller.py`; API-et viser dem på `/docs` og `/api/defaults`.

## Inndata og enheter

Hver beregning krever `qdim_l_s`, `lengde_m` og `tillatte_sdr`.
Øvrige felt har overstyrbare standardverdier. UI-et forhåndsutfyller Qdim,
lengde og et SDR-utvalg, men disse verdiene er ikke API-standarder.

Vannmengde konverteres fra l/s til m³/s og diameter og ruhet fra mm til m
før hydraulikkberegningen. Kostnader oppgis i kr og MNOK.
`lengde_sjo_m=None` betyr at hele `lengde_m` regnes som sjølagt.
Sjø- og landlengder må derfor oppgis i samsvar med prosjektet når begge brukes.

## Hydraulikk

| Størrelse | Formel | Enhet |
|---|---|---|
| Innvendig diameter | `d_i = DN/OD * (1 - 2/SDR)` | Samme enhet som DN/OD |
| Vannhastighet | `v = Q / (pi * d_i² / 4)` | m/s |
| Reynolds-tall | `Re = v * d_i / nu` | Dimensjonsløst |
| Friksjonstap | `Hf = f * L/d_i * v² / (2g)` | m |
| Singulærtap | `St = Tk * v² / (2g)` | m |
| Totalt tap | `H_total = Hf + St` | m |
| Skjærspenning | `tau = gamma * d_i * Hf / (4L)` | Pa |
| Trykk fra totalt tap | `p = gamma * H_total / 100000` | bar |

Her er `nu` kinematisk viskositet [m²/s], `gamma` spesifikk vekt av vann
[N/m³], `Tk` sum singulærtapskoeffisienter og `g` gravitasjon [m/s²].
Statisk løftehøyde inngår ikke i totalt tap.

For `Re >= 2300` løses Colebrook-White iterativt for Darcy-friksjonsfaktoren:

```text
1/sqrt(f) = -2 * log10((k/d_i)/3.7 + 2.51/(Re * sqrt(f)))
```

For `Re < 2300` brukes `f = 64/Re`. Ruheten `k` er i meter.

## Oppdrift, ballast og kostnad

Rørets teoretiske egenvekt beregnes fra PE-tetthet og tverrsnittsarealet
mellom utvendig og innvendig diameter. Vekten av avløp følger vannfylt
innvendig volum, med vannfylling `1 - luftfylling_andel`.
Oppdriften følger utvendig fortrengt volum og saltvannstetthet.

```text
netto_oppdrift = max(0, oppdrift - vekt_pe - vekt_avlop)
vekt_lodd = netto_oppdrift * rho_lodd / (rho_lodd - rho_saltvann)
```

Verdiene oppgis som kg/m-ekvivalenter. Rørkostnaden bruker katalogens
kg/m, mens oppdriftsberegningen bruker teoretisk PE-vekt.
Sjøkostnaden inkluderer rør, lodd og sjølegging; landkostnaden inkluderer
rør. Excel-eksporten inneholder beregnede verdier, ikke regnearkformler.

## Kravkontroll

Et alternativ må oppfylle alle krav for å bli godkjent:

- Hastighet og skjærspenning minst lik prosjektets minimumsverdier.
- Totalt tap høyst lik prosjektets maksimumsverdi.
- Trykket fra totalt tap høyst lik tillatt SDR-trykk.
- DN/OD høyst lik den trykkavhengige diametergrensen.
- SDR høyst 19, i tillegg til å være valgt i `tillatte_sdr`.

Tillatt trykk beregnes som `p = 2 * sigma / (SDR - 1)` [MPa] og konverteres
til bar. Feltbeskrivelsen for `dimensjonerende_ringspenning_mpa` viser til
PE100 med sikkerhetsfaktor C=1,25 og EN 12201 som grunnlag for standardverdien
8,0 MPa. Materialspenningen kan overstyres for prosjektet.

Den separate diametergrensen er:

```text
D_max = 100 mm * (1 + 2 * 6.3 MPa / p_design)
```

`p_design` er kandidatens trykk fra totalt tap, konvertert til MPa.
Konstanten 6,3 MPa er separat fra den overstyrbare materialspenningen
i SDR-trykkontrollen. Underkjente alternativer får konkrete avviksårsaker.

## Rangering

| Strategi | Valg blant godkjente rør |
|---|---|
| `billigste_godkjent` | Lavest beregnet kostnad |
| `best_hydraulisk` | Brukerens prioriterte rekkefølge av hydrauliske marginer |
| `balansert` | 50 % pris, 25 % hastighet og 25 % skjærspenning |
| `egendefinert_vekting` | Brukerens positive vekter, normalisert til sum 1 |

Vektet rangering bruker min-maks-normalisering innenfor de godkjente
alternativene i beregningen. Lavere pris, høyere hastighet og høyere
skjærspenning gir høyere delscore. Like verdier får delscore 0,5.
Totalt tap inngår bare som krav, ikke som vektet mål.

## Rørkatalog

`data/RØR.csv` er semikolonseparert med desimalkomma. DN-kolonnen kan hete
`DN/OD` eller ha et enhetssuffiks, som `DN/OD [mm]`. SDR-klasser og
tilgjengelige dimensjoner oppdages fra katalogen. Hver SDR-klasse har
et kolonnepar for veggtykkelse [mm] og vekt [kg/m].

Duplikate positive DN/OD-verdier er en feil. En DN/SDR-kombinasjon med
begge verdier utelatt er tillatt; ufullstendige eller mistenkelige
kombinasjoner rapporteres av katalogvalideringen og utelates fra beregning
og eksport. Veggtykkelsen må være innenfor ±50 % av `DN/SDR`.
Denne sjekken kan avvise små PE-rør med produksjonsteknisk minimumstykkelse.

## Rapport

`rapport.py` bygger rapportgrunnlaget fra beregningsresultatet.
`rapport_pdf.py` viser forutsetninger, anbefaling, kravkontroll,
valgte godkjente alternativer og sammenligningsgrafer ved Qdim.
Rapportendepunktet kjører beregningen mot gjeldende katalog før PDF-en lages.
Valgfri AI-tekst i `rapport_ai.py` forklarer dette grunnlaget og er ikke
en uavhengig fagkontroll.
