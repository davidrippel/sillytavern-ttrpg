from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def _ensure_snake_case(value: str, field: str) -> str:
    if not SNAKE_CASE.match(value):
        raise ValueError(f"{field} must be lowercase snake_case (got {value!r})")
    return value


class Pillar(BaseModel):
    title: str
    description: str


class ToneAndPillars(BaseModel):
    setting_statement: str
    pillars: list[Pillar]
    content_to_include: list[str]
    content_to_avoid: list[str]

    @model_validator(mode="after")
    def _shape(self) -> "ToneAndPillars":
        if not (3 <= len(self.pillars) <= 5):
            raise ValueError(f"pillars must have 3-5 entries (got {len(self.pillars)})")
        if len(self.setting_statement.split()) < 15:
            raise ValueError("setting_statement must be at least 2-3 sentences")
        return self


class AttributeDraft(BaseModel):
    key: str
    display: str
    description: str
    examples: list[str]

    @field_validator("key")
    @classmethod
    def _key_snake(cls, value: str) -> str:
        return _ensure_snake_case(value, "attribute key")

    @field_validator("examples")
    @classmethod
    def _examples_count(cls, value: list[str]) -> list[str]:
        if not (2 <= len(value) <= 4):
            raise ValueError(f"each attribute must have 2-4 examples (got {len(value)})")
        return value


class AttributesDraft(BaseModel):
    attributes: list[AttributeDraft]

    @model_validator(mode="after")
    def _validate(self) -> "AttributesDraft":
        if len(self.attributes) != 6:
            raise ValueError(f"must produce exactly 6 attributes (got {len(self.attributes)})")
        keys = [a.key for a in self.attributes]
        if len(set(keys)) != 6:
            raise ValueError(f"attribute keys must be unique (got {keys})")
        displays = [a.display.strip().lower() for a in self.attributes]
        if len(set(displays)) != 6:
            raise ValueError(f"attribute display names must be unique (got {[a.display for a in self.attributes]})")
        descriptions = [a.description.strip().lower() for a in self.attributes]
        if len(set(descriptions)) != 6:
            raise ValueError("attribute descriptions must be distinct (no two attributes describe the same ground)")
        return self


class ResourceDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    display: str
    kind: str
    description: str | None = None
    starting_value: int | float | str | bool | None = None
    max_value_field: str | None = None
    threshold_field: str | None = None
    threshold_consequence: dict | None = None
    threshold: int | None = None
    threshold_effect: str | None = None
    endgame_value: int | None = None
    endgame_effect: str | None = None

    @field_validator("key")
    @classmethod
    def _key_snake(cls, value: str) -> str:
        return _ensure_snake_case(value, "resource key")

    @field_validator("kind")
    @classmethod
    def _kind_known(cls, value: str) -> str:
        allowed = {"pool", "pool_with_threshold", "counter", "static_value", "flag", "tally"}
        if value not in allowed:
            raise ValueError(f"resource kind must be one of {sorted(allowed)} (got {value!r})")
        return value


class ResourcesDraft(BaseModel):
    resources: list[ResourceDraft]

    @model_validator(mode="after")
    def _validate(self) -> "ResourcesDraft":
        keys = [r.key for r in self.resources]
        if len(set(keys)) != len(keys):
            raise ValueError(f"resource keys must be unique (got {keys})")
        if "hp_current" not in keys or "hp_max" not in keys:
            missing = [k for k in ("hp_current", "hp_max") if k not in keys]
            raise ValueError(f"resources must include {missing}")
        # Genre resources beyond the required hp pair: 2-4
        non_required = [k for k in keys if k not in {"hp_current", "hp_max"}]
        if not (2 <= len(non_required) <= 6):
            raise ValueError(f"need 2-4 genre resources beyond hp_current/hp_max (got {len(non_required)})")
        for resource in self.resources:
            if resource.kind == "pool_with_threshold":
                if not resource.threshold_field:
                    raise ValueError(f"resource {resource.key!r} (pool_with_threshold) requires threshold_field")
                if resource.threshold_field not in keys:
                    raise ValueError(
                        f"resource {resource.key!r} threshold_field {resource.threshold_field!r} is not a known resource key"
                    )
        return self


