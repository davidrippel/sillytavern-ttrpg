from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class BriefError(ValueError):
    pass


class GenreBrief(BaseModel):
    pack_name: str
    display_name: str
    schema_version: int
    one_line_pitch: str
    tone_keywords: list[str] = Field(default_factory=list)
    attribute_flavor: str
    resource_flavor: str
    ability_categories_hint: str
    thematic_pillars_hint: str | None = None
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
        if value != 1:
            raise ValueError(f"unsupported schema_version {value}; only 1 is supported")
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
    return GenreBrief.model_validate(raw)
