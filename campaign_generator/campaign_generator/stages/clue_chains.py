from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..artifacts import serialize_clue_graph
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
    return plot.beat_id_to_text()


def _convert_stage_graph(stage_graph: StageClueGraph, beat_lookup: dict[str, str]) -> ClueGraph:
    converted_clues: list[Clue] = []
    beat_text_to_id = {text: beat_id for beat_id, text in beat_lookup.items()}
    for clue in stage_graph.clues:
        converted_targets = []
        for target in clue.points_to:
            if target.type == "beat":
                value = target.value if target.value in beat_lookup else beat_text_to_id.get(target.value, target.value)
            else:
                value = target.value
            converted_targets.append(ClueTarget(type=target.type, value=value))
        converted_supports = [
            beat_id if beat_id in beat_lookup else beat_text_to_id.get(beat_id, beat_id)
            for beat_id in clue.supports_beats
        ]
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


def _build_fallback_clue_graph(
    *,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
) -> ClueGraph:
    beat_list = [beat for act in plot.acts for beat in act.beats]
    if not beat_list:
        raise LLMError("cannot build fallback clue graph without plot beats")

    if not npcs.npcs and not locations.locations:
        raise LLMError("cannot build fallback clue graph without NPCs or locations")

    clues: list[Clue] = []
    entry_ids: list[str] = []
    npc_cycle = npcs.npcs or []
    location_cycle = locations.locations or []

    for index, beat in enumerate(beat_list, start=1):
        primary_id = f"clue{index:02d}a"
        secondary_id = f"clue{index:02d}b"
        next_primary_id = f"clue{index + 1:02d}a" if index < len(beat_list) else None

        location = location_cycle[(index - 1) % len(location_cycle)] if location_cycle else None
        npc = npc_cycle[(index - 1) % len(npc_cycle)] if npc_cycle else None

        primary_found_at_type = "location" if location is not None else "npc"
        primary_found_at = location.name if location is not None else npc.name
        secondary_found_at_type = "npc" if npc is not None else "location"
        secondary_found_at = npc.name if npc is not None else location.name

        primary_targets = [ClueTarget(type="beat", value=beat.id), ClueTarget(type="clue", value=secondary_id)]
        if next_primary_id is not None:
            primary_targets.append(ClueTarget(type="clue", value=next_primary_id))
        elif npc is not None:
            primary_targets.append(ClueTarget(type="npc", value=npc.name))
        elif location is not None:
            primary_targets.append(ClueTarget(type="location", value=location.name))

        secondary_targets = [ClueTarget(type="beat", value=beat.id)]
        if next_primary_id is not None:
            secondary_targets.append(ClueTarget(type="clue", value=next_primary_id))
        elif location is not None:
            secondary_targets.append(ClueTarget(type="location", value=location.name))
        elif npc is not None:
            secondary_targets.append(ClueTarget(type="npc", value=npc.name))

        clues.append(
            Clue(
                id=primary_id,
                found_at_type=primary_found_at_type,
                found_at=primary_found_at,
                reveals=f"Evidence tied to '{beat.text}' points toward a larger pattern behind {plot.driving_mystery.lower()}",
                points_to=primary_targets,
                supports_beats=[beat.id],
            )
        )
        clues.append(
            Clue(
                id=secondary_id,
                found_at_type=secondary_found_at_type,
                found_at=secondary_found_at,
                reveals=f"A second lead reinforces '{beat.text}' and adds pressure from the campaign's factions and witnesses.",
                points_to=secondary_targets,
                supports_beats=[beat.id],
            )
        )

        if index == 1:
            entry_ids.extend([primary_id, secondary_id])

    return ClueGraph(entry_clue_ids=entry_ids, clues=clues)


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
    progress_callback: Callable[[str], None] | None = None,
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
        clue_graph = _convert_stage_graph(stage_graph, beat_lookup)
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, serialize_clue_graph(clue_graph, plot))
        errors = validate_clue_graph(plot, npcs, locations, clue_graph)
        if not errors:
            return clue_graph
        validation_log.write(f"[clue_chains] repair attempt {attempt}: {'; '.join(errors)}")
        repair_note = "Repair these constraint failures: " + "; ".join(errors)

    validation_log.write("[clue_chains] model-generated clue graph failed after 3 attempts; using deterministic fallback")
    if progress_callback is not None:
        progress_callback("Clue graph model attempts failed; using deterministic fallback")
    fallback_graph = _build_fallback_clue_graph(plot=plot, npcs=npcs, locations=locations)
    if snapshot_path is not None:
        _write_snapshot(snapshot_path, serialize_clue_graph(fallback_graph, plot))
    fallback_errors = validate_clue_graph(plot, npcs, locations, fallback_graph)
    if fallback_errors:
        raise LLMError(
            "clue_chains failed after model attempts and fallback graph validation. "
            f"Fallback errors: {'; '.join(fallback_errors)}"
        )
    return fallback_graph
