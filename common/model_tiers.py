"""Two-tier model routing.

Each pipeline stage is tagged with a tier ("primary" or "cheap"); the
tier resolves to a concrete OpenRouter model id via env vars (or
built-in fallbacks). A per-run global override (CLI ``--model`` or
seed ``model:`` field) skips tier resolution and applies the same
model to every stage.

Resolution precedence (highest first):

  1. ``global_override`` — CLI ``--model`` flag or seed/brief ``model:``.
  2. ``overrides[stage_name]`` — seed/brief ``stage_models:`` map. Values
     may be ``"primary"`` / ``"cheap"`` (resolved via env) or a literal
     OpenRouter id.
  3. ``tier_map[stage_name]`` — the pipeline's hardcoded default tier.
  4. ``"primary"`` as the final fallback.
"""
from __future__ import annotations

import os

from .env import load_project_dotenv

PRIMARY_MODEL_ENV = "PRIMARY_MODEL"
CHEAP_MODEL_ENV = "CHEAP_MODEL"
DEFAULT_PRIMARY = "anthropic/claude-sonnet-4.6"
DEFAULT_CHEAP = "deepseek/deepseek-v3.2"

TIER_NAMES = frozenset({"primary", "cheap"})


def resolve_tier(tier: str) -> str:
    """Resolve a tier name to a concrete OpenRouter model id.

    "primary" → ``$PRIMARY_MODEL`` or ``$CAMPAIGN_GENERATOR_DEFAULT_MODEL``
    (legacy) or :data:`DEFAULT_PRIMARY`.
    "cheap"   → ``$CHEAP_MODEL`` or :data:`DEFAULT_CHEAP`.
    Anything else is returned unchanged (treated as a literal model id).
    """
    load_project_dotenv()
    if tier == "primary":
        return (
            os.getenv(PRIMARY_MODEL_ENV)
            or os.getenv("CAMPAIGN_GENERATOR_DEFAULT_MODEL")
            or DEFAULT_PRIMARY
        )
    if tier == "cheap":
        return os.getenv(CHEAP_MODEL_ENV) or DEFAULT_CHEAP
    return tier


def resolve_stage_model(
    stage_name: str,
    tier_map: dict[str, str],
    *,
    overrides: dict[str, str] | None = None,
    global_override: str | None = None,
) -> str:
    if global_override:
        return global_override
    if overrides and stage_name in overrides:
        return resolve_tier(overrides[stage_name])
    return resolve_tier(tier_map.get(stage_name, "primary"))


def is_anthropic_model(model: str) -> bool:
    return model.startswith("anthropic/")