Activation = Literal["active", "passive", "passive_or_triggered", "triggered", "ritual"]


class AbilityCategoryDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    display: str
    description: str
    activation: Activation
    has_levels: bool = False
    level_names: list[str] = Field(default_factory=list)
    roll_attribute: str | None = None
    consequence_on_failure: str | None = None
    consequence_on_partial: str | None = None

    @field_validator("key")
    @classmethod
    def _key_snake(cls, value: str) -> str:
        return _ensure_snake_case(value, "ability category key")


class AbilityCategoriesDraft(BaseModel):
    categories: list[AbilityCategoryDraft]

    @model_validator(mode="after")
    def _validate(self) -> "AbilityCategoriesDraft":
        if not (3 <= len(self.categories) <= 8):
            raise ValueError(f"must produce 3-8 ability categories (got {len(self.categories)})")
        keys = [c.key for c in self.categories]
        if len(set(keys)) != len(keys):
            raise ValueError(f"ability category keys must be unique (got {keys})")
        return self


class AbilityDraft(BaseModel):
    name: str
    category: str
    prerequisite: str | None = None
    description: str
    effect: str

    @field_validator("category")
    @classmethod
    def _category_snake(cls, value: str) -> str:
        return _ensure_snake_case(value, "ability category reference")


class AbilityCatalogDraft(BaseModel):
    catalog: list[AbilityDraft]

    @model_validator(mode="after")
    def _validate(self) -> "AbilityCatalogDraft":
        if not (15 <= len(self.catalog) <= 25):
            raise ValueError(f"ability catalog must have 15-25 entries (got {len(self.catalog)})")
        names = [a.name for a in self.catalog]
        if len(set(names)) != len(names):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"ability names must be unique; duplicates: {duplicates}")
        return self


class GMOverlay(BaseModel):
    setting_and_tone: str
    thematic_pillars: str
    attribute_guidance: str
    resource_mechanics: str
    ability_adjudication: str
    npc_conventions: str
    content_to_include: str
    content_to_avoid: str
    character_creation: str


class FailureMove(BaseModel):
    title: str
    body: str


class FailureMovesDraft(BaseModel):
    moves: list[FailureMove]
    partial_success_trades: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "FailureMovesDraft":
        if not (8 <= len(self.moves) <= 12):
            raise ValueError(f"failure_moves must have 8-12 genre-specific moves (got {len(self.moves)})")
        return self


class ExampleHook(BaseModel):
    title: str
    body: str


class ExampleHooksDraft(BaseModel):
    hooks: list[ExampleHook]

    @model_validator(mode="after")
    def _validate(self) -> "ExampleHooksDraft":
        if not (2 <= len(self.hooks) <= 3):
            raise ValueError(f"example_hooks must have 2-3 hooks (got {len(self.hooks)})")
        return self


class GeneratorSeedDraft(BaseModel):
    setting_anchors: list[str]
    themes_include: list[str]
    themes_exclude: list[str]
    tone: list[str]
    antagonist_archetypes_preferred: list[str]
    num_acts: int = 4
    num_npcs: int = 10
    num_locations: int = 8
    clue_chain_density: Literal["low", "medium", "high"] = "medium"
    branch_points: int = 6

    @model_validator(mode="after")
    def _non_empty_lists(self) -> "GeneratorSeedDraft":
        for field in ("setting_anchors", "themes_include", "tone", "antagonist_archetypes_preferred"):
            value = getattr(self, field)
            if not value:
                raise ValueError(f"{field} must not be empty")
        return self


class PackDescription(BaseModel):
    description: str

    @field_validator("description")
    @classmethod
    def _one_sentence(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description must not be empty")
        if len(cleaned) > 280:
            raise ValueError("description should be a single evocative sentence (<= 280 chars)")
        return cleaned


class ChecklistItem(BaseModel):
    section: str
    text: str


class ReviewChecklistDraft(BaseModel):
    items: list[ChecklistItem]

    @model_validator(mode="after")
    def _validate(self) -> "ReviewChecklistDraft":
        if len(self.items) < 4:
            raise ValueError(f"review checklist must have at least 4 specific items (got {len(self.items)})")
        return self
