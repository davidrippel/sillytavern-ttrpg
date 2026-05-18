from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Premise + plot spine (v2) -----------------------------------------


class PremiseDocument(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    paragraphs: list[str] = Field(min_length=2, max_length=2)
    central_conflict: str
    tone_statement: str
    thematic_pillars: list[str] = Field(min_length=3, max_length=5)

    @property
    def premise_text(self) -> str:
        return "\n\n".join(self.paragraphs)


class Antagonist(BaseModel):
    name: str
    motivation: str
    secret: str
    relationship_to_protagonist: str


class SupportingCastMember(BaseModel):
    name: str = Field(min_length=1)
    archetype: str = Field(min_length=1, max_length=120)
    narrative_role: str = Field(min_length=1, max_length=240)


class ActOutline(BaseModel):
    """An act in the v2 system is a *thematic chapter*, not a list of beats.

    Acts give the campaign generator a way to group locations and NPCs by
    when they come into play, but the runtime has no concept of "current
    act" — the extension tracks facts and threads, not act numbers. So
    we keep `act_number`, `title`, and `goal`; the v1 `beats` field is
    retired.
    """

    act_number: int | None = None
    title: str
    goal: str


class PlotSkeleton(BaseModel):
    """The campaign's thematic spine, plus a small cast of supporting
    fixtures. There are no beats. The GM is told *what the campaign is
    about*, not *what should happen next*.
    """

    acts: list[ActOutline] = Field(min_length=2, max_length=4)
    main_antagonist: Antagonist
    driving_mystery: str
    hook: str
    escalation_arc: str
    thematic_spine: list[str] = Field(
        min_length=3,
        max_length=5,
        description=(
            "3-5 short escalation themes the GM should honor as the campaign "
            "progresses. Not beats; not ordered. A vibe vector."
        ),
    )
    supporting_cast: list[SupportingCastMember] = Field(default_factory=list)

    @model_validator(mode="after")
    def assign_act_numbers(self) -> "PlotSkeleton":
        for idx, act in enumerate(self.acts, start=1):
            act.act_number = idx
        return self


# --- Factions ----------------------------------------------------------


class Faction(BaseModel):
    name: str
    description: str = Field(max_length=300)
    goals: list[str] = Field(min_length=1)
    methods: list[str] = Field(min_length=1)
    internal_tensions: list[str] = Field(min_length=1)
    relationship_to_plot: str = Field(max_length=200)
    moral_alignment: str

    @field_validator("goals", "methods", "internal_tensions")
    @classmethod
    def cap_list_items(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 120:
                raise ValueError("each goals/methods/tensions item must be <= 120 chars")
        return value


class FactionSet(BaseModel):
    factions: list[Faction] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def validate_ambiguity(self) -> "FactionSet":
        moral_labels = " ".join(faction.moral_alignment.lower() for faction in self.factions)
        if "ambiguous" not in moral_labels:
            raise ValueError("at least one faction must be morally ambiguous")
        return self


# --- NPCs --------------------------------------------------------------


class NPCRelationship(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = Field(max_length=160)


class NPC(BaseModel):
    name: str
    role: str = Field(max_length=80)
    faction_affiliation: str | None = None
    physical_description: str = Field(max_length=220)
    speaking_style: str = Field(max_length=160)
    motivation: str = Field(max_length=220)
    secret: str = Field(max_length=320)
    relationships: list[NPCRelationship] = Field(default_factory=list)
    advantages: list[str] = Field(
        default_factory=list,
        description=(
            "Short story-mode advantage phrases describing what the NPC "
            "is good at. Free-form; the GM picks them up from prose."
        ),
    )
    discovery_surfaces: list[str] = Field(
        default_factory=list,
        description=(
            "Optional hints about what the player can learn through this "
            "NPC. Used by the GM as nudges; not a clue chain."
        ),
    )
    act_presence: list[str] = Field(
        default_factory=list,
        description="Which acts the NPC most naturally appears in (free-form labels).",
    )
    image_generation_prompt: str = Field(default="", max_length=600)


class NPCRoster(BaseModel):
    npcs: list[NPC] = Field(min_length=6, max_length=25)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "NPCRoster":
        names = [npc.name for npc in self.npcs]
        if len(names) != len(set(names)):
            raise ValueError("NPC names must be unique")
        return self


# --- Locations ---------------------------------------------------------


class SensoryDescription(BaseModel):
    sight: str | None = Field(default=None, max_length=220)
    sound: str | None = Field(default=None, max_length=220)
    smell: str | None = Field(default=None, max_length=220)

    @model_validator(mode="after")
    def require_two_senses(self) -> "SensoryDescription":
        present = sum(1 for value in [self.sight, self.sound, self.smell] if value)
        if present < 2:
            raise ValueError("location must include at least two sensory details")
        return self


class Location(BaseModel):
    name: str
    type: str = Field(max_length=60)
    sensory_description: SensoryDescription
    notable_features: list[str] = Field(min_length=1)
    hidden_elements: list[str] = Field(min_length=1)
    npc_names: list[str] = Field(default_factory=list)
    discovery_surfaces: list[str] = Field(
        default_factory=list,
        description="Hints the player can pick up by paying attention here.",
    )

    @field_validator("notable_features", "hidden_elements")
    @classmethod
    def cap_list_items(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 220:
                raise ValueError("each notable_features/hidden_elements item must be <= 220 chars")
        return value


class LocationCatalog(BaseModel):
    locations: list[Location] = Field(min_length=5, max_length=20)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "LocationCatalog":
        names = [location.name for location in self.locations]
        if len(names) != len(set(names)):
            raise ValueError("location names must be unique")
        return self


# --- Truths (v2) -------------------------------------------------------


class Truth(BaseModel):
    """A single atomic fact that defines the campaign's underlying
    situation. The GM never sees the whole truth set; the extension's
    pacing module picks one at a time and injects it as a director's
    note when the player's threads and recent facts brush against it.
    """

    id: str = Field(min_length=2)
    text: str = Field(min_length=10, max_length=240)
    hint: str = Field(default="", max_length=200)
    adjacency_keys: list[str] = Field(
        default_factory=list,
        description=(
            "Lowercase tokens (NPC names, location names, faction names, "
            "concepts) that signal a director's note for this truth is "
            "in scope. The extension's pacing module matches these against "
            "live threads and recent facts."
        ),
    )

    @field_validator("id")
    @classmethod
    def snake_case_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("truth id must be snake_case ([a-z][a-z0-9_]*)")
        return value


class TruthSet(BaseModel):
    truths: list[Truth] = Field(min_length=4, max_length=10)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "TruthSet":
        ids = [t.id for t in self.truths]
        if len(ids) != len(set(ids)):
            raise ValueError("truth ids must be unique")
        return self


# --- Complications (v2) ------------------------------------------------


class Complication(BaseModel):
    """A genre-specific, campaign-specific narrative complication. The
    GM picks from `__pack_complications` (pack-level) and these
    (campaign-level) when a scene calls for a setback or a pacing cue.
    """

    title: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=10, max_length=320)

    @field_validator("body")
    @classmethod
    def reject_vague_phrases(cls, value: str) -> str:
        haystack = value.lower()
        forbidden = (
            "something happens",
            "something bad happens",
            "the gm decides",
            "you fail",
            "you lose",
        )
        for term in forbidden:
            if term in haystack:
                raise ValueError(f"complication body contains vague phrase {term!r}")
        return value


class ComplicationSet(BaseModel):
    complications: list[Complication] = Field(min_length=6, max_length=15)


# --- Branches ----------------------------------------------------------


class Branch(BaseModel):
    name: str
    if_condition: str
    then_outcome: str
    later_consequences: list[str] = Field(min_length=1)
    references: list[str] = Field(default_factory=list)


class BranchPlan(BaseModel):
    branches: list[Branch] = Field(min_length=4, max_length=10)


# --- Sample characters (v2 story-mode shape) ---------------------------


class SampleCharacterRelationship(BaseModel):
    name: str
    tie: str


class SampleCharacter(BaseModel):
    """A pre-generated player character matching the v2 character template."""

    name: str = Field(min_length=1)
    concept: str = Field(min_length=10, max_length=320)
    advantages: list[str] = Field(min_length=2, max_length=4)
    disadvantages: list[str] = Field(min_length=1, max_length=2)
    belongings: list[str] = Field(default_factory=list, max_length=8)
    relationships: list[SampleCharacterRelationship] = Field(default_factory=list, max_length=4)
    hook_into_campaign: str = Field(max_length=320)


class SampleCharacterSet(BaseModel):
    characters: list[SampleCharacter] = Field(min_length=1, max_length=8)


# --- Opening hook + initial AN ----------------------------------------


class OpeningHookDocument(BaseModel):
    premise: str
    tone_statement: str
    character_creation_guidance: list[str] = Field(default_factory=list)
    opening_scene: str
    pc_prior_knowledge: str | None = None

    def render(self) -> str:
        lines = [
            "Premise",
            self.premise,
            "",
            "Tone",
            self.tone_statement,
            "",
            "Character Creation Guidance",
            *(f"- {item}" for item in self.character_creation_guidance),
            "",
            "Opening Scene",
            self.opening_scene,
        ]
        if self.pc_prior_knowledge and self.pc_prior_knowledge.strip():
            lines.extend(["", "What you already know", self.pc_prior_knowledge.strip()])
        return "\n".join(lines)
