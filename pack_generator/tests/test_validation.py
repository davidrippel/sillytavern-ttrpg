"""Schema-level validation tests for the v2 pack generator.

These tests pin the input contracts of the pydantic schemas in
``pack_generator.schemas`` so the LLM-driven stages cannot silently
ship a pack with structurally bad output.
"""
from __future__ import annotations

import pytest

from pack_generator.schemas import (
    AdvantagesDisadvantagesDraft,
    ComplicationsDraft,
    ExampleHooksDraft,
    GeneratorSeedDraft,
    GMOverlay,
    ToneAndPillars,
    VocabAxis,
)


# --- Tone --------------------------------------------------------------


def test_tone_pillars_count_bounds() -> None:
    payload = {
        "setting_statement": "two sentences here. and another sentence. and a third.",
        "pillars": [{"title": "x", "description": "y"}] * 2,
        "content_to_include": ["a"],
        "content_to_avoid": ["b"],
    }
    with pytest.raises(Exception):
        ToneAndPillars.model_validate(payload)


# --- GM overlay --------------------------------------------------------


def _overlay_payload(section_filler: str) -> dict:
    return {
        "setting_and_tone": section_filler,
        "thematic_pillars": section_filler,
        "resolving_actions": section_filler,
        "translating_pressures": section_filler,
        "npc_conventions": section_filler,
        "content_to_include": section_filler,
        "content_to_avoid": section_filler,
        "character_creation": section_filler,
    }


def test_gm_overlay_rejects_excessive_word_count() -> None:
    long_section = "padding " * 250  # 250 words/section * 8 = 2000 words > 1800
    with pytest.raises(Exception, match="word count"):
        GMOverlay.model_validate(_overlay_payload(long_section))


def test_gm_overlay_accepts_reasonable_length() -> None:
    short_section = "this is a reasonable section. " * 10
    GMOverlay.model_validate(_overlay_payload(short_section))


def test_gm_overlay_rejects_leaked_stat_mode_language() -> None:
    payload = _overlay_payload("reasonable text here. " * 10)
    payload["resolving_actions"] = (
        "The GM calls for a 2d6 roll when the outcome is uncertain. " * 10
    )
    with pytest.raises(Exception, match="retired stat-mode language"):
        GMOverlay.model_validate(payload)


def test_gm_overlay_rejects_plus_one_language() -> None:
    payload = _overlay_payload("reasonable text here. " * 10)
    payload["character_creation"] = "Give a +1 to the chosen attribute. " * 10
    with pytest.raises(Exception, match="retired stat-mode language"):
        GMOverlay.model_validate(payload)


# --- Complications -----------------------------------------------------


def _good_complication(i: int) -> dict:
    return {
        "title": f"Concrete complication {i}.",
        "body": (
            f"A specific named character or place reacts in a way that escalates the situation "
            f"for the protagonist (#{i})."
        ),
    }


def _good_cost(i: int) -> dict:
    return {"text": f"Success, but the protagonist owes someone a favor (#{i})."}


def test_complications_requires_min_entries() -> None:
    payload = {
        "complications": [_good_complication(i) for i in range(8)],
        "success_costs": [_good_cost(i) for i in range(7)],
    }
    with pytest.raises(Exception, match="10-15"):
        ComplicationsDraft.model_validate(payload)


def test_complications_rejects_vague_phrases() -> None:
    bad = _good_complication(0)
    bad["body"] = "Something bad happens and the players figure it out themselves."
    payload = {
        "complications": [bad, *[_good_complication(i) for i in range(1, 11)]],
        "success_costs": [_good_cost(i) for i in range(7)],
    }
    with pytest.raises(Exception, match="vague phrase"):
        ComplicationsDraft.model_validate(payload)


def test_complications_accepts_valid_payload() -> None:
    payload = {
        "complications": [_good_complication(i) for i in range(12)],
        "success_costs": [_good_cost(i) for i in range(8)],
    }
    ComplicationsDraft.model_validate(payload)


# --- Advantages / disadvantages ----------------------------------------


