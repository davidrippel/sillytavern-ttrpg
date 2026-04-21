from __future__ import annotations

import os
from pathlib import Path

from .env import load_project_dotenv

DEFAULT_MODEL_FALLBACK = "anthropic/claude-sonnet-4.5"
DRY_RUN_MODEL_FALLBACK = "anthropic/claude-haiku-4.5"
DEFAULT_TEMPERATURE_FALLBACK = 0.8
OPENROUTER_API_URL_FALLBACK = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_TIMEOUT_SECONDS_FALLBACK = 120.0
OPENROUTER_MAX_RETRIES_FALLBACK = 3
STAGE_MAX_RETRIES_FALLBACK = 3


def _get_env_str(name: str, fallback: str) -> str:
    load_project_dotenv()
    return os.getenv(name, fallback)


def _get_env_optional_str(name: str) -> str | None:
    load_project_dotenv()
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value


def _get_env_int(name: str, fallback: int) -> int:
    load_project_dotenv()
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return int(value)


def _get_env_float(name: str, fallback: float) -> float:
    load_project_dotenv()
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return float(value)


def get_default_model() -> str:
    return _get_env_str("CAMPAIGN_GENERATOR_DEFAULT_MODEL", DEFAULT_MODEL_FALLBACK)


def get_dry_run_model() -> str:
    return _get_env_str("CAMPAIGN_GENERATOR_DRY_RUN_MODEL", DRY_RUN_MODEL_FALLBACK)


def get_default_temperature() -> float:
    return _get_env_float("CAMPAIGN_GENERATOR_DEFAULT_TEMPERATURE", DEFAULT_TEMPERATURE_FALLBACK)


def get_openrouter_api_url() -> str:
    return _get_env_str("OPENROUTER_API_URL", OPENROUTER_API_URL_FALLBACK)


def get_openrouter_timeout_seconds() -> float:
    return _get_env_float("OPENROUTER_TIMEOUT_SECONDS", OPENROUTER_TIMEOUT_SECONDS_FALLBACK)


def get_openrouter_max_retries() -> int:
    return _get_env_int("OPENROUTER_MAX_RETRIES", OPENROUTER_MAX_RETRIES_FALLBACK)


def get_stage_max_retries() -> int:
    return _get_env_int("CAMPAIGN_GENERATOR_STAGE_MAX_RETRIES", STAGE_MAX_RETRIES_FALLBACK)


def get_genres_base_dir() -> Path | None:
    value = _get_env_optional_str("CAMPAIGN_GENERATOR_GENRES_BASE_DIR")
    return Path(value).expanduser().resolve() if value else None


def get_campaigns_base_dir() -> Path | None:
    value = _get_env_optional_str("CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR")
    return Path(value).expanduser().resolve() if value else None
