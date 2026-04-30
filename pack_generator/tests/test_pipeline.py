from __future__ import annotations

from pathlib import Path

import pytest

from common.llm import ReplayLLMClient
from common.pack import load_pack
from pack_generator.pipeline import run_pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "canned_llm_responses" / "space_opera"
EXAMPLE_BRIEF = REPO_ROOT / "pack_generator" / "examples" / "space_opera_brief.yaml"


def test_pipeline_replays_to_valid_pack(tmp_path: Path) -> None:
    client = ReplayLLMClient.from_fixture_dir(FIXTURES)
    output_dir = tmp_path / "space_opera_adventure"

    result = run_pipeline(
        brief_path=EXAMPLE_BRIEF,
        output_path=output_dir,
        model="replay-model",
        dry_run=False,
        stages="all",
        llm_client=client,
    )

    assert result.output_dir == output_dir.resolve()
    pack = load_pack(output_dir)
    assert pack.metadata.pack_name == "space_opera_adventure"
    assert len(pack.attributes.attributes) == 6
    assert {"hp_current", "hp_max"}.issubset({r.key for r in pack.resources.resources})
    assert 15 <= len(pack.abilities.catalog) <= 25
    assert pack.gm_prompt_overlay.strip()
    assert pack.review_checklist.strip()
    assert pack.failure_moves.strip()
    assert pack.example_hooks.strip()
    # generator_seed.yaml's genre key must equal pack_name (load_pack enforces this)


def test_pipeline_progress_callback_emits_stage_lines(tmp_path: Path) -> None:
    client = ReplayLLMClient.from_fixture_dir(FIXTURES)
    output_dir = tmp_path / "space_opera_adventure_progress"
    messages: list[str] = []

    run_pipeline(
        brief_path=EXAMPLE_BRIEF,
        output_path=output_dir,
        model="replay-model",
        dry_run=False,
        stages="all",
        llm_client=client,
        progress_callback=messages.append,
    )

    starting = [m for m in messages if m.startswith("Starting stage:")]
    completed = [m for m in messages if m.startswith("Completed stage:")]
    # 11 LLM stages + character_template = 12 stage lines
    assert len(starting) == 12, starting
    assert len(completed) == 12, completed
    # Final summary mentions duration and credits
    assert any("Pack generation finished" in m for m in messages)


def test_pipeline_refuses_non_empty_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "occupied"
    output_dir.mkdir()
    (output_dir / "stuff.txt").write_text("hello", encoding="utf-8")

    client = ReplayLLMClient.from_fixture_dir(FIXTURES)
    with pytest.raises(ValueError, match="not empty"):
        run_pipeline(
            brief_path=EXAMPLE_BRIEF,
            output_path=output_dir,
            stages="all",
            llm_client=client,
        )


def test_generated_pack_is_consumable_by_campaign_generator_validation(tmp_path: Path) -> None:
    """End-to-end check that the produced pack passes the campaign generator's pack validator."""
    client = ReplayLLMClient.from_fixture_dir(FIXTURES)
    output_dir = tmp_path / "consumable"

    run_pipeline(
        brief_path=EXAMPLE_BRIEF,
        output_path=output_dir,
        stages="all",
        llm_client=client,
    )

    # campaign_generator's pack module is the same module at common.pack now
    pack = load_pack(output_dir)
    # Spot-check that an attribute referenced by an ability category is in the attribute set
    attribute_keys = {a.key for a in pack.attributes.attributes}
    for category in pack.abilities.categories:
        roll_attr = getattr(category, "roll_attribute", None)
        if roll_attr is not None:
            assert roll_attr in attribute_keys, f"{category.key} roll_attribute {roll_attr} not in {attribute_keys}"
