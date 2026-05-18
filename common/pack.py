from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SUPPORTED_PACK_SCHEMA_VERSION = 2


class PackValidationError(ValueError):
    pass


class PackMetadata(BaseModel):
    schema_version: int
    pack_name: str
    display_name: str
    version: str
    description: str
    inspirations: list[str] = Field(default_factory=list)
    created: str | date | None = None
    updated: str | date | None = None
    author: str | None = None

    @field_validator("pack_name")
    @classmethod
    def validate_pack_name(cls, value: str) -> str:
        if value != value.lower() or "-" in value or " " in value:
            raise ValueError("pack_name must be lowercase snake_case")
        return value


class CharacterRelationship(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    tie: str


class CharacterTemplate(BaseModel):
    """Story-mode (schema v2) starting character shape.

    Stored on disk as ``character_template.json``. The extension uses this
    as the seed for a new character; players fill in the values.
    """

    name: str = ""
    concept: str = ""
    advantages: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    belongings: list[str] = Field(default_factory=list)
    relationships: list[CharacterRelationship] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _reject_legacy_keys(self) -> "CharacterTemplate":
        # Pydantic with extra="forbid" would do this; we check explicitly so
        # the error message is helpful when migrating v1 packs.
        return self


class NamingFile(BaseModel):
    """Optional naming-diversity hints for the campaign generator."""

    naming_registers: list[str] = Field(default_factory=list)
    district_flavors: list[str] = Field(default_factory=list)


class GenrePack(BaseModel):
    """Schema v2 pack: story-mode only.

    All runtime-injected text content (overlay, complications, reference)
    is loaded as raw markdown strings. The campaign generator embeds them
    into the lorebook as constant entries named ``__pack_gm_overlay``,
    ``__pack_complications``, and ``__pack_reference``.
    """

    path: Path
    metadata: PackMetadata
    character_template: CharacterTemplate
    gm_prompt_overlay: str
    tone: str
    complications: str
    advantages_disadvantages: str
    example_hooks: str
    generator_seed_defaults: dict[str, Any]
    review_checklist: str
    naming: NamingFile = Field(default_factory=NamingFile)


REQUIRED_PACK_FILES = {
    "pack.yaml",
    "character_template.json",
    "gm_prompt_overlay.md",
    "tone.md",
    "complications.md",
    "advantages_disadvantages.md",
    "example_hooks.md",
    "generator_seed.yaml",
    "REVIEW_CHECKLIST.md",
}

# Files that belonged to the retired v1 (stat-mode) pack schema. If any
# are present we tell the user to migrate or regenerate.
LEGACY_V1_FILES = {
    "attributes.yaml",
    "resources.yaml",
    "abilities.yaml",
    "failure_moves.md",
}

# Required GM overlay section headers (matched case-insensitively against
# ``## <Section>`` lines in gm_prompt_overlay.md).
REQUIRED_OVERLAY_SECTIONS = (
    "setting and tone",
    "thematic pillars",
    "resolving actions",
    "translating mechanical pressures",
    "npc conventions",
    "content to include",
    "content to avoid",
    "character creation",
)

# Fields the v1 ``generator_seed.yaml`` carried that no longer apply.
RETIRED_SEED_FIELDS = {"num_acts", "clue_chain_density", "branch_points"}

LEGACY_TEMPLATE_KEYS = {"attributes", "abilities", "equipment", "state"}


def _resolve_existing_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()

    search_roots = [Path.cwd().resolve(), *Path.cwd().resolve().parents]
    for root in search_roots:
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved
    return candidate.resolve()


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _check_required_overlay_sections(overlay_text: str) -> list[str]:
    lowered = overlay_text.lower()
    missing: list[str] = []
    for header in REQUIRED_OVERLAY_SECTIONS:
        # Accept the header anywhere as a ``## `` line.
        if f"## {header}" not in lowered:
            missing.append(header)
    return missing


def validate_pack_directory(path: Path) -> None:
    missing = sorted(name for name in REQUIRED_PACK_FILES if not (path / name).exists())
    if missing:
        raise PackValidationError(f"pack is missing required files: {missing}")
    legacy_present = sorted(name for name in LEGACY_V1_FILES if (path / name).exists())
    if legacy_present:
        raise PackValidationError(
            f"pack contains retired v1 files: {legacy_present}. The pack format is now "
            f"schema v2 (story-mode only). Migrate per Docs/02_GENRE_PACK_SPEC.md "
            f"or regenerate with the pack generator."
        )


def load_pack(path: str | Path) -> GenrePack:
    pack_path = _resolve_existing_path(path)
    validate_pack_directory(pack_path)

    metadata = PackMetadata.model_validate(_read_yaml(pack_path / "pack.yaml"))
    if metadata.schema_version != SUPPORTED_PACK_SCHEMA_VERSION:
        raise PackValidationError(
            f"unsupported schema_version {metadata.schema_version} "
            f"(this build expects v{SUPPORTED_PACK_SCHEMA_VERSION}). "
            f"Migrate per Docs/02_GENRE_PACK_SPEC.md or regenerate."
        )

    with (pack_path / "character_template.json").open("r", encoding="utf-8") as handle:
        raw_template = json.load(handle)
    legacy_keys = sorted(set(raw_template) & LEGACY_TEMPLATE_KEYS)
    if legacy_keys:
        raise PackValidationError(
            f"character_template.json contains retired v1 keys: {legacy_keys}. "
            f"v2 templates use name/concept/advantages/disadvantages/belongings/"
            f"relationships/notes."
        )
    character_template = CharacterTemplate.model_validate(raw_template)

    generator_seed_defaults = _read_yaml(pack_path / "generator_seed.yaml")
    if generator_seed_defaults.get("genre") != metadata.pack_name:
        raise PackValidationError(
            "generator_seed.yaml genre must match pack.yaml pack_name"
        )
    retired_in_seed = sorted(set(generator_seed_defaults) & RETIRED_SEED_FIELDS)
    if retired_in_seed:
        raise PackValidationError(
            f"generator_seed.yaml contains retired v1 fields: {retired_in_seed}. "
            f"Remove them; v2 uses num_truths / num_complications / num_factions."
        )

    overlay_text = _read_text(pack_path / "gm_prompt_overlay.md")
    overlay_gaps = _check_required_overlay_sections(overlay_text)
    if overlay_gaps:
        raise PackValidationError(
            f"gm_prompt_overlay.md is missing required sections: {overlay_gaps}"
        )

    naming_path = pack_path / "naming.yaml"
    if naming_path.exists():
        naming = NamingFile.model_validate(_read_yaml(naming_path))
    else:
        naming = NamingFile()

    return GenrePack(
        path=pack_path,
        metadata=metadata,
        character_template=character_template,
        gm_prompt_overlay=overlay_text,
        tone=_read_text(pack_path / "tone.md"),
        complications=_read_text(pack_path / "complications.md"),
        advantages_disadvantages=_read_text(pack_path / "advantages_disadvantages.md"),
        example_hooks=_read_text(pack_path / "example_hooks.md"),
        generator_seed_defaults=generator_seed_defaults,
        review_checklist=_read_text(pack_path / "REVIEW_CHECKLIST.md"),
        naming=naming,
    )
