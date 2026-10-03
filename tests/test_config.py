import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("filinnhold, eksisterende, forventet", [
    (None, {}, [None, None, None]),
    (
        "\ufeffPIPESELECTOR_AI_ENABLED=true\nOPENAI_API_KEY=test-placeholder-token\n"
        "OPENAI_MODEL=testmodell\n",
        {},
        ["true", "test-placeholder-token", "testmodell"],
    ),
    (
        "PIPESELECTOR_AI_ENABLED=true\nOPENAI_API_KEY=fil-token\nOPENAI_MODEL=filmodell\n",
        {"PIPESELECTOR_AI_ENABLED": "false", "OPENAI_API_KEY": "miljo-token", "OPENAI_MODEL": "miljomodell"},
        ["false", "miljo-token", "miljomodell"],
    ),
])
def test_env_lastes_ved_oppstart_fra_prosjektmappen(tmp_path, filinnhold, eksisterende, forventet):
    prosjektmappe = Path(__file__).resolve().parents[1]
    (tmp_path / "config.py").write_text(
        (prosjektmappe / "config.py").read_text(encoding="utf-8"), encoding="utf-8",
    )
    if filinnhold is not None:
        (tmp_path / ".env").write_text(filinnhold, encoding="utf-8")
    arbeidsmappe = tmp_path / "annen_mappe"
    arbeidsmappe.mkdir()
    miljo = os.environ.copy()
    for navn in ["PIPESELECTOR_AI_ENABLED", "OPENAI_API_KEY", "OPENAI_MODEL", "PYTHON_DOTENV_DISABLED"]:
        miljo.pop(navn, None)
    miljo.update(eksisterende)
    resultat = subprocess.run(
        [sys.executable, "-c",
         "import json, os, runpy, sys; runpy.run_path(sys.argv[1]); "
         "print(json.dumps([os.getenv(n) for n in "
         "['PIPESELECTOR_AI_ENABLED', 'OPENAI_API_KEY', 'OPENAI_MODEL']]))",
         str(tmp_path / "config.py")],
        cwd=arbeidsmappe, env=miljo, capture_output=True, text=True, check=True,
    )
    assert json.loads(resultat.stdout) == forventet
