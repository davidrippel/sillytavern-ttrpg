from __future__ import annotations

from pathlib import Path

import pytest

from pack_generator.brief import BriefError, GenreBrief, load_brief


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_BRIEF = REPO_ROOT / "pack_generator" / "examples" / "space_opera_brief.yaml"


def test_load_example_brief_round_trip() -> None:
    brief = load_brief(EXAMPLE_BRIEF)
    assert isinstance(brief, GenreBrief)
    assert brief.pack_name == "space_opera_adventure"
    assert brief.schema_version == 1
    assert "gritty" in brief.tone_keywords
    assert brief.attribute_flavor.strip()
    assert brief.resource_flavor.strip()
    assert brief.ability_categories_hint.strip()


def test_pack_name_must_be_snake_case() -> None:
    with pytest.raises(Exception):
        GenreBrief(
            pack_name="Space-Opera",  # invalid: hyphen + capital
            display_name="Space Opera",
            schema_version=1,
            one_line_pitch="x",
            tone_keywords=["a"],
            attribute_flavor="x",
            resource_flavor="x",
            ability_categories_hint="x",
        )


def test_load_brief_missing_required_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "pack_name: x\n"
        "display_name: x\n"
        "schema_version: 1\n"
        "one_line_pitch: x\n"
        "tone_keywords: [a]\n"
        # attribute_flavor missing
        "resource_flavor: x\n"
        "ability_categories_hint: x\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_brief(bad)


def test_load_brief_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(BriefError):
        load_brief(bad)
