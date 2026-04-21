from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..llm import LLMClient, LLMError, generate_structured
from ..schemas import Clue, ClueGraph, ClueTarget, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..validation import ValidationLog, validate_clue_graph


PROMPT_FILE = "06_clue_chains.md"


class StageClueTarget(BaseModel):
    type: Literal["clue", "npc", "location", "beat"]
    value: str


class StageClue(BaseModel):
    id: str
    found_at_type: Literal["npc", "location"]
    found_at: str
    reveals: str
    points_to: list[StageClueTarget] = Field(min_length=1)
    supports_beats: list[str] = Field(min_length=1)


class StageClueGraph(BaseModel):
    entry_clue_ids: list[str] = Field(min_length=1)
    clues: list[StageClue] = Field(min_length=4, max_length=24)


def _target_clue_count(density: str, beat_count: int) -> int:
    normalized = density.lower().strip()
    if normalized == "light":
        return max(8, min(beat_count, 12))
    if normalized == "heavy":
        return max(14, min(beat_count + 6, 20))
    return max(10, min(beat_count + 2, 16))


def _build_beat_lookup(plot: PlotSkeleton) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for act_index, act in enumerate(plot.acts, start=1):
        for beat_index, beat in enumerate(act.beats, start=1):
            lookup[f"act{act_index}_beat{beat_index}"] = beat
    return lookup


def _convert_stage_graph(stage_graph: StageClueGraph, beat_lookup: dict[str, str]) -> ClueGraph:
    converted_clues: list[Clue] = []
    known_beat_values = set(beat_lookup.values())
    for clue in stage_graph.clues:
        converted_targets = []
        for target in clue.points_to:
            if target.type == "beat":
                value = beat_lookup.get(target.value, target.value)
            else:
                value = target.value
            converted_targets.append(ClueTarget(type=target.type, value=value))
        converted_supports = [beat_lookup.get(beat_id, beat_id) for beat_id in clue.supports_beats]
        converted_clues.append(
            Clue(
                id=clue.id,
                found_at_type=clue.found_at_type,
                found_at=clue.found_at,
                reveals=clue.reveals,
                points_to=converted_targets,
                supports_beats=converted_supports,
            )
        )
    return ClueGraph(entry_clue_ids=stage_graph.entry_clue_ids, clues=converted_clues)


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    density: str,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    snapshot_path: Path | None = None,
) -> ClueGraph:
    repair_note = ""
    beat_lookup = _build_beat_lookup(plot)
    target_clues = _target_clue_count(density, len(beat_lookup))
    for attempt in range(1, 4):
        context = {
            "premise_summary": {
                "central_conflict": premise.central_conflict,
                "tone_statement": premise.tone_statement,
                "thematic_pillars": premise.thematic_pillars,
            },
            "plot_summary": {
                "hook": plot.hook,
                "driving_mystery": plot.driving_mystery,
                "act_titles": [act.title for act in plot.acts],
            },
            "faction_names": [faction.name for faction in factions.factions],
            "npc_menu": [{"name": npc.name, "role": npc.role} for npc in npcs.npcs],
            "location_menu": [{"name": location.name, "type": location.type} for location in locations.locations],
            "beat_menu": beat_lookup,
            "clue_chain_density": density,
            "target_clue_count": target_clues,
            "repair_note": repair_note,
        }
        try:
            stage_graph = generate_structured(
                client=client,
                stage_name="clue_chains",
                system_prompt=system_prompt,
                user_prompt=json.dumps(context, indent=2),
                schema=StageClueGraph,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
        except LLMError as exc:
            raise LLMError(
                "clue_chains generation failed. Check stages/validation_log.txt and stages/calls.jsonl "
                f"for the failed attempts. Last error: {exc}"
            ) from exc
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, stage_graph.model_dump())
        clue_graph = _convert_stage_graph(stage_graph, beat_lookup)
        errors = validate_clue_graph(plot, npcs, locations, clue_graph)
        if not errors:
            return clue_graph
        validation_log.write(f"[clue_chains] repair attempt {attempt}: {'; '.join(errors)}")
        repair_note = "Repair these constraint failures: " + "; ".join(errors)
    raise LLMError("clue_chains failed cross-stage validation after 3 attempts")
