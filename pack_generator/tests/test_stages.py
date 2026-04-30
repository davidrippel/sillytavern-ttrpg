from __future__ import annotations

import json
from pathlib import Path

from common.llm import ReplayLLMClient
from common.validation import ValidationLog
from pack_generator.brief import load_brief
from pack_generator.schemas import AttributesDraft, ResourcesDraft, ToneAndPillars
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
