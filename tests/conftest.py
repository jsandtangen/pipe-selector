import pytest


@pytest.fixture(autouse=True)
def sla_av_ai_i_tester(monkeypatch):
    """Rapporttester skal aldri bruke en ekte API-nøkkel fra utviklermiljøet."""
    monkeypatch.setenv("PIPESELECTOR_AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
