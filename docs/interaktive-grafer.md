# Interaktive grafer

Frontend bruker vanlig HTML, CSS og JavaScript. Plotly.js Basic 3.1.0
ligger lokalt i `static/vendor/`, med MIT-lisens. Ingen CDN, React,
byggesteg, Plotly-konto eller ekstern grafserver kreves.

## Arkitektur og beregningsgrunnlag

`visualisering.py` omformer eksisterende beregningsresultater til
Plotly-spesifikasjoner via `/api/calculations/interactive-plots`.
`beregn_ledningskarakteristikk_data` leverer kurvene og `finn_krysning_q`
leverer grensepunktene. Hydrauliske formler, kravkontroll, økonomi og
rangering er uendret. Det eldre `/api/calculations/plots` og CLI-grafene
beholdes for bakoverkompatibilitet.

Samlet graf beholder beregningsdomenet 1–450 l/s, individuelle grafer
1–400 l/s, med faste referanser ved 150 og 300 l/s. Standardutsnittet kan
være tettere enn beregningsdomenet. Grensepunkter og relevante referanser
inngår i valg av utsnitt; fullt beregningsområde er fortsatt tilgjengelig.
Brukerens egen zoom skal bevares gjennom interaksjoner.

Skjulte kurver kan gi automatisk tilpassing av standardutsnittet. Etter
at brukeren har zoomet selv, beholdes dette utsnittet til «Tilbakestill
visning». Inspektørkontroller beholder tastaturfokus når innholdet oppdateres.

Spesifikasjonene skiller mellom:

- `data`: kurver, gyldige segmenter og markører fra eksisterende beregninger.
- `layout`: standardakser og tekniske referanselinjer.
- `thresholdAnnotations`: direkte kravetiketter, uavhengige av festede bokser.
- `pipes`: røridentitet, farge, beregnede verdier ved Qdim og referansepunkter.
- `fullRange`: hele det beregnede kurveområdet.

Inspektørens Qdim-verdier kommer fra beregningsresultatet. Verdier på
kurven og ved interpolerte grensepunkter kommer fra det eksisterende
kurvegrunnlaget. Denne forskjellen skal ikke skjules ved å regne om
prosjektets resultater i frontend.

## Ett arbeidsområde

`static/index.html` leverer beregningsresultat og rapporthandling;
`static/analysis.js` orkestrerer rørvalg, faner og behovsstyrt grafoppretting.
`static/graphs.js` eier grafpresentasjon og interaksjonstilstand.
Pris, sammenligning og enkeltrør deler ett arbeidsområde med faner.
Den aktive visningen rendres ved behov; de øvrige spesifikasjonene
beholdes slik at både enkeltrør og eksport er tilgjengelige uten en lang
side med alle grafer samtidig.

Analyseområdet kommer etter anbefalingen og før den fulle resultattabellen.
Utvidet visning er en native modal dialog med den samme grafnoden; Escape
eller lukkeknappen returnerer til arbeidsområdet uten å bygge grafen på nytt.

En kompakt røroversikt erstatter den tradisjonelle Plotly-legenden.
Søk gjør større utvalg håndterbare. Peker/fokus fremhever en kurve
midlertidig, valg åpner tekniske verdier, og en separat synlighetsknapp
viser/skjuler hele rørgruppen. Disse handlingene skal ikke blandes.
Andre synlige alternativer dempes ved fremheving og forsvinner ikke.
Enkeltrør velges i samme arbeidsområde.

Inspektøren viser relevante tall med enheter, og referansepunktene har
tastaturtilgjengelige handlinger for festing av tekstbokser. Vesentlige
verdier er derfor tilgjengelige uten hover. Den innebygde
Plotly-verktøylinjen er skjult for å unngå doble kontroller. Egne kontroller
gir zoom, tilbakestilling og utvidet visning; sekundære handlinger samles
i en meny. Utvidet visning bruker samme graf og tilstand.

## Annotasjoner og tilstand

Standardvisningen har markører og kompakte hoverdetaljer, uten en fast
samling tekstbokser. Klikk på et datapunkt fester eller fjerner en boks.
Referansepunkter kan også festes fra inspektøren. Flere bokser får en
forutsigbar lokal plassering som forsøker å redusere overlapping.

