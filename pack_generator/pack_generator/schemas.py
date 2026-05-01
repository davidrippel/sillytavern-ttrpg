from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
CONSEQUENCE_FORMAT = re.compile(r"^([a-z][a-z0-9_]*)\s*:\s*([+-]?\d+)\s*$")


def _ensure_snake_case(value: str, field: str) -> str:
    if not SNAKE_CASE.match(value):
        raise ValueError(f"{field} must be lowercase snake_case (got {value!r})")
    return value


def _parse_consequence(value: str) -> tuple[str, int] | None:
    match = CONSEQUENCE_FORMAT.match(value.strip())
    if not match:
        return None
    return match.group(1), int(match.group(2))


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


class AttributeOverlap(BaseModel):
    a: str
    b: str
    conflicting_examples: list[str] = Field(default_factory=list)
    explanation: str = ""


class AttributeOverlapReport(BaseModel):
    overlaps: list[AttributeOverlap] = Field(default_factory=list)


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
        live_kinds = {"pool", "pool_with_threshold", "counter", "tally"}
        live_resources = [r for r in self.resources if r.kind in live_kinds]
        if len(live_resources) > 4:
            live_keys = [r.key for r in live_resources]
            raise ValueError(
                f"too many live resource tracks ({len(live_resources)}: {live_keys}); the authoring guide caps "
                f"live tracks at 4 (HP plus three genre resources is the upper bound). Consolidate or demote "
                f"one to a static descriptor"
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

    @model_validator(mode="after")
    def _validate_consequence_gradient(self) -> "AbilityCategoryDraft":
        if not self.consequence_on_failure or not self.consequence_on_partial:
            return self
        failure = _parse_consequence(self.consequence_on_failure)
        partial = _parse_consequence(self.consequence_on_partial)
        if failure is None or partial is None:
            return self
        if failure == partial:
            raise ValueError(
                f"category {self.key!r}: consequence_on_failure and consequence_on_partial are identical "
                f"({self.consequence_on_failure!r}); partial should be a lesser cost or different kind"
            )
        f_resource, f_delta = failure
        p_resource, p_delta = partial
        if f_resource == p_resource and abs(p_delta) > abs(f_delta):
            raise ValueError(
                f"category {self.key!r}: consequence_on_partial ({self.consequence_on_partial!r}) is "
                f"harsher than consequence_on_failure ({self.consequence_on_failure!r}); partial should be lesser"
            )
        return self


class AbilityCategoriesDraft(BaseModel):
    categories: list[AbilityCategoryDraft]

    @model_validator(mode="after")
    def _validate(self) -> "AbilityCategoriesDraft":
        if not (3 <= len(self.categories) <= 8):
            raise ValueError(f"must produce 3-8 ability categories (got {len(self.categories)})")
        keys = [c.key for c in self.categories]
        if len(set(keys)) != len(keys):
            raise ValueError(f"ability category keys must be unique (got {keys})")
        active = [c for c in self.categories if c.activation == "active"]
        seen: dict[tuple[str, str], str] = {}
        for category in active:
            if not category.roll_attribute or not category.consequence_on_failure:
                continue
            signature = (category.roll_attribute, category.consequence_on_failure.strip())
            if signature in seen:
                raise ValueError(
                    f"active categories {seen[signature]!r} and {category.key!r} share the same roll_attribute "
                    f"({signature[0]!r}) and consequence_on_failure ({signature[1]!r}); collapse them or "
                    f"differentiate the mechanical signature"
                )
            seen[signature] = category.key
        if len(self.categories) >= 4:
            activations = {c.activation for c in self.categories}
            if len(activations) < 2:
                raise ValueError(
                    f"all {len(self.categories)} categories share the same activation "
                    f"({next(iter(activations))!r}); the authoring guide recommends a mix — "
                    f"1-3 active, plus passive/triggered/ritual. Diversify the activation types"
                )
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
        self._validate_prerequisite_depth()
        return self

    def _validate_prerequisite_depth(self) -> None:
        by_name = {a.name: a for a in self.catalog}
        depth_cache: dict[str, int] = {}

        def depth(name: str, visiting: set[str]) -> int:
            if name in depth_cache:
                return depth_cache[name]
            if name in visiting:
                raise ValueError(f"prerequisite cycle detected involving ability {name!r}")
            ability = by_name.get(name)
            if ability is None:
                return 0
            prereq = (ability.prerequisite or "").strip()
            if not prereq or prereq.lower() == "none":
                depth_cache[name] = 0
                return 0
            if prereq not in by_name:
                depth_cache[name] = 0
                return 0
            visiting = visiting | {name}
            d = 1 + depth(prereq, visiting)
            depth_cache[name] = d
            return d

        max_chain_depth = 3
        for ability in self.catalog:
            d = depth(ability.name, set())
            if d > max_chain_depth:
                raise ValueError(
                    f"ability {ability.name!r} has prerequisite chain depth {d} (max {max_chain_depth}); "
                    f"deep prerequisite chains straitjacket character builds"
                )


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

    @model_validator(mode="after")
    def _validate_word_count(self) -> "GMOverlay":
        sections = (
            self.setting_and_tone,
            self.thematic_pillars,
            self.attribute_guidance,
            self.resource_mechanics,
            self.ability_adjudication,
            self.npc_conventions,
            self.content_to_include,
            self.content_to_avoid,
            self.character_creation,
        )
        total = sum(len(section.split()) for section in sections)
        if total > 1800:
            raise ValueError(
                f"gm_prompt_overlay total word count is {total}; the authoring guide caps overlays at "
                f"~1500 words (hard fail at 1800). Cut redundant prose; the LLM doesn't need every "
                f"subtlety spelled out"
            )
        return self
    story_mode_play: str = ""


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
        for hook in self.hooks:
            tail = hook.body.strip().lower()[-200:]
            if "?" in tail:
                continue
            choice_phrases = ("what do you do", "what now", "you must decide", "your move", "you must choose")
            if any(phrase in tail for phrase in choice_phrases):
                continue
            raise ValueError(
                f"hook {hook.title!r} does not end at a moment of choice; the last paragraph should "
                f"present the player with a question or explicit decision point"
            )
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

    @model_validator(mode="after")
    def _validate_no_theme_contradictions(self) -> "GeneratorSeedDraft":
        normalized_include = {_normalize_seed_term(t) for t in self.themes_include if t}
        normalized_exclude = {_normalize_seed_term(t) for t in self.themes_exclude if t}
        normalized_include.discard("")
        normalized_exclude.discard("")
        exact_overlap = normalized_include & normalized_exclude
        if exact_overlap:
            raise ValueError(
                f"themes_include and themes_exclude overlap on terms: {sorted(exact_overlap)}; "
                f"the same theme cannot be both wanted and forbidden"
            )
        normalized_tone = {_normalize_seed_term(t) for t in self.tone if t}
        normalized_tone.discard("")
        contradictions: list[tuple[str, str]] = []
        for tone_term in normalized_tone:
            for exclude_term in normalized_exclude:
                if tone_term == exclude_term or tone_term in exclude_term or exclude_term in tone_term:
                    contradictions.append((tone_term, exclude_term))
        if contradictions:
            raise ValueError(
                f"tone keywords contradict themes_exclude: {contradictions}; the GM cannot be told to "
                f"evoke a tone whose name overlaps a forbidden theme (e.g. tone:[grim] + exclude:[grimdark])"
            )
        return self

    @model_validator(mode="after")
    def _validate_anchor_specificity(self) -> "GeneratorSeedDraft":
        cliche_anchors = {
            "the_frontier",
            "the_void",
            "the_belt",
            "deep_space",
            "a_colony",
            "a_station",
            "the_outpost",
            "the_wilds",
            "the_unknown",
        }
        too_generic: list[str] = []
        for anchor in self.setting_anchors:
            normalized = _normalize_seed_term(anchor)
            if normalized in cliche_anchors:
                too_generic.append(anchor)
                continue
            tokens = [t for t in normalized.split("_") if t]
            if len(tokens) < 2:
                too_generic.append(anchor)
        if too_generic:
            raise ValueError(
                f"setting_anchors entries are too generic: {too_generic}; each anchor needs a specific "
                f"descriptor (not 'the_frontier' but 'verdant_prime_derelict_colony'). At least 2 tokens "
                f"and not in the cliché blocklist"
            )
        return self

    @model_validator(mode="after")
    def _validate_antagonist_diversity(self) -> "GeneratorSeedDraft":
        normalized = {_normalize_seed_term(a) for a in self.antagonist_archetypes_preferred}
        normalized.discard("")
        if len(normalized) < 3:
            raise ValueError(
                f"antagonist_archetypes_preferred must have at least 3 distinct archetypes "
                f"(got {len(normalized)} unique: {sorted(normalized)}); single-archetype packs feel flat"
            )
        return self


def _normalize_seed_term(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")


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
