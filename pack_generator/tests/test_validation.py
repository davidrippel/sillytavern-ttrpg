from __future__ import annotations

import pytest

from pack_generator.schemas import (
    AbilityCatalogDraft,
    AbilityCategoriesDraft,
    AbilityCategoryDraft,
    AttributesDraft,
    ExampleHooksDraft,
    GeneratorSeedDraft,
    GMOverlay,
    ResourcesDraft,
    ToneAndPillars,
)


def _attr(key: str, display: str | None = None, description: str | None = None) -> dict:
    return {
        "key": key,
        "display": display or key.title(),
        "description": description or f"Domain of {key} actions",
        "examples": [f"{key} example one", f"{key} example two"],
    }


def test_attributes_must_have_six_entries() -> None:
    with pytest.raises(Exception):
        AttributesDraft.model_validate({"attributes": [_attr(f"k{i}") for i in range(5)]})


def test_attributes_unique_keys() -> None:
    payload = {"attributes": [_attr("might"), _attr("might"), _attr("c"), _attr("d"), _attr("e"), _attr("f")]}
    with pytest.raises(Exception):
        AttributesDraft.model_validate(payload)


def test_attributes_distinct_descriptions() -> None:
    same = "the same domain"
    payload = {
        "attributes": [
            _attr("a", description=same),
            _attr("b", description=same),
            _attr("c"),
            _attr("d"),
            _attr("e"),
            _attr("f"),
        ]
    }
    with pytest.raises(Exception):
        AttributesDraft.model_validate(payload)


def test_resources_must_include_hp_pair() -> None:
    payload = {
        "resources": [
            {"key": "hp_current", "display": "HP", "kind": "pool", "starting_value": 10, "max_value_field": "hp_max"},
            # hp_max missing
            {"key": "stress", "display": "Stress", "kind": "counter", "starting_value": 0},
            {"key": "fuel", "display": "Fuel", "kind": "counter", "starting_value": 0},
        ]
    }
    with pytest.raises(Exception):
        ResourcesDraft.model_validate(payload)


def test_ability_catalog_size_bounds() -> None:
    too_few = {
        "catalog": [
            {"name": f"A{i}", "category": "x", "description": "d", "effect": "e"} for i in range(10)
        ]
    }
    with pytest.raises(Exception):
        AbilityCatalogDraft.model_validate(too_few)


def test_ability_catalog_unique_names() -> None:
    payload = {
        "catalog": [
            {"name": "Same", "category": "x", "description": "d", "effect": "e"},
            {"name": "Same", "category": "x", "description": "d", "effect": "e"},
            *[
                {"name": f"A{i}", "category": "x", "description": "d", "effect": "e"}
                for i in range(13)
            ],
        ]
    }
    with pytest.raises(Exception):
        AbilityCatalogDraft.model_validate(payload)


def test_tone_pillars_count_bounds() -> None:
    payload = {
        "setting_statement": "two sentences here. and another sentence. and a third.",
        "pillars": [{"title": "x", "description": "y"}] * 2,
        "content_to_include": ["a"],
        "content_to_avoid": ["b"],
    }
    with pytest.raises(Exception):
        ToneAndPillars.model_validate(payload)


def _category(
    key: str,
    *,
    activation: str = "active",
    roll_attribute: str | None = "wits",
    consequence_on_failure: str | None = None,
    consequence_on_partial: str | None = None,
) -> dict:
    payload = {
        "key": key,
        "display": key.title(),
        "description": f"{key} category",
        "activation": activation,
    }
    if roll_attribute is not None:
        payload["roll_attribute"] = roll_attribute
    if consequence_on_failure is not None:
        payload["consequence_on_failure"] = consequence_on_failure
    if consequence_on_partial is not None:
        payload["consequence_on_partial"] = consequence_on_partial
    return payload


def test_ability_category_rejects_identical_partial_and_failure_consequence() -> None:
    with pytest.raises(Exception, match="identical"):
        AbilityCategoryDraft.model_validate(
            _category(
                "old_tech",
                consequence_on_failure="exposure: +1",
                consequence_on_partial="exposure: +1",
            )
        )


def test_ability_category_accepts_different_partial_and_failure_consequence() -> None:
    AbilityCategoryDraft.model_validate(
        _category(
            "old_tech",
            consequence_on_failure="exposure: +2",
            consequence_on_partial="exposure: +1",
        )
    )


def test_ability_category_rejects_partial_harsher_than_failure() -> None:
    with pytest.raises(Exception, match="harsher"):
        AbilityCategoryDraft.model_validate(
            _category(
                "old_tech",
                consequence_on_failure="exposure: +1",
                consequence_on_partial="exposure: +3",
            )
        )


def test_ability_categories_rejects_collapsed_active_categories() -> None:
    payload = {
        "categories": [
            _category("alpha", consequence_on_failure="hp_current: -1"),
            _category("beta", consequence_on_failure="hp_current: -1"),
            _category("gamma", roll_attribute="grit", consequence_on_failure="ship_condition: -1"),
        ]
    }
    with pytest.raises(Exception, match="share the same"):
        AbilityCategoriesDraft.model_validate(payload)


def test_ability_categories_accepts_distinct_signatures() -> None:
    payload = {
        "categories": [
            _category("alpha", consequence_on_failure="hp_current: -1"),
            _category("beta", roll_attribute="grit", consequence_on_failure="hp_current: -1"),
            _category("gamma", roll_attribute="charm", consequence_on_failure="heat: +1"),
        ]
    }
    AbilityCategoriesDraft.model_validate(payload)