def _axis(title: str, n_entries: int) -> dict:
    return {
        "title": title,
        "entries": [f"{title} concrete entry number {i}" for i in range(n_entries)],
    }


def test_vocab_axis_rejects_short_entry() -> None:
    with pytest.raises(Exception, match="too vague"):
        VocabAxis.model_validate({"title": "Bodily", "entries": ["strong", "fast", "wise", "lucky"]})


def test_advantages_disadvantages_total_counts() -> None:
    payload = {
        "advantage_axes": [
            _axis("Bodily", 4),
            _axis("Knowledge", 4),
            _axis("Social", 4),
        ],  # 12 entries — below 20 minimum
        "disadvantage_axes": [
            _axis("Marked", 5),
            _axis("Bound", 5),
            _axis("Hunted", 5),
        ],
    }
    with pytest.raises(Exception, match="advantages total"):
        AdvantagesDisadvantagesDraft.model_validate(payload)


def test_advantages_disadvantages_accepts_valid_payload() -> None:
    payload = {
        "advantage_axes": [
            _axis("Bodily", 7),
            _axis("Knowledge", 7),
            _axis("Mystical", 7),
            _axis("Social", 4),
        ],  # 25 entries
        "disadvantage_axes": [
            _axis("Marked", 5),
            _axis("Wounded", 5),
            _axis("Bound", 5),
            _axis("Hunted", 5),
        ],  # 20 entries
    }
    AdvantagesDisadvantagesDraft.model_validate(payload)


# --- Example hooks -----------------------------------------------------


def test_example_hooks_rejects_hook_without_choice() -> None:
    payload = {
        "hooks": [
            {"title": "h1", "body": "A scene plays out and resolves cleanly with no further input needed."},
            {"title": "h2", "body": "Another scene that simply describes events. The end."},
        ]
    }
    with pytest.raises(Exception, match="moment of choice"):
        ExampleHooksDraft.model_validate(payload)


def test_example_hooks_accepts_question_ending() -> None:
    payload = {
        "hooks": [
            {"title": "h1", "body": "A scene unfolds with rising tension. What do you do?"},
            {"title": "h2", "body": "The deal goes wrong; everyone is staring at you. Your move?"},
        ]
    }
    ExampleHooksDraft.model_validate(payload)


# --- Generator seed ----------------------------------------------------


def _seed(**overrides) -> dict:
    payload = {
        "setting_anchors": ["specific_anchor_one", "specific_anchor_two"],
        "themes_include": ["found_family", "salvage_economics"],
        "themes_exclude": ["military_jingoism"],
        "tone": ["gritty", "hopeful"],
        "antagonist_archetypes_preferred": ["corp_factor", "cultist", "rival_captain"],
    }
    payload.update(overrides)
    return payload


def test_generator_seed_rejects_include_exclude_overlap() -> None:
    payload = _seed(themes_include=["grimdark"], themes_exclude=["grimdark", "military"])
    with pytest.raises(Exception, match="overlap"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_rejects_tone_exclude_overlap() -> None:
    payload = _seed(tone=["grim"], themes_exclude=["grimdark"])
    with pytest.raises(Exception, match="tone"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_rejects_too_few_antagonists() -> None:
    payload = _seed(antagonist_archetypes_preferred=["solo_villain", "solo villain"])
    with pytest.raises(Exception, match="at least 3 distinct"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_rejects_cliche_anchor() -> None:
    payload = _seed(setting_anchors=["the_frontier", "specific_anchor_two"])
    with pytest.raises(Exception, match="too generic"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_rejects_one_token_anchor() -> None:
    payload = _seed(setting_anchors=["frontier", "specific_anchor_two"])
    with pytest.raises(Exception, match="too generic"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_accepts_valid_payload() -> None:
    payload = _seed(setting_anchors=["nexus_station_omega", "rust_belt_outpost"])
    GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_rejects_count_out_of_range() -> None:
    payload = _seed(num_truths=2)
    with pytest.raises(Exception, match="out of expected range"):
        GeneratorSeedDraft.model_validate(payload)
