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
    assert brief.schema_version == 2
    assert "gritty" in brief.tone_keywords
    assert brief.pressure_flavor.strip()
    assert brief.advantages_disadvantages_hint.strip()
    assert brief.complications_hint.strip()


def test_pack_name_must_be_snake_case() -> None:
    with pytest.raises(Exception):
        GenreBrief(
            pack_name="Space-Opera",
            display_name="Space Opera",
            schema_version=2,
            one_line_pitch="x",
            tone_keywords=["a"],
            pressure_flavor="x",
            advantages_disadvantages_hint="x",
            complications_hint="x",
        )


def test_load_brief_missing_required_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "pack_name: x\n"
        "display_name: x\n"
        "schema_version: 2\n"
        "one_line_pitch: x\n"
        "tone_keywords: [a]\n"
        # pressure_flavor missing
        "advantages_disadvantages_hint: x\n"
        "complications_hint: x\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_brief(bad)


def test_load_brief_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(BriefError):
        load_brief(bad)


def test_load_brief_rejects_v1_legacy_fields(tmp_path: Path) -> None:
    """v1 briefs carried attribute_flavor / resource_flavor / ability_categories_hint;
    the v2 pipeline rejects them with a migration hint instead of silently ignoring."""
    bad = tmp_path / "v1.yaml"
    bad.write_text(
        "pack_name: x\n"
        "display_name: X\n"
        "schema_version: 2\n"
        "one_line_pitch: x\n"
        "tone_keywords: [a]\n"
        "pressure_flavor: x\n"
        "advantages_disadvantages_hint: x\n"
        "complications_hint: x\n"
        "attribute_flavor: leftover\n",
        encoding="utf-8",
    )
    with pytest.raises(BriefError, match="retired v1 fields"):
        load_brief(bad)


def test_load_brief_rejects_v1_schema_version(tmp_path: Path) -> None:
    bad = tmp_path / "v1_schema.yaml"
    bad.write_text(
        "pack_name: x\n"
        "display_name: X\n"
        "schema_version: 1\n"
        "one_line_pitch: x\n"
        "tone_keywords: [a]\n"
        "pressure_flavor: x\n"
        "advantages_disadvantages_hint: x\n"
        "complications_hint: x\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="unsupported brief schema_version"):
        load_brief(bad)