def _resource(key: str, kind: str, **extra) -> dict:
    payload = {"key": key, "display": key.title(), "kind": kind, "starting_value": 0}
    payload.update(extra)
    return payload


def test_resources_rejects_more_than_four_live_tracks() -> None:
    payload = {
        "resources": [
            _resource("hp_current", "pool", max_value_field="hp_max", starting_value=10),
            _resource("hp_max", "static_value", starting_value=10),
            _resource("heat", "counter"),
            _resource("stress", "counter"),
            _resource("supply", "counter"),
            _resource("morale", "counter"),
        ]
    }
    with pytest.raises(Exception, match="too many live"):
        ResourcesDraft.model_validate(payload)


def test_resources_accepts_four_live_tracks() -> None:
    payload = {
        "resources": [
            _resource("hp_current", "pool", max_value_field="hp_max", starting_value=10),
            _resource("hp_max", "static_value", starting_value=10),
            _resource("heat", "counter"),
            _resource("stress", "counter"),
            _resource("supply", "counter"),
        ]
    }
    ResourcesDraft.model_validate(payload)


def test_gm_overlay_rejects_excessive_word_count() -> None:
    long_section = "padding " * 250
    payload = {
        "setting_and_tone": long_section,
        "thematic_pillars": long_section,
        "attribute_guidance": long_section,
        "resource_mechanics": long_section,
        "ability_adjudication": long_section,
        "npc_conventions": long_section,
        "content_to_include": long_section,
        "content_to_avoid": long_section,
        "character_creation": long_section,
    }
    with pytest.raises(Exception, match="word count"):
        GMOverlay.model_validate(payload)


def test_gm_overlay_accepts_reasonable_length() -> None:
    short_section = "this is a reasonable section. " * 10
    payload = {
        "setting_and_tone": short_section,
        "thematic_pillars": short_section,
        "attribute_guidance": short_section,
        "resource_mechanics": short_section,
        "ability_adjudication": short_section,
        "npc_conventions": short_section,
        "content_to_include": short_section,
        "content_to_avoid": short_section,
        "character_creation": short_section,
    }
    GMOverlay.model_validate(payload)


def test_ability_categories_rejects_monoculture_activation() -> None:
    payload = {
        "categories": [
            _category("a", activation="active"),
            _category("b", activation="active", roll_attribute="grit"),
            _category("c", activation="active", roll_attribute="charm"),
            _category("d", activation="active", roll_attribute="edge"),
        ]
    }
    with pytest.raises(Exception, match="same activation"):
        AbilityCategoriesDraft.model_validate(payload)


def test_ability_categories_accepts_diverse_activation() -> None:
    payload = {
        "categories": [
            _category("a", activation="active"),
            _category("b", activation="active", roll_attribute="grit"),
            _category("c", activation="passive", roll_attribute=None),
            _category("d", activation="ritual", roll_attribute="wits"),
        ]
    }
    AbilityCategoriesDraft.model_validate(payload)


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


def test_generator_seed_accepts_three_distinct_antagonists() -> None:
    payload = _seed(antagonist_archetypes_preferred=["a", "b", "c"])
    GeneratorSeedDraft.model_validate(payload)


def test_ability_catalog_rejects_deep_prereq_chain() -> None:
    catalog = [
        {"name": "A", "category": "x", "description": "d", "effect": "e"},
        {"name": "B", "category": "x", "description": "d", "effect": "e", "prerequisite": "A"},
        {"name": "C", "category": "x", "description": "d", "effect": "e", "prerequisite": "B"},
        {"name": "D", "category": "x", "description": "d", "effect": "e", "prerequisite": "C"},
        {"name": "E", "category": "x", "description": "d", "effect": "e", "prerequisite": "D"},
    ]
    catalog.extend(
        {"name": f"X{i}", "category": "x", "description": "d", "effect": "e"} for i in range(11)
    )
    with pytest.raises(Exception, match="prerequisite chain depth"):
        AbilityCatalogDraft.model_validate({"catalog": catalog})


def test_ability_catalog_accepts_short_prereq_chain() -> None:
    catalog = [
        {"name": "A", "category": "x", "description": "d", "effect": "e"},
        {"name": "B", "category": "x", "description": "d", "effect": "e", "prerequisite": "A"},
        {"name": "C", "category": "x", "description": "d", "effect": "e", "prerequisite": "B"},
    ]
    catalog.extend(
        {"name": f"X{i}", "category": "x", "description": "d", "effect": "e"} for i in range(13)
    )
    AbilityCatalogDraft.model_validate({"catalog": catalog})


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


def test_generator_seed_rejects_cliche_anchor() -> None:
    payload = _seed(setting_anchors=["the_frontier", "specific_anchor_two"])
    with pytest.raises(Exception, match="too generic"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_rejects_one_token_anchor() -> None:
    payload = _seed(setting_anchors=["frontier", "specific_anchor_two"])
    with pytest.raises(Exception, match="too generic"):
        GeneratorSeedDraft.model_validate(payload)


def test_generator_seed_accepts_multi_token_anchor() -> None:
    payload = _seed(setting_anchors=["nexus_station_omega", "rust_belt_outpost"])
    GeneratorSeedDraft.model_validate(payload)


def test_ability_categories_minimum() -> None:
    with pytest.raises(Exception):
        AbilityCategoriesDraft.model_validate(
            {
                "categories": [
                    {
                        "key": "only",
                        "display": "Only",
                        "description": "d",
                        "activation": "passive",
                    }
                ]
            }
        )
