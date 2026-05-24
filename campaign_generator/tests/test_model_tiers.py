"""Tests for the two-tier model routing helpers."""
from __future__ import annotations

import pytest

from common import model_tiers
from common.llm import _build_messages


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Block the project's .env from re-populating the variables we're about
    # to clear — otherwise dotenv reloads them from disk and the tests
    # become non-hermetic on machines where developers have set tier
    # overrides.
    monkeypatch.setattr(model_tiers, "load_project_dotenv", lambda: None)
    monkeypatch.delenv(model_tiers.PRIMARY_MODEL_ENV, raising=False)
    monkeypatch.delenv(model_tiers.CHEAP_MODEL_ENV, raising=False)
    monkeypatch.delenv("CAMPAIGN_GENERATOR_DEFAULT_MODEL", raising=False)


def test_resolve_tier_primary_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert model_tiers.resolve_tier("primary") == model_tiers.DEFAULT_PRIMARY


def test_resolve_tier_primary_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(model_tiers.PRIMARY_MODEL_ENV, "openai/gpt-5")
    assert model_tiers.resolve_tier("primary") == "openai/gpt-5"


def test_resolve_tier_primary_falls_back_to_legacy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMPAIGN_GENERATOR_DEFAULT_MODEL", "anthropic/claude-sonnet-4.5")
    assert model_tiers.resolve_tier("primary") == "anthropic/claude-sonnet-4.5"


def test_resolve_tier_cheap_uses_default() -> None:
    assert model_tiers.resolve_tier("cheap") == model_tiers.DEFAULT_CHEAP


def test_resolve_tier_cheap_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(model_tiers.CHEAP_MODEL_ENV, "deepseek/deepseek-chat")
    assert model_tiers.resolve_tier("cheap") == "deepseek/deepseek-chat"


def test_resolve_tier_passthrough_for_literal_id() -> None:
    # Anything that isn't "primary"/"cheap" is treated as a literal model id.
    assert model_tiers.resolve_tier("openai/gpt-4o-mini") == "openai/gpt-4o-mini"


TIER_MAP = {"stage_a": "primary", "stage_b": "cheap"}


def test_resolve_stage_model_uses_tier_map() -> None:
    assert (
        model_tiers.resolve_stage_model("stage_a", TIER_MAP)
        == model_tiers.DEFAULT_PRIMARY
    )
    assert (
        model_tiers.resolve_stage_model("stage_b", TIER_MAP)
        == model_tiers.DEFAULT_CHEAP
    )


def test_resolve_stage_model_global_override_wins() -> None:
    resolved = model_tiers.resolve_stage_model(
        "stage_a",
        TIER_MAP,
        overrides={"stage_a": "cheap"},
        global_override="openai/gpt-5",
    )
    assert resolved == "openai/gpt-5"


def test_resolve_stage_model_per_stage_override_resolves_tier() -> None:
    # Tier-named overrides go through env resolution.
    resolved = model_tiers.resolve_stage_model(
        "stage_a",
        TIER_MAP,
        overrides={"stage_a": "cheap"},
    )
    assert resolved == model_tiers.DEFAULT_CHEAP


def test_resolve_stage_model_per_stage_override_literal() -> None:
    # Non-tier values pass through as literal model ids.
    resolved = model_tiers.resolve_stage_model(
        "stage_a",
        TIER_MAP,
        overrides={"stage_a": "openai/gpt-4o-mini"},
    )
    assert resolved == "openai/gpt-4o-mini"


def test_resolve_stage_model_unknown_stage_falls_back_to_primary() -> None:
    assert (
        model_tiers.resolve_stage_model("stage_z", TIER_MAP)
        == model_tiers.DEFAULT_PRIMARY
    )


def test_is_anthropic_model() -> None:
    assert model_tiers.is_anthropic_model("anthropic/claude-sonnet-4.6")
    assert not model_tiers.is_anthropic_model("deepseek/deepseek-v3.2")
    assert not model_tiers.is_anthropic_model("openai/gpt-5")


# ---------------------------------------------------------------------------
# Prompt-caching message shape
# ---------------------------------------------------------------------------


def test_build_messages_no_cache_prefix_uses_plain_string() -> None:
    messages = _build_messages(
        system_prompt="sys",
        user_prompt="user",
        cache_prefix=None,
        model="anthropic/claude-sonnet-4.6",
    )
    assert messages == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]


def test_build_messages_anthropic_with_prefix_uses_content_blocks() -> None:
    messages = _build_messages(
        system_prompt="sys",
        user_prompt="user",
        cache_prefix="cacheable-prefix",
        model="anthropic/claude-sonnet-4.6",
    )
    assert messages[0] == {"role": "system", "content": "sys"}
    user_msg = messages[1]
    assert user_msg["role"] == "user"
    blocks = user_msg["content"]
    assert isinstance(blocks, list)
    assert blocks[0]["text"] == "cacheable-prefix"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[1]["text"] == "user"
    assert "cache_control" not in blocks[1]


def test_build_messages_non_anthropic_concatenates_prefix() -> None:
    messages = _build_messages(
        system_prompt="sys",
        user_prompt="user",
        cache_prefix="prefix",
        model="deepseek/deepseek-v3.2",
    )
    assert messages[0] == {"role": "system", "content": "sys"}
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "prefix\n\nuser"
