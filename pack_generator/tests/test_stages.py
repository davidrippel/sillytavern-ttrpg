from __future__ import annotations

import json
from pathlib import Path

from common.llm import ReplayLLMClient
from common.validation import ValidationLog
from pack_generator.brief import load_brief
import pytest

from pack_generator.schemas import (
    AbilityCategoriesDraft,
    AttributesDraft,
    ResourcesDraft,
    ToneAndPillars,
)
from pack_generator.brief import GenreBrief
from pack_generator.schemas import AbilityCatalogDraft, FailureMovesDraft, ToneAndPillars
from pack_generator.stages import (
    ability_catalog as ability_catalog_stage,
)
from pack_generator.stages import (
    ability_categories as ability_categories_stage,
)
from pack_generator.stages import (
    failure_moves as failure_moves_stage,
)
from pack_generator.stages import (
    tone_and_pillars as tone_stage_mod,
)
from pack_generator.stages import (
    attributes as attributes_stage,
)
from pack_generator.stages import (
    character_template as character_template_stage,
)
from pack_generator.stages import (
    tone_and_pillars as tone_stage,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "canned_llm_responses" / "space_opera"
EXAMPLE_BRIEF = REPO_ROOT / "pack_generator" / "examples" / "space_opera_brief.yaml"


def test_tone_and_pillars_stage_uses_replay(tmp_path: Path) -> None:
    brief = load_brief(EXAMPLE_BRIEF)
    client = ReplayLLMClient.from_fixture_dir(FIXTURES)
    log = ValidationLog(tmp_path / "log.txt")
    result = tone_stage.run(
        client=client,
        system_prompt="(test prompt)",
        brief=brief,
        model="replay",
        temperature=0.0,
        validation_log=log,
    )
    assert isinstance(result, ToneAndPillars)
    assert 3 <= len(result.pillars) <= 5


def test_attributes_stage_produces_six_unique(tmp_path: Path) -> None:
    brief = load_brief(EXAMPLE_BRIEF)
    client = ReplayLLMClient.from_fixture_dir(FIXTURES)
    log = ValidationLog(tmp_path / "log.txt")
    # We need a tone to feed in; replay it first.
    tone = tone_stage.run(
        client=client,
        system_prompt="(test prompt)",
        brief=brief,
        model="replay",
        temperature=0.0,
        validation_log=log,
    )
    attributes = attributes_stage.run(
        client=client,
        system_prompt="(test prompt)",
        brief=brief,
        tone=tone,
        model="replay",
        temperature=0.0,
        validation_log=log,
    )
    assert isinstance(attributes, AttributesDraft)
    keys = [a.key for a in attributes.attributes]
    assert len(keys) == 6 == len(set(keys))


def _attrs_for_orphan_test() -> AttributesDraft:
    return AttributesDraft.model_validate(
        {
            "attributes": [
                {"key": k, "display": k.title(), "description": f"{k} domain", "examples": [f"{k}-a", f"{k}-b"]}
                for k in ("grit", "edge", "wits", "resolve", "charm", "knack")
            ]
        }
    )


def _resources_with_orphan() -> ResourcesDraft:
    return ResourcesDraft.model_validate(
        {
            "resources": [
                {"key": "hp_current", "display": "HP", "kind": "pool", "starting_value": 10, "max_value_field": "hp_max"},
                {"key": "hp_max", "display": "HP Max", "kind": "static_value", "starting_value": 10},
                {"key": "heat", "display": "Heat", "kind": "counter", "starting_value": 0},
                {"key": "exposure", "display": "Exposure", "kind": "counter", "starting_value": 0},
            ]
        }
    )


def test_ability_categories_rejects_orphan_resource(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    attrs = _attrs_for_orphan_test()
    resources = _resources_with_orphan()
    # categories reference 'heat' but never 'exposure' — exposure is an orphan
    categories = AbilityCategoriesDraft.model_validate(
        {
            "categories": [
                {
                    "key": "skills",
                    "display": "Skills",
                    "description": "d",
                    "activation": "active",
                    "roll_attribute": "knack",
                    "consequence_on_failure": "hp_current: -1",
                },
                {
                    "key": "stealth",
                    "display": "Stealth",
                    "description": "d",
                    "activation": "active",
                    "roll_attribute": "edge",
                    "consequence_on_failure": "heat: +1",
                },
                {
                    "key": "rest",
                    "display": "Rest",
                    "description": "d",
                    "activation": "passive",
                },
            ]
        }
    )
    with pytest.raises(ValueError, match="orphan resource"):
        ability_categories_stage._validate_cross_references(categories, attrs, resources, log)


def test_ability_categories_accepts_referenced_resources(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    attrs = _attrs_for_orphan_test()
    resources = _resources_with_orphan()
    categories = AbilityCategoriesDraft.model_validate(
        {
            "categories": [
                {
                    "key": "skills",
                    "display": "Skills",
                    "description": "d",
                    "activation": "active",
                    "roll_attribute": "knack",
                    "consequence_on_failure": "heat: +1",
                },
                {
                    "key": "delve",
                    "display": "Delve",
                    "description": "d",
                    "activation": "active",
                    "roll_attribute": "wits",
                    "consequence_on_failure": "exposure: +1",
                },
                {
                    "key": "rest",
                    "display": "Rest",
                    "description": "d",
                    "activation": "passive",
                },
            ]
        }
    )
    ability_categories_stage._validate_cross_references(categories, attrs, resources, log)


def _moves(*pairs: tuple[str, str]) -> FailureMovesDraft:
    return FailureMovesDraft.model_validate(
        {"moves": [{"title": t, "body": b} for t, b in pairs]}
    )


def test_failure_moves_rejects_vague_phrases(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    resources = _resources_with_orphan()
    moves = _moves(
        ("The hammer drops", "heat: +1 and a contact stops returning calls"),
        ("Bad luck", "Something bad happens to the protagonist"),
        ("Lights out", "hp_current: -1 from a sudden hazard"),
        ("Reroute", "A faction redirects a patrol toward the crew"),
        ("Pressure", "exposure: +1; the artifact hums louder"),
        ("Rumor", "A rival hears about the score and starts asking around"),
        ("Echo", "An NPC ally is wounded protecting the crew"),
        ("Breach", "heat: +1 and a station guard begins a sweep"),
    )
    with pytest.raises(ValueError, match="vague phrase"):
        failure_moves_stage._validate_move_quality(moves, resources, log)


def test_failure_moves_rejects_too_few_resource_references(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    resources = _resources_with_orphan()
    moves = _moves(
        ("a", "no resource here"),
        ("b", "still none"),
        ("c", "purely narrative"),
        ("d", "a contact arrives"),
        ("e", "a rival hears"),
        ("f", "an NPC suffers"),
        ("g", "the station closes"),
        ("h", "an ally is exposed"),
    )
    with pytest.raises(ValueError, match="reference a real resource"):
        failure_moves_stage._validate_move_quality(moves, resources, log)


def test_failure_moves_accepts_well_formed(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    resources = _resources_with_orphan()
    moves = _moves(
        ("Heat rises", "heat: +1 as a watcher takes notice"),
        ("Bleed", "hp_current: -1 from a glancing blow"),
        ("Mark", "exposure: +1; the artifact remembers"),
        ("Debt", "An old contact appears wanting payback"),
        ("Witness", "A bystander notes the scene for later use"),
        ("Pursuit", "heat: +1 and a hostile is en route"),
        ("Ally hit", "An NPC ally takes the consequence instead"),
        ("Cargo wrong", "Reveal a complication in the manifest"),
    )
    failure_moves_stage._validate_move_quality(moves, resources, log)


def _catalog_with(effects: list[str]) -> AbilityCatalogDraft:
    catalog = []
    for i in range(15):
        effect = effects[i] if i < len(effects) else "no mechanic"
        catalog.append(
            {"name": f"Ability {i}", "category": "skills", "description": "d", "effect": effect}
        )
    return AbilityCatalogDraft.model_validate({"catalog": catalog})


def test_ability_catalog_rejects_unknown_resource_key_in_effect(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    attrs = _attrs_for_orphan_test()
    resources = _resources_with_orphan()
    catalog = _catalog_with(["mana: +1 from invocation"])
    with pytest.raises(ValueError, match="unknown key 'mana'"):
        ability_catalog_stage._validate_effect_grammar(catalog, attrs, resources, log)


def test_ability_catalog_accepts_known_resource_in_effect(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    attrs = _attrs_for_orphan_test()
    resources = _resources_with_orphan()
    catalog = _catalog_with(["heat: +1 from a loud breach"])
    ability_catalog_stage._validate_effect_grammar(catalog, attrs, resources, log)


def test_ability_categories_flags_missing_weird_category(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    attrs = _attrs_for_orphan_test()
    resources = _resources_with_orphan()
    # brief hints at weird/magic but every category only burns hp
    brief = GenreBrief.model_validate(
        {
            "pack_name": "test",
            "display_name": "Test",
            "schema_version": 1,
            "one_line_pitch": "p",
            "tone_keywords": ["x"],
            "attribute_flavor": "f",
            "resource_flavor": "f",
            "ability_categories_hint": "Combat, skills, and magic — magic is the genre-defining weird category.",
        }
    )
    categories = AbilityCategoriesDraft.model_validate(
        {
            "categories": [
                {"key": "combat", "display": "Combat", "description": "d", "activation": "active",
                 "roll_attribute": "edge", "consequence_on_failure": "hp_current: -1"},
                {"key": "skills", "display": "Skills", "description": "d", "activation": "active",
                 "roll_attribute": "knack", "consequence_on_failure": "heat: +1"},
                {"key": "rest", "display": "Rest", "description": "d", "activation": "passive"},
            ]
        }
    )
    # heat IS non-HP so this should pass — let me make a stricter test where only hp is touched
    # Adjust: make all consequences hp_current
    categories = AbilityCategoriesDraft.model_validate(
        {
            "categories": [
                {"key": "combat", "display": "Combat", "description": "d", "activation": "active",
                 "roll_attribute": "edge", "consequence_on_failure": "hp_current: -1"},
                {"key": "skills", "display": "Skills", "description": "d", "activation": "active",
                 "roll_attribute": "knack", "consequence_on_failure": "hp_current: -1"},
                {"key": "rest", "display": "Rest", "description": "d", "activation": "passive"},
            ]
        }
    )
    # We also need the orphan check not to fire — drop heat & exposure from resources
    minimal_resources = ResourcesDraft.model_validate(
        {
            "resources": [
                {"key": "hp_current", "display": "HP", "kind": "pool", "starting_value": 10, "max_value_field": "hp_max"},
                {"key": "hp_max", "display": "HP Max", "kind": "static_value", "starting_value": 10},
                {"key": "armor", "display": "Armor", "kind": "counter", "starting_value": 0},
                {"key": "fatigue", "display": "Fatigue", "kind": "counter", "starting_value": 0},
            ]
        }
    )
    with pytest.raises(ValueError, match="weird|genre-defining"):
        ability_categories_stage._validate_cross_references(
            categories, attrs, minimal_resources, log, brief=brief
        )


def _minimal_brief(content_to_avoid: list[str]) -> GenreBrief:
    return GenreBrief.model_validate(
        {
            "pack_name": "test_pack",
            "display_name": "Test Pack",
            "schema_version": 1,
            "one_line_pitch": "A pitch.",
            "tone_keywords": ["gritty"],
            "attribute_flavor": "f",
            "resource_flavor": "f",
            "ability_categories_hint": "h",
            "content_to_avoid": content_to_avoid,
        }
    )


def _minimal_tone(content_to_avoid: list[str]) -> ToneAndPillars:
    return ToneAndPillars.model_validate(
        {
            "setting_statement": "A setting statement of at least fifteen words to satisfy the validator. " * 2,
            "pillars": [{"title": "p1", "description": "d"}, {"title": "p2", "description": "d"}, {"title": "p3", "description": "d"}],
            "content_to_include": ["a", "b"],
            "content_to_avoid": content_to_avoid,
        }
    )


def test_tone_stage_rejects_missing_brief_avoid_terms(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    brief = _minimal_brief(["military_jingoism", "racial_essentialism"])
    tone = _minimal_tone(["grimdark_nihilism"])
    with pytest.raises(ValueError, match="missing from generated"):
        tone_stage_mod._validate_brief_avoid_honored(tone, brief, log)


def test_tone_stage_accepts_normalized_match(tmp_path: Path) -> None:
    log = ValidationLog(tmp_path / "log.txt")
    brief = _minimal_brief(["military_jingoism"])
    # Normalization strips punctuation and underscores; "military jingoism" should match
    tone = _minimal_tone(["military jingoism", "other"])
    tone_stage_mod._validate_brief_avoid_honored(tone, brief, log)


def test_character_template_uses_attribute_and_resource_keys() -> None:
    with (FIXTURES / "attributes.json").open() as f:
        attributes = AttributesDraft.model_validate(json.load(f))
    with (FIXTURES / "resources.json").open() as f:
        resources = ResourcesDraft.model_validate(json.load(f))

    template = character_template_stage.build(attributes, resources)

    # All attribute keys present, all start at 0
    assert set(template["attributes"].keys()) == {a.key for a in attributes.attributes}
    assert all(value == 0 for value in template["attributes"].values())

    # State contains every resource key plus 'conditions'
    expected_state_keys = {r.key for r in resources.resources} | {"conditions"}
    assert set(template["state"].keys()) == expected_state_keys
    assert template["state"]["conditions"] == []
    # hp_current's starting value made it through
    assert template["state"]["hp_current"] == 10
