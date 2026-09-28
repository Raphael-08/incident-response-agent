from agent.config import load_settings


def test_empty_groq_model_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://example.test")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "key")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "shopfast-incidents")
    monkeypatch.setenv("GROQ_API_KEY", "key")
    monkeypatch.setenv("GROQ_MODEL", "")
    assert load_settings().groq_model == "openai/gpt-oss-120b"


import pytest

from agent import config
from agent.config import ConfigError

REQUIRED = ["HINDSIGHT_BASE_URL", "HINDSIGHT_API_KEY", "GROQ_API_KEY"]


@pytest.fixture
def env(monkeypatch):
    """Valid environment, isolated from the real .env file."""
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for name in REQUIRED:
        monkeypatch.setenv(name, "value")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "shopfast-incidents")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    return monkeypatch


def test_valid_env_loads(env):
    settings = load_settings()
    assert settings.hindsight_bank_id == "shopfast-incidents"
    assert settings.groq_model == "openai/gpt-oss-120b"


@pytest.mark.parametrize("name", REQUIRED)
@pytest.mark.parametrize("value", [None, "", "   ", "replace-me"])
def test_missing_or_placeholder_secret_fails_fast(env, name, value):
    if value is None:
        env.delenv(name)
    else:
        env.setenv(name, value)
    with pytest.raises(ConfigError, match=name):
        load_settings()


@pytest.mark.parametrize("bank_id", ["", "ab", "Shopfast", "-shop", "shop_fast", "a" * 65])
def test_invalid_bank_id_rejected(env, bank_id):
    env.setenv("HINDSIGHT_BANK_ID", bank_id)
    with pytest.raises(ConfigError):
        load_settings()


def test_bank_id_override_wins_and_is_validated(env):
    assert load_settings("shopfast-incidents-demo3").hindsight_bank_id == "shopfast-incidents-demo3"
    with pytest.raises(ConfigError):
        load_settings("Bad Bank")
