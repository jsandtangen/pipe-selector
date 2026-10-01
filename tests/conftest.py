import pytest


@pytest.fixture(autouse=True)
def sla_av_ai_i_tester(monkeypatch):
    """Rapporttester skal aldri bruke en ekte API-nøkkel fra utviklermiljøet."""
    monkeypatch.setenv("PIPESELECTOR_AI_ENABLED", "false")
