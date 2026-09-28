from agent.config import load_settings


def test_empty_groq_model_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://example.test")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "key")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "shopfast-incidents")
    monkeypatch.setenv("GROQ_API_KEY", "key")
    monkeypatch.setenv("GROQ_MODEL", "")
    assert load_settings().groq_model == "openai/gpt-oss-120b"
