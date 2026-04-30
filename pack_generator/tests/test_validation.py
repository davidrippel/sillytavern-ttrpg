from __future__ import annotations

import pytest

from pack_generator.schemas import (
    AbilityCatalogDraft,
    AbilityCategoriesDraft,
    AttributesDraft,
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
