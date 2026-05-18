from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# --- Tone and pillars ----------------------------------------------------


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


# --- GM prompt overlay (v2) ---------------------------------------------


class GMOverlay(BaseModel):
    """The story-mode GM overlay. Each section becomes a ``## Header`` in
    the rendered ``gm_prompt_overlay.md``. The campaign generator embeds
    the whole rendered file into the lorebook as ``__pack_gm_overlay``.

    There are no resource_mechanics, attribute_guidance, or
    ability_adjudication sections in v2 — the system has no scores,
    pools, or rolls. Their place is taken by ``resolving_actions``
    (narrative adjudication) and ``translating_pressures`` (the genre's
    accumulating signs).
    """

    setting_and_tone: str
    thematic_pillars: str
    resolving_actions: str
    translating_pressures: str
    npc_conventions: str
    content_to_include: str
    content_to_avoid: str
    character_creation: str

    @model_validator(mode="after")
    def _validate_word_count(self) -> "GMOverlay":
        sections = (
            self.setting_and_tone,
            self.thematic_pillars,
            self.resolving_actions,
            self.translating_pressures,
            self.npc_conventions,
            self.content_to_include,
            self.content_to_avoid,
            self.character_creation,
        )
        total = sum(len(section.split()) for section in sections)
        if total > 1800:
            raise ValueError(
                f"gm_prompt_overlay total word count is {total}; the authoring guide caps "
                f"overlays at ~1500 words (hard fail at 1800). Cut redundant prose."
            )
        return self

    @model_validator(mode="after")
    def _validate_no_legacy_language(self) -> "GMOverlay":
        # The runtime has no dice or numeric resources. If the overlay
        # leaks stat-mode language, repair-loop the stage instead of
        # shipping a broken pack.
        haystack = (
            self.resolving_actions
            + "\n"
            + self.translating_pressures
            + "\n"
            + self.character_creation
        ).lower()
        bad_terms = ("2d6", "+1 to ", "attribute roll", "make a roll", "status_update")
        leaks = [term for term in bad_terms if term in haystack]
        if leaks:
            raise ValueError(
                f"gm_prompt_overlay leaks retired stat-mode language: {leaks}. "
                f"v2 packs use narrative adjudication only — no dice, no numeric resources."
            )
        return self


# --- Complications -------------------------------------------------------


class Complication(BaseModel):
    title: str
    body: str

    @field_validator("body")
    @classmethod
    def _body_substantive(cls, value: str) -> str:
        if len(value.split()) < 6:
            raise ValueError(
                f"complication body too short ({value!r}); each complication is a concrete "
                f"narrative consequence, at least one full sentence"
            )
        return value