Annotasjonens `x`/`y` forblir det tekniske datapunktet. Tekstboksens
`ax`/`ay` er en separat visuell forskyvning i piksler. Bare boksen kan
flyttes; beregningsverdier og punktets koordinater kan ikke redigeres.
Plotly tegner forbindelseslinjen. Kravetiketter er separate fra
brukerens festede bokser og skal ikke skjules av handlingen for tekstbokser.

Zoom, kurvesynlighet, festede punkter og manuelle forskyvninger lagres
per graf, input og rørutvalg i nettleserminnet. Fanebytte og utvidelse skal
ikke nullstille dem. Nye beregningsforutsetninger får egen tilstand.
Tilstanden overlever ikke omlasting av siden.

Bokser begrenses visuelt til tilgjengelig plass ved endret størrelse,
zoom og panorering. Den lagrede manuelle forskyvningen holdes separat
fra den midlertidige begrensningen, slik at den opprinnelige plasseringen
kan gjenopprettes når det er plass igjen. Tilbakestilling av zoom og
boksplassering er separate handlinger. Mange samtidig festede bokser kan
fortsatt overlappe i små grafer; automatisk plassering er bevisst enkel.

## SVG og PDF

Rapportknappen vises etter vellykket «Plott valgte rør», før
analyseområdet. Endres rørutvalget, kreves ny plotting før rapporten blir
tilgjengelig igjen.

Eksport bygger på samme spesifikasjoner og tilstand som arbeidsområdet.
Alle nødvendige grafer tas med, også faner og enkeltrør som ikke har vært
åpnet. Besøkte grafer bruker lagret zoom, kurvesynlighet og festede bokser;
ubesøkte grafer bruker standardoppsettet. Eksport skal ikke montere alle
grafene i den synlige siden.

Eksportdata rekonstrueres fra kanoniske kurvestiler. Midlertidig
fremheving ved peker, fokus eller inspeksjonsvalg inngår ikke i statiske
bilder. Brukerens eksplisitte kurvesynlighet bevares. Kontroller og
HTML-inspektør eksporteres ikke; bildene får en egen kompakt rørlegend.
Kravetiketter og festede bokser beholdes. Det levende grafoppsettet skal
ikke endres av eksport.

SVG gir separat vektoreksport. PDF bruker PNG med dobbel pikseloppløsning
fra `Plotly.toImage`. API-et validerer bildeformat, størrelse og at graf-ID-ene
stemmer nøyaktig med valgt rørutvalg. `rapport_pdf.py` bygger bildene direkte
inn i ReportLab-rapporten uten å tegne dem på nytt med et annet standardoppsett.
API-klienter uten innsendte bilder får fortsatt de eldre rapportgrafene.

Rapporten beholder beregningsgrunnlag, kravkontroll, resultattabeller,
supplerende sammenligningsdiagrammer og en egen tabell med alle opprinnelige
referansepunkter: rør, punkttype, Q, totalt tap, v og τ. Tabellen er uavhengig
av hvilke kurver eller tekstbokser som er synlige i de eksporterte bildene.
Kravverdiene dokumenteres også i kravkontroll og beregningsvedlegg.
Et renere grensesnitt skal derfor ikke fjerne teknisk rapportinformasjon.

## Kontroll og begrensninger

Kjør Python-testene med `python -m pytest` og JavaScript-kontrollene med
`node --test tests/test_graphs.cjs`. I prosjektets Windows-miljø brukes
`.venv/Scripts/python.exe` dersom `python` ikke finnes i PATH.

Python-kontrollene dekker uendrede kurvedata, grenser, referanseverdier,
grafmetadata, API-validering, innbygging av eksakte eksportbilder og
rapporttabellenes fullstendighet. `tests/test_export_completeness.py`
kontrollerer at både faste referanser og grensepunkter fortsatt finnes i
rapporttabellen med 1 og 5 rør selv om innsendte grafbilder er helt blanke.

JavaScript-testene bruker en Plotly-testdobbel for kontroller og tilstand.
De verifiserer applikasjonens egen logikk, men dokumenterer ikke faktisk
nettleserrendering, pikselplassering eller Plotlys draoperasjoner.

I implementeringsmiljøet kunne den offisielle Windows Computer Use-klienten
finne Chrome-vinduet med PipeSelector. Skjermbildeinnhenting ble deretter
stoppet fordi klienten ikke kunne verifisere nettleserens gjeldende URL med
tilstrekkelig sikkerhet. Derfor foreligger ingen ny skjermbildebasert eller
manuell pointer-/touch-verifikasjon fra denne økten. Direkte visuell QA må
utføres i en tilgjengelig nettleser.
