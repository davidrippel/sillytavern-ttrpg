from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PremiseDocument(BaseModel):
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


class Beat(BaseModel):
    id: str | None = None
    text: str

    @model_validator(mode="before")
    @classmethod
    def coerce_string(cls, value):
        if isinstance(value, str):
            return {"text": value}
        return value

    @property
    def label(self) -> str | None:
        if not self.id:
            return None
        match = re.fullmatch(r"act(\d+)_beat(\d+)", self.id)
        if not match:
            return self.id
        return f"{match.group(1)}.{match.group(2)}"

    @property
    def rendered(self) -> str:
        label = self.label
        return f"{label} {self.text}" if label else self.text


class ActOutline(BaseModel):
    act_number: int | None = None
    title: str
    goal: str
    beats: list[Beat] = Field(min_length=3, max_length=5)


class PlotSkeleton(BaseModel):
    acts: list[ActOutline] = Field(min_length=3, max_length=6)
    main_antagonist: Antagonist
    driving_mystery: str
    hook: str
    escalation_arc: str

    @model_validator(mode="after")
    def assign_beat_ids(self) -> "PlotSkeleton":
        for act_index, act in enumerate(self.acts, start=1):
            act.act_number = act_index
            for beat_index, beat in enumerate(act.beats, start=1):
                beat.id = f"act{act_index}_beat{beat_index}"
        return self

    def all_beats(self) -> list[Beat]:
        return [beat for act in self.acts for beat in act.beats]

    def beat_id_to_text(self) -> dict[str, str]:
        return {beat.id: beat.text for beat in self.all_beats() if beat.id is not None}

    def beat_text_to_id(self) -> dict[str, str]:
        return {beat.text: beat.id for beat in self.all_beats() if beat.id is not None}

    def format_beat_reference(self, value: str) -> str:
        id_to_text = self.beat_id_to_text()
        text_to_id = self.beat_text_to_id()
        if value in id_to_text:
            beat = Beat(id=value, text=id_to_text[value])
            return beat.rendered
        if value in text_to_id:
            beat_id = text_to_id[value]
            beat = Beat(id=beat_id, text=value)
            return beat.rendered
        return value


class Faction(BaseModel):
    name: str
    description: str
    goals: list[str] = Field(min_length=1)
    methods: list[str] = Field(min_length=1)
    internal_tensions: list[str] = Field(min_length=1)
    relationship_to_plot: str
    moral_alignment: str


class FactionSet(BaseModel):
    factions: list[Faction] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def validate_ambiguity(self) -> "FactionSet":
        moral_labels = " ".join(faction.moral_alignment.lower() for faction in self.factions)
        if "ambiguous" not in moral_labels:
            raise ValueError("at least one faction must be morally ambiguous")
        return self


class NPCRelationship(BaseModel):
    name: str
    description: str


class NPC(BaseModel):
    name: str
    role: str
    faction_affiliation: str | None = None
    physical_description: str
    speaking_style: str
    motivation: str
    secret: str
    relationships: list[NPCRelationship] = Field(default_factory=list)
    abilities: list[str] = Field(default_factory=list)
    act_presence: list[str] = Field(default_factory=list)


class NPCRoster(BaseModel):
    npcs: list[NPC] = Field(min_length=6, max_length=15)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "NPCRoster":
        names = [npc.name for npc in self.npcs]
        if len(names) != len(set(names)):
            raise ValueError("NPC names must be unique")
        return self


class SensoryDescription(BaseModel):
    sight: str | None = None
    sound: str | None = None
    smell: str | None = None

    @model_validator(mode="after")
    def require_two_senses(self) -> "SensoryDescription":
        present = sum(1 for value in [self.sight, self.sound, self.smell] if value)
        if present < 2:
            raise ValueError("location must include at least two sensory details")
        return self


class Location(BaseModel):
    name: str
    type: str
    sensory_description: SensoryDescription
    notable_features: list[str] = Field(min_length=1)
    hidden_elements: list[str] = Field(min_length=1)
    npc_names: list[str] = Field(default_factory=list)
    plot_beats: list[str] = Field(min_length=1)


class LocationCatalog(BaseModel):
    locations: list[Location] = Field(min_length=5, max_length=12)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "LocationCatalog":
        names = [location.name for location in self.locations]
        if len(names) != len(set(names)):
            raise ValueError("location names must be unique")
        return self


class ClueTarget(BaseModel):
    type: str
    value: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        allowed = {"clue", "npc", "location", "beat"}
        if value not in allowed:
            raise ValueError(f"type must be one of {sorted(allowed)}")
        return value


class Clue(BaseModel):
    id: str
    found_at_type: str
    found_at: str
    reveals: str
    points_to: list[ClueTarget] = Field(min_length=1)
    supports_beats: list[str] = Field(min_length=1)

    @field_validator("found_at_type")
    @classmethod
    def validate_found_at_type(cls, value: str) -> str:
        if value not in {"npc", "location"}:
            raise ValueError("found_at_type must be npc or location")
        return value


class ClueGraph(BaseModel):
    entry_clue_ids: list[str] = Field(min_length=1)
    clues: list[Clue] = Field(min_length=4)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ClueGraph":
        ids = [clue.id for clue in self.clues]
        if len(ids) != len(set(ids)):
            raise ValueError("clue ids must be unique")
        return self


class Branch(BaseModel):
    name: str
    if_condition: str
    then_outcome: str
    later_act_consequences: list[str] = Field(min_length=1)
    references: list[str] = Field(default_factory=list)


class BranchPlan(BaseModel):
    branches: list[Branch] = Field(min_length=4, max_length=10)


class InitialAuthorsNote(BaseModel):
    current_act: str
    pending_beats: list[str] = Field(default_factory=list)
    active_threads: list[str] = Field(default_factory=list)
    recent_beats: list[str] = Field(default_factory=list)
    reminders: list[str] = Field(default_factory=list)

    def render(self) -> str:
        recent_beats = [f"- {beat}" for beat in self.recent_beats] if self.recent_beats else ["- (empty at start)"]
        sections = [
            f"Current Act: {self.current_act}",
            "Pending beats:",
            *(f"- {beat}" for beat in self.pending_beats),
            "Active threads:",
            *(f"- {thread}" for thread in self.active_threads),
            "Recent beats:",
            *recent_beats,
            "Reminders:",
            *(f"- {reminder}" for reminder in self.reminders),
        ]
        return "\n".join(sections)


class OpeningHookDocument(BaseModel):
    premise: str
    tone_statement: str
    character_creation_guidance: list[str] = Field(default_factory=list)
    opening_scene: str

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
        return "\n".join(lines)