class SuccessCost(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _trim(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned.split()) < 4:
            raise ValueError(f"success-cost entry too short ({value!r})")
        return cleaned


class ComplicationsDraft(BaseModel):
    complications: list[Complication]
    success_costs: list[SuccessCost]

    @model_validator(mode="after")
    def _shape(self) -> "ComplicationsDraft":
        if not (10 <= len(self.complications) <= 15):
            raise ValueError(
                f"complications must have 10-15 genre-specific entries "
                f"(got {len(self.complications)})"
            )
        if not (6 <= len(self.success_costs) <= 12):
            raise ValueError(
                f"success_costs must have 6-12 entries (got {len(self.success_costs)})"
            )
        # No vague phrases.
        vague = ("something happens", "something bad", "the gm decides", "you fail", "you lose")
        for entry in self.complications:
            haystack = f"{entry.title} {entry.body}".lower()
            for phrase in vague:
                if phrase in haystack:
                    raise ValueError(
                        f"complication {entry.title!r} contains vague phrase {phrase!r}; "
                        f"replace with a concrete change to the situation"
                    )
        return self


UNIVERSAL_COMPLICATIONS: tuple[str, ...] = (
    "Reveal an unwelcome truth or danger the player didn't know.",
    "Separate the protagonist from something they value.",
    "Force a hard choice between two things they want to keep.",
    "Burn a resource — gear breaks, a torch dies, ammunition spent.",
    "Attract attention from someone dangerous.",
    "Inflict a condition (bleeding, exhausted, shaken, marked).",
)


# --- Advantages / disadvantages -----------------------------------------


class VocabAxis(BaseModel):
    title: str
    entries: list[str]

    @model_validator(mode="after")
    def _shape(self) -> "VocabAxis":
        if not (4 <= len(self.entries) <= 8):
            raise ValueError(
                f"axis {self.title!r}: must have 4-8 entries (got {len(self.entries)})"
            )
        for entry in self.entries:
            if len(entry.split()) < 3:
                raise ValueError(
                    f"axis {self.title!r}: entry {entry!r} is too vague — needs a specific "
                    f"thing the GM can picture (a place, training, mark, debt)"
                )
        return self


class AdvantagesDisadvantagesDraft(BaseModel):
    advantage_axes: list[VocabAxis]
    disadvantage_axes: list[VocabAxis]

    @model_validator(mode="after")
    def _shape(self) -> "AdvantagesDisadvantagesDraft":
        if not (3 <= len(self.advantage_axes) <= 5):
            raise ValueError(
                f"advantage_axes must have 3-5 axes (got {len(self.advantage_axes)})"
            )
        if not (3 <= len(self.disadvantage_axes) <= 5):
            raise ValueError(
                f"disadvantage_axes must have 3-5 axes (got {len(self.disadvantage_axes)})"
            )
        adv_total = sum(len(a.entries) for a in self.advantage_axes)
        dis_total = sum(len(a.entries) for a in self.disadvantage_axes)
        if not (20 <= adv_total <= 35):
            raise ValueError(f"advantages total must be 20-35 (got {adv_total})")
        if not (15 <= dis_total <= 25):
            raise ValueError(f"disadvantages total must be 15-25 (got {dis_total})")
        return self


# --- Example hooks -------------------------------------------------------


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
            choice_phrases = (
                "what do you do",
                "what now",
                "you must decide",
                "your move",
                "you must choose",
            )
            if any(phrase in tail for phrase in choice_phrases):
                continue
            raise ValueError(
                f"hook {hook.title!r} does not end at a moment of choice; the last paragraph "
                f"should present the player with a question or explicit decision point"
            )
        return self


# --- Generator seed defaults (v2) ----------------------------------------


class GeneratorSeedDraft(BaseModel):
    setting_anchors: list[str]
    themes_include: list[str]
    themes_exclude: list[str]
    tone: list[str]
    antagonist_archetypes_preferred: list[str]
    num_npcs: int = 18
    num_locations: int = 12
    num_factions: int = 4
    num_truths: int = 7
    num_complications: int = 12

    @model_validator(mode="after")
    def _non_empty_lists(self) -> "GeneratorSeedDraft":
        for field in (
            "setting_anchors",
            "themes_include",
            "tone",
            "antagonist_archetypes_preferred",
        ):
            value = getattr(self, field)
            if not value:
                raise ValueError(f"{field} must not be empty")
        return self

    @model_validator(mode="after")
    def _validate_counts(self) -> "GeneratorSeedDraft":
        for field, lo, hi in (
            ("num_npcs", 8, 30),
            ("num_locations", 6, 20),
            ("num_factions", 2, 6),
            ("num_truths", 5, 10),
            ("num_complications", 8, 15),
        ):
            v = getattr(self, field)
            if not (lo <= v <= hi):
                raise ValueError(f"{field}={v} out of expected range [{lo}, {hi}]")
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
                f"themes_include and themes_exclude overlap on: {sorted(exact_overlap)}"
            )
        normalized_tone = {_normalize_seed_term(t) for t in self.tone if t}
        normalized_tone.discard("")
        contradictions: list[tuple[str, str]] = []
        for tone_term in normalized_tone:
            for exclude_term in normalized_exclude:
                if (
                    tone_term == exclude_term
                    or tone_term in exclude_term
                    or exclude_term in tone_term
                ):
                    contradictions.append((tone_term, exclude_term))
        if contradictions:
            raise ValueError(
                f"tone keywords contradict themes_exclude: {contradictions}"
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
                f"setting_anchors entries are too generic: {too_generic}; "
                f"each anchor needs at least 2 tokens and not in the cliché blocklist"
            )
        return self

    @model_validator(mode="after")
    def _validate_antagonist_diversity(self) -> "GeneratorSeedDraft":
        normalized = {_normalize_seed_term(a) for a in self.antagonist_archetypes_preferred}
        normalized.discard("")
        if len(normalized) < 3:
            raise ValueError(
                f"antagonist_archetypes_preferred must have at least 3 distinct archetypes "
                f"(got {sorted(normalized)})"
            )
        return self


def _normalize_seed_term(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")


# --- Pack description ----------------------------------------------------


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


# --- Naming --------------------------------------------------------------


class NamingDraft(BaseModel):
    naming_registers: list[str]
    district_flavors: list[str]

    @model_validator(mode="after")
    def _validate(self) -> "NamingDraft":
        if not (8 <= len(self.naming_registers) <= 14):
            raise ValueError(
                f"naming_registers must have 8-14 entries (got {len(self.naming_registers)})"
            )
        if not (8 <= len(self.district_flavors) <= 16):
            raise ValueError(
                f"district_flavors must have 8-16 entries (got {len(self.district_flavors)})"
            )
        for entry in self.naming_registers:
            if len(entry) < 30:
                raise ValueError(
                    f"naming register entry too short ({entry!r}); each entry should describe "
                    f"a naming convention specifically enough that an LLM can sample names"
                )
        for entry in self.district_flavors:
            if len(entry) < 20:
                raise ValueError(
                    f"district flavor entry too short ({entry!r}); each entry should be a "
                    f"concrete neighborhood or precinct archetype that fits the genre"
                )
        return self


# --- Review checklist ----------------------------------------------------


class ChecklistItem(BaseModel):
    section: str
    text: str


class ReviewChecklistDraft(BaseModel):
    items: list[ChecklistItem]

    @model_validator(mode="after")
    def _validate(self) -> "ReviewChecklistDraft":
        if len(self.items) < 4:
            raise ValueError(
                f"review checklist must have at least 4 specific items (got {len(self.items)})"
            )
        return self
