from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False, encoding="utf-8-sig")
CSV_FIL = BASE_DIR / "data" / "RØR.csv"
OUTPUT_MAPPE = BASE_DIR / "resultater"
