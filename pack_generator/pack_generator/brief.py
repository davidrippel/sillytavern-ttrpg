from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class BriefError(ValueError):
    pass


SUPPORTED_BRIEF_SCHEMA_VERSION = 2


class GenreBrief(BaseModel):
    """Input to the pack generator (schema v2 — story-mode only).

    The brief is the human-authored description of the genre. The
    generator consumes it once at the start of the pipeline and the
    fields are referenced by name in stage prompts.

    v1 briefs (with ``attribute_flavor`` / ``resource_flavor`` /
    ``ability_categories_hint``) are rejected; the runtime no longer has
    attribute scores, resource pools, or ability slots, so those hints
    have nothing to drive. See examples/space_opera_brief.yaml for the
    v2 shape.
    """

    pack_name: str
    display_name: str
    schema_version: int
    one_line_pitch: str
    tone_keywords: list[str] = Field(default_factory=list)

    # The thematic spine of the genre — what the GM is meant to lean on.
    thematic_pillars_hint: str | None = None

    # The genre's signature accumulating pressure (corruption, sanity,
    # heat, ship damage, exposure). Authored as a paragraph: what the
    # pressure is, what feeds it, what the player sees when it climbs.
    pressure_flavor: str

    # Vocabulary hint for advantages_disadvantages.md — what axes the
    # genre uses (bodily / mystical / social, or crew-role / contacts /
    # heat, etc.), and 4-8 example phrases per axis.
    advantages_disadvantages_hint: str

    # Vocabulary hint for complications.md — the kinds of narrative
    # complications that fit the genre (church-takes-notice, heat-rises,
    # corruption-wells-up, ship-takes-damage). 6-10 examples.
    complications_hint: str

    content_to_avoid: list[str] = Field(default_factory=list)
    example_inspiration_list: str | None = None
    example_characters: str | None = None
    campaign_style_hint: str | None = None

    @field_validator("pack_name")
    @classmethod
    def _snake_case_pack_name(cls, value: str) -> str:
        if value != value.lower() or "-" in value or " " in value:
            raise ValueError("pack_name must be lowercase snake_case")
        return value

    @field_validator("schema_version")
    @classmethod
    def _supported_schema_version(cls, value: int) -> int:
        if value != SUPPORTED_BRIEF_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported brief schema_version {value}; only "
                f"v{SUPPORTED_BRIEF_SCHEMA_VERSION} is supported "
                f"(story-mode). v1 briefs carried attribute/resource/"
                f"ability hints that no longer apply."
            )
        return value

    @field_validator("tone_keywords")
    @classmethod
    def _at_least_one_tone_keyword(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("tone_keywords must contain at least one keyword")
        return value


def load_brief(path: str | Path) -> GenreBrief:
    brief_path = Path(path)
    if not brief_path.exists():
        raise BriefError(f"brief file not found: {brief_path}")
    with brief_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise BriefError(f"brief must be a YAML mapping, got {type(raw).__name__}")
    legacy_keys = sorted(
        set(raw) & {"attribute_flavor", "resource_flavor", "ability_categories_hint"}
    )
    if legacy_keys:
        raise BriefError(
            f"brief contains retired v1 fields: {legacy_keys}. "
            f"v2 briefs use pressure_flavor / advantages_disadvantages_hint / "
            f"complications_hint instead. See examples/space_opera_brief.yaml."
        )
    return GenreBrief.model_validate(raw)
