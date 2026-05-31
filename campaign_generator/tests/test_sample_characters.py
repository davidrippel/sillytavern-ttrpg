from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from common.validation import ValidationLog

from campaign_generator.schemas import SampleCharacterSet
from campaign_generator.stages import sample_characters
from campaign_generator.validation import validate_cross_stage


def _character(name: str) -> dict:
    return {
        "name": name,
        "concept": "A grounded protagonist with a personal reason to investigate.",
        "advantages": ["Patient observer", "Knows the old roads"],
        "disadvantages": ["Owes a dangerous favor"],
        "belongings": ["A worn map", "A brass key", "A patched coat"],
        "relationships": [],
        "hook_into_campaign": "Visible NPC asked for help at the Old Gate.",
    }


def test_sample_character_retries_name_collision_with_hidden_npc(monkeypatch, tmp_path: Path) -> None:
    prompts: list[dict] = []
    responses = [
        SampleCharacterSet.model_validate({"characters": [_character("Hidden NPC")]}),
        SampleCharacterSet.model_validate({"characters": [_character("Distinct Hero")]}),
    ]

    def fake_generate_structured(**kwargs):
        prompts.append(json.loads(kwargs["user_prompt"]))
        return responses.pop(0)

    monkeypatch.setattr(sample_characters, "generate_structured", fake_generate_structured)

    result = sample_characters.run(
        client=SimpleNamespace(),
        system_prompt="prompt",
        pack=SimpleNamespace(
            metadata=SimpleNamespace(pack_name="test_pack", display_name="Test Pack"),
            advantages_disadvantages="vocabulary",
            character_template=SimpleNamespace(model_dump=lambda: {}),
        ),
        premise=SimpleNamespace(model_dump=lambda: {}),
        plot=SimpleNamespace(model_dump=lambda: {}),
        factions=SimpleNamespace(factions=[]),
        npcs=SimpleNamespace(
            npcs=[
                SimpleNamespace(name="Visible NPC"),
                SimpleNamespace(name="Hidden NPC"),
            ]
        ),
        locations=SimpleNamespace(locations=[SimpleNamespace(name="Old Gate")]),
        seed=SimpleNamespace(num_sample_characters=1, protagonist_archetype=None, protagonist_known_facts=[]),
        model="test-model",
        temperature=0.0,
        validation_log=ValidationLog(tmp_path / "validation_log.txt"),
        known_npc_names={"Visible NPC"},
    )

    assert result.characters[0].name == "Distinct Hero"
    assert prompts[0]["npcs"] == [{"name": "Visible NPC"}]
    assert prompts[0]["forbidden_npc_names"] == ["Hidden NPC", "Visible NPC"]
    assert "duplicates an NPC name" in prompts[1]["repair_note"]


def test_cross_stage_validation_rejects_sample_character_npc_name_collision() -> None:
    errors = validate_cross_stage(
        plot=SimpleNamespace(),
        factions=SimpleNamespace(factions=[]),
        npcs=SimpleNamespace(
            npcs=[
                SimpleNamespace(
                    name="Hidden NPC",
                    faction_affiliation=None,
                    relationships=[],
                )
            ]
        ),
        locations=SimpleNamespace(locations=[]),
        truths=SimpleNamespace(truths=[]),
        sample_characters=SampleCharacterSet.model_validate(
            {"characters": [_character("Hidden NPC")]}
        ),
    )

    assert errors == ["Sample character 'Hidden NPC' duplicates an NPC name"]
