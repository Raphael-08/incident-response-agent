"""Loads configuration from environment variables. Fails fast when a required value is missing."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    hindsight_base_url: str
    hindsight_api_key: str
    hindsight_bank_id: str
    groq_api_key: str
    groq_model: str


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == "replace-me":
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    """Read settings from the environment (and a local .env file, if present)."""
    load_dotenv()
    return Settings(
        hindsight_base_url=_require("HINDSIGHT_BASE_URL"),
        hindsight_api_key=_require("HINDSIGHT_API_KEY"),
        hindsight_bank_id=os.getenv("HINDSIGHT_BANK_ID", "shopfast-incidents"),
        groq_api_key=_require("GROQ_API_KEY"),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    )
