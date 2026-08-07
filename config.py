from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_FIL = BASE_DIR / "data" / "RØR.csv"
OUTPUT_MAPPE = BASE_DIR / "resultater"

# Faglige standardverdier (ruhet, Tk, krav, priser, tettheter osv.) og
# obligatorisk prosjektinput (Qdim, ledningslengde, tillatte SDR-klasser)
# er samlet i modeller.BeregningsInput, ikke som frittstående konstanter
# her. Se modeller.py for gjeldende standardverdier og hvilke felt som
# må oppgis eksplisitt av bruker for hvert prosjekt.
