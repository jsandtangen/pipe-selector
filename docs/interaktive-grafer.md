# Interaktive grafer

Frontend er fortsatt vanlig HTML, CSS og JavaScript. Plotly.js Basic 3.1.0
ligger lokalt i `static/vendor/`, med MIT-lisens. Ingen CDN, React, byggesteg,
Plotly-konto eller ekstern grafserver kreves ved bruk av appen.

## Data og beregninger

Tidligere sendte `/api/calculations/plots` Matplotlib-grafer som base64-PNG.
Dette endepunktet og CLI-grafene beholdes for bakoverkompatibilitet.
Nettleseren bruker nå `/api/calculations/interactive-plots`, som returnerer
Plotly-spesifikasjoner fra `visualisering.py`. Kurvene bruker den eksisterende
`beregn_ledningskarakteristikk_data` og grensepunktene bruker
`finn_krysning_q`. Resultatene kommer fortsatt fra `tjenester.py`.

Samlet graf bruker samme 1-450 l/s-domene og samme regel for tykk linje som
tidligere. Individuelle grafer bruker 1-400 l/s og referansene 150/300 l/s.
Hver kurve og hvert punkt har Q, totalt tap, hastighet og skjærspenning i hover.
Prisgrafen viser godkjente alternativer, eller alle beregnede rør hvis ingen
er godkjent. Løftehøyde er nå eksplisitt i hover, og kurvefargene identifiserer
samme rør gjennom alle grafene. Kravkontroll og rangeringslogikk er uendret.

## Tekstbokser og state

Annotasjonens `x`/`y` er datapunktet. `ax`/`ay` er tekstboksens separate
visuelle forskyvning i piksler. Bare `annotationTail` er redigerbar;
datapunkt, tekst og beregningsverdier kan ikke flyttes eller redigeres.
Forbindelseslinjen tegnes av Plotly. Standardplasseringen fordeler boksene i
kolonner over selve kurveområdet, med økt grafhøyde ved mange bokser.

`static/graphs.js` lagrer kurvesynlighet, zoom og annotasjoner i en begrenset
Map i nettleserens minne, nøstet etter graf-ID, beregningsinput og rørvalg.
Samme graf kan rendres på nytt uten å miste oppsettet. Nye forutsetninger
eller rørvalg får egen state. Oppsettet overlever ikke omlasting av siden.
Ved endret vindusbredde fordeles standardbokser på nytt; manuelt flyttede
bokser beholder forskyvningen, men begrenses til grafens ytterkanter.
Ved zoom/panorering begrenses også boksene til bildet for å unngå klipping.
Tilbakestilling av zoom og tekstbokser er separate handlinger.

## PDF og grafeksport

Rapportknappen vises etter vellykket plotting. Ved nedlasting bruker
`Plotly.toImage` de aktive grafene direkte, inkludert zoom, skjulte kurver og
flyttede bokser. PNG-bildene eksporteres med dobbel pikseloppløsning og sendes
med rapportforespørselen. API-et validerer PNG-format, størrelse og at graf-ID-ene
stemmer med det valgte rørutvalget. `rapport_pdf.py` bygger bildene direkte inn
i ReportLab-rapporten, uten å regenerere disse grafene med standardoppsett.
Eksisterende tabeller, forutsetninger og supplerende sammenligningsdiagrammer
beholdes. API-klienter som ikke sender grafeksport får fortsatt eldre standardgrafer.

PDF bruker rasterbilder for å unngå en ny SVG-konverteringsavhengighet og
forskjeller i tekst/font-rendering. «Last ned SVG» gir separat vektoreksport
fra hver graf. Høye grafer med mange tekstbokser skaleres til én A4-side og
kan gi liten tekst i PDF, særlig hvis de eksporteres fra en smal mobilvisning.
Større nettleservindu gir et mer kompakt oppsett før eksport.

## Kontroller

Kjør Python-testene med `python -m pytest` og JavaScript-kontrollene med
`node --test tests/test_graphs.cjs`. Sistnevnte tester egen state- og
plasseringslogikk med en Plotly-testdobbel; de erstatter ikke nettlesertesting.
Testene dekker 1/3/5 rør, tre skjermbredder, standardplassering, flytting,
zoom, ny rendering, endret rørvalg, grafutvalg og bruk av eksakte innsendte
bilder i PDF. Direkte pointer-/touch-testing og visuell Plotly-kontroll må
utføres i en tilgjengelig nettleser; nettlesertilgang manglet i implementeringsøkten.
