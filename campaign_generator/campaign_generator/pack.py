from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    author: str | None = None

    @field_validator("pack_name")
    @classmethod
    def validate_pack_name(cls, value: str) -> str:
        if value != value.lower() or "-" in value or " " in value:
            raise ValueError("pack_name must be lowercase snake_case")
        return value


class AttributeDefinition(BaseModel):
    key: str
    display: str
    description: str
    examples: list[str] = Field(default_factory=list)


class AttributesFile(BaseModel):
    attributes: list[AttributeDefinition]

    @model_validator(mode="after")
    def validate_count_and_uniqueness(self) -> "AttributesFile":
        if len(self.attributes) != 6:
            raise ValueError("attributes.yaml must contain exactly 6 attributes")
        keys = [attribute.key for attribute in self.attributes]
        if len(keys) != len(set(keys)):
            raise ValueError("attribute keys must be unique")
        return self


class ResourceThresholdConsequence(BaseModel):
    field: str
    delta: str | int
    then_reset: bool = False


class ResourceDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    display: str
    kind: str
    description: str | None = None
    starting_value: int | float | str | bool | None = None
    max_value_field: str | None = None
    threshold_field: str | None = None
    threshold_consequence: ResourceThresholdConsequence | None = None
    threshold: int | None = None
    threshold_effect: str | None = None
    endgame_value: int | None = None
    endgame_effect: str | None = None


class ResourcesFile(BaseModel):
    resources: list[ResourceDefinition]

    @model_validator(mode="after")
    def validate_required_resources(self) -> "ResourcesFile":
        keys = {resource.key for resource in self.resources}
        missing = {"hp_current", "hp_max"} - keys
        if missing:
            raise ValueError(f"resources.yaml missing required resources: {sorted(missing)}")
        return self


class AbilityCategory(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    display: str
    description: str
    activation: str
    has_levels: bool = False
    level_names: list[str] = Field(default_factory=list)


class AbilityDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    category: str
    prerequisite: str | None = None
    description: str
    effect: str


class AbilitiesFile(BaseModel):
    categories: list[AbilityCategory]
    catalog: list[AbilityDefinition]

    @model_validator(mode="after")
    def validate_categories(self) -> "AbilitiesFile":
        category_keys = {category.key for category in self.categories}
        if len(category_keys) != len(self.categories):
            raise ValueError("ability category keys must be unique")
        unknown_categories = sorted(
            {ability.category for ability in self.catalog if ability.category not in category_keys}
        )
        if unknown_categories:
            raise ValueError(f"abilities reference unknown categories: {unknown_categories}")
        return self


class GenrePack(BaseModel):
    path: Path
    metadata: PackMetadata
    attributes: AttributesFile
    resources: ResourcesFile
    abilities: AbilitiesFile
    character_template: dict[str, Any]
    gm_prompt_overlay: str
    tone: str
    failure_moves: str
    example_hooks: str
    generator_seed_defaults: dict[str, Any]
    review_checklist: str

    @property
    def ability_names(self) -> set[str]:
        return {ability.name for ability in self.abilities.catalog}

    @property
    def attribute_keys(self) -> list[str]:
        return [attribute.key for attribute in self.attributes.attributes]


REQUIRED_PACK_FILES = {
    "pack.yaml",
    "attributes.yaml",
    "resources.yaml",
    "abilities.yaml",
    "character_template.json",
    "gm_prompt_overlay.md",
    "tone.md",
    "failure_moves.md",
    "example_hooks.md",
    "generator_seed.yaml",
    "REVIEW_CHECKLIST.md",
}


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


def validate_pack_directory(path: Path) -> None:
    missing = sorted(name for name in REQUIRED_PACK_FILES if not (path / name).exists())
    if missing:
        raise PackValidationError(f"pack is missing required files: {missing}")


def load_pack(path: str | Path) -> GenrePack:
    pack_path = _resolve_existing_path(path)
    validate_pack_directory(pack_path)

    metadata = PackMetadata.model_validate(_read_yaml(pack_path / "pack.yaml"))
    if metadata.schema_version != 1:
        raise PackValidationError(f"unsupported schema_version {metadata.schema_version}")

    attributes = AttributesFile.model_validate(_read_yaml(pack_path / "attributes.yaml"))
    resources = ResourcesFile.model_validate(_read_yaml(pack_path / "resources.yaml"))
    abilities = AbilitiesFile.model_validate(_read_yaml(pack_path / "abilities.yaml"))

    with (pack_path / "character_template.json").open("r", encoding="utf-8") as handle:
        character_template = json.load(handle)

    template_attributes = character_template.get("attributes", {})
    attribute_keys = set(attributes_key.key for attributes_key in attributes.attributes)
    if set(template_attributes.keys()) != attribute_keys:
        raise PackValidationError("character_template.json attributes must match attributes.yaml keys")

    generator_seed_defaults = _read_yaml(pack_path / "generator_seed.yaml")
    if generator_seed_defaults.get("genre") != metadata.pack_name:
        raise PackValidationError(
            "generator_seed.yaml genre must match pack.yaml pack_name"
        )

    return GenrePack(
        path=pack_path,
        metadata=metadata,
        attributes=attributes,
        resources=resources,
        abilities=abilities,
        character_template=character_template,
        gm_prompt_overlay=_read_text(pack_path / "gm_prompt_overlay.md"),
        tone=_read_text(pack_path / "tone.md"),
        failure_moves=_read_text(pack_path / "failure_moves.md"),
        example_hooks=_read_text(pack_path / "example_hooks.md"),
        generator_seed_defaults=generator_seed_defaults,
        review_checklist=_read_text(pack_path / "REVIEW_CHECKLIST.md"),
    )
