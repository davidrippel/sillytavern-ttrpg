from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..artifacts import serialize_clue_graph
from common.llm import LLMClient, LLMError, generate_structured
from ..schemas import Clue, ClueGraph, ClueTarget, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from common.settings import get_use_llm_clue_graph
from ..validation import ValidationLog, validate_clue_graph


PROMPT_FILE = "06_clue_chains.md"
PROSE_PROMPT_FILE = "06b_clue_prose.md"


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


def _normalize_beat_reference(plot: PlotSkeleton, value: str) -> str | None:
    beat_lookup = plot.beat_id_to_text()
    if value in beat_lookup:
        return value
    return plot.beat_text_to_id().get(value)


def _extract_candidate_beats(plot: PlotSkeleton, clue: Clue) -> list[str]:
    beat_ids: list[str] = []
    for beat_ref in clue.supports_beats:
        normalized = _normalize_beat_reference(plot, beat_ref)
        if normalized and normalized not in beat_ids:
            beat_ids.append(normalized)
    for target in clue.points_to:
        if target.type != "beat":
            continue
        normalized = _normalize_beat_reference(plot, target.value)
        if normalized and normalized not in beat_ids:
            beat_ids.append(normalized)
    return beat_ids


def _valid_anchor(clue: Clue, npc_names: set[str], location_names: set[str]) -> bool:
    if clue.found_at_type == "npc":
        return clue.found_at in npc_names
    if clue.found_at_type == "location":
        return clue.found_at in location_names
    return False


def _next_synthetic_id(used_ids: set[str], beat_index: int, slot_label: str) -> str:
    base = f"repair_clue{beat_index:02d}{slot_label}"
    candidate = base
    suffix = 1
    while candidate in used_ids:
        suffix += 1
        candidate = f"{base}_{suffix}"
    used_ids.add(candidate)
    return candidate


def _synthetic_reveals(plot: PlotSkeleton, beat_text: str, slot_label: str) -> str:
    if slot_label == "a":
        return f"Evidence tied to '{beat_text}' points toward a larger pattern behind {plot.driving_mystery.lower()}"
    return f"A second lead reinforces '{beat_text}' and adds pressure from the campaign's factions and witnesses."


def _build_synthetic_clue(
    *,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
    beat_index: int,
    beat_id: str,
    beat_text: str,
    slot_label: str,
    used_ids: set[str],
) -> Clue:
    npc_cycle = npcs.npcs or []
    location_cycle = locations.locations or []
    if not npc_cycle and not location_cycle:
        raise LLMError("cannot build fallback clue graph without NPCs or locations")
    location = location_cycle[(beat_index - 1) % len(location_cycle)] if location_cycle else None
    npc = npc_cycle[(beat_index - 1) % len(npc_cycle)] if npc_cycle else None

    if slot_label == "a":
        found_at_type = "location" if location is not None else "npc"
        found_at = location.name if location is not None else npc.name
    else:
        found_at_type = "npc" if npc is not None else "location"
        found_at = npc.name if npc is not None else location.name

    return Clue(
        id=_next_synthetic_id(used_ids, beat_index, slot_label),
        found_at_type=found_at_type,
        found_at=found_at,
        reveals=_synthetic_reveals(plot, beat_text, slot_label),
        points_to=[ClueTarget(type="beat", value=beat_id)],
        supports_beats=[beat_id],
    )


def _dedupe_targets(targets: list[ClueTarget]) -> list[ClueTarget]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ClueTarget] = []
    for target in targets:
        key = (target.type, target.value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def _rebuild_clue_targets(
    clue: Clue,
    *,
    beat_id: str,
    next_primary_id: str | None,
    secondary_id: str | None,
    npc_names: set[str],
    location_names: set[str],
) -> list[ClueTarget]:
    targets: list[ClueTarget] = [ClueTarget(type="beat", value=beat_id)]
    if secondary_id is not None and secondary_id != clue.id:
        targets.append(ClueTarget(type="clue", value=secondary_id))
    if next_primary_id is not None and next_primary_id != clue.id:
        targets.append(ClueTarget(type="clue", value=next_primary_id))
    for target in clue.points_to:
        if target.type == "npc" and target.value in npc_names:
            targets.append(target)
        if target.type == "location" and target.value in location_names:
            targets.append(target)
    return _dedupe_targets(targets)


def _build_hybrid_fallback_clue_graph(
    *,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
    candidate_graph: ClueGraph,
) -> tuple[ClueGraph, int, int]:
    beat_list = [beat for act in plot.acts for beat in act.beats]
    if not beat_list:
        raise LLMError("cannot build fallback clue graph without plot beats")
    if not npcs.npcs and not locations.locations:
        raise LLMError("cannot build fallback clue graph without NPCs or locations")

    npc_names = {npc.name for npc in npcs.npcs}
    location_names = {location.name for location in locations.locations}
    beat_order = {beat.id: index for index, beat in enumerate(beat_list)}
    beat_lookup = plot.beat_id_to_text()
    used_ids: set[str] = set()
    preserved_by_beat: dict[str, list[Clue]] = defaultdict(list)

    for clue in candidate_graph.clues:
        if not _valid_anchor(clue, npc_names, location_names):
            continue
        clue_beats = _extract_candidate_beats(plot, clue)
        if not clue_beats:
            continue
        primary_beat = min(clue_beats, key=lambda beat_id: beat_order[beat_id])
        if len(preserved_by_beat[primary_beat]) >= 2:
            continue
        preserved_by_beat[primary_beat].append(clue)
        used_ids.add(clue.id)

    selected_pairs: list[tuple[Clue, Clue]] = []
    preserved_count = 0
    synthetic_count = 0
    for beat_index, beat in enumerate(beat_list, start=1):
        preserved = list(preserved_by_beat.get(beat.id, []))
        preserved_count += len(preserved)
        while len(preserved) < 2:
            preserved.append(
                _build_synthetic_clue(
                    plot=plot,
                    npcs=npcs,
                    locations=locations,
                    beat_index=beat_index,
                    beat_id=beat.id,
                    beat_text=beat.text,
                    slot_label="a" if len(preserved) == 0 else "b",
                    used_ids=used_ids,
                )
            )
            synthetic_count += 1
        selected_pairs.append((preserved[0], preserved[1]))

    rebuilt_clues: list[Clue] = []
    for beat_index, beat in enumerate(beat_list):
        primary, secondary = selected_pairs[beat_index]
        next_primary_id = selected_pairs[beat_index + 1][0].id if beat_index + 1 < len(selected_pairs) else None
        rebuilt_clues.append(
            primary.model_copy(
                update={
                    "points_to": _rebuild_clue_targets(
                        primary,
                        beat_id=beat.id,
                        next_primary_id=next_primary_id,
                        secondary_id=secondary.id,
                        npc_names=npc_names,
                        location_names=location_names,
                    ),
                    "supports_beats": [beat.id],
                }
            )
        )
        rebuilt_clues.append(
            secondary.model_copy(
                update={
                    "points_to": _rebuild_clue_targets(
                        secondary,
                        beat_id=beat.id,
                        next_primary_id=next_primary_id,
                        secondary_id=None,
                        npc_names=npc_names,
                        location_names=location_names,
                    ),
                    "supports_beats": [beat.id],
                }
            )
        )

    graph = ClueGraph(entry_clue_ids=[selected_pairs[0][0].id, selected_pairs[0][1].id], clues=rebuilt_clues)
    return graph, preserved_count, synthetic_count


def build_clue_skeleton(
    *,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
) -> ClueGraph:
    """Build a structurally-valid clue graph deterministically from the plot,
    NPCs, and locations. Every beat receives exactly two clues that point at
    it, and the ordering wires successive beats together so that every clue is
    reachable from the entry pair."""
    anchor_type = "location" if locations.locations else "npc"
    anchor_name = (
        locations.locations[0].name if locations.locations else npcs.npcs[0].name
    )
    first_beat_id = plot.acts[0].beats[0].id
    first_beat_text = plot.acts[0].beats[0].text
    seed_clues = [
        Clue(
            id=f"__skeleton_seed_{index}__",
            found_at_type=anchor_type,
            found_at=anchor_name,
            reveals=_synthetic_reveals(plot, first_beat_text, "a" if index % 2 == 0 else "b"),
            points_to=[ClueTarget(type="beat", value=first_beat_id)],
            supports_beats=[first_beat_id],
        )
        for index in range(4)
    ]
    seed_graph = ClueGraph(
        entry_clue_ids=[seed_clues[0].id],
        clues=seed_clues,
    )
    graph, _, _ = _build_hybrid_fallback_clue_graph(
        plot=plot,
        npcs=npcs,
        locations=locations,
        candidate_graph=seed_graph,
    )
    return graph


def _summarize_npc(npcs: NPCRoster, name: str) -> dict[str, str] | None:
    for npc in npcs.npcs:
        if npc.name == name:
            return {
                "name": npc.name,
                "role": npc.role,
                "speaking_style": npc.speaking_style,
                "motivation": npc.motivation,
            }
    return None


def _summarize_location(locations: LocationCatalog, name: str) -> dict[str, object] | None:
    for location in locations.locations:
        if location.name == name:
            return {
                "name": location.name,
                "type": location.type,
                "notable_features": location.notable_features,
            }
    return None


def _enrich_clue_prose(
    *,
    client: LLMClient,
    system_prompt: str,
    clue: Clue,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
    premise: PremiseDocument,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> tuple[Clue, bool]:
    """Ask the LLM to rewrite only the `reveals` field of a single clue.
    Returns (possibly-updated clue, llm_success_flag)."""
    beat_lookup = plot.beat_id_to_text()
    beat_targets = [t.value for t in clue.points_to if t.type == "beat"]
    beat_context = [
        {"id": beat_id, "text": beat_lookup.get(beat_id, beat_id)}
        for beat_id in beat_targets
    ] or [
        {"id": beat_id, "text": beat_lookup.get(beat_id, beat_id)}
        for beat_id in clue.supports_beats
    ]

    if clue.found_at_type == "npc":
        anchor_context = _summarize_npc(npcs, clue.found_at)
    else:
        anchor_context = _summarize_location(locations, clue.found_at)

    context = {
        "premise_summary": {
            "central_conflict": premise.central_conflict,
            "tone_statement": premise.tone_statement,
        },
        "clue": {
            "id": clue.id,
            "found_at_type": clue.found_at_type,
            "found_at": clue.found_at,
            "points_to": [t.model_dump() for t in clue.points_to],
            "supports_beats": clue.supports_beats,
        },
        "found_at_context": anchor_context or {"name": clue.found_at},
        "beat_context": beat_context,
    }

    try:
        result = generate_structured(
            client=client,
            stage_name=f"clue_prose_{clue.id}",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=StageClue,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
    except LLMError as exc:
        validation_log.write(
            f"[clue_chains] prose enrichment for {clue.id} failed; keeping templated reveals. {exc}"
        )
        return clue, False

    new_reveals = (result.reveals or "").strip()
    if not new_reveals:
        validation_log.write(
            f"[clue_chains] prose enrichment for {clue.id} returned empty reveals; keeping templated text."
        )
        return clue, False

    return clue.model_copy(update={"reveals": new_reveals}), True


def _run_legacy_llm_first(
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
    snapshot_path: Path | None,
    progress_callback: Callable[[str], None] | None,
) -> ClueGraph | None:
    """Legacy path: ask the LLM to produce the entire graph, retry on validation
    failure. Returns the graph on success, or None on persistent failure (caller
    should fall through to the deterministic skeleton)."""
    repair_note = ""
    beat_lookup = _build_beat_lookup(plot)
    target_clues = _target_clue_count(density, len(beat_lookup))
    clue_graph: ClueGraph | None = None
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
            validation_log.write(f"[clue_chains] legacy LLM-first attempt {attempt} raised: {exc}")
            return None
        clue_graph = _convert_stage_graph(stage_graph, beat_lookup)
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, serialize_clue_graph(clue_graph, plot))
        errors = validate_clue_graph(plot, npcs, locations, clue_graph)
        if not errors:
            return clue_graph
        validation_log.write(f"[clue_chains] legacy LLM-first attempt {attempt} validation: {'; '.join(errors)}")
        repair_note = "Repair these constraint failures: " + "; ".join(errors)
    return None


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
    prose_system_prompt: str | None = None,
) -> ClueGraph:
    """Generate a clue graph by:
    1. Optionally trying the legacy LLM-builds-whole-graph path (off by default,
       opt-in via CG_LLM_CLUE_GRAPH=1).
    2. Otherwise (default) building a deterministic skeleton from beats/NPCs/
       locations, then asking the LLM to enrich each clue's `reveals` prose in
       isolation. The graph topology is never at risk; only prose can degrade,
       and degradation falls back to the deterministic templated text.
    """
    if get_use_llm_clue_graph():
        if progress_callback is not None:
            progress_callback("Clue graph: attempting LLM-first mode (CG_LLM_CLUE_GRAPH=1)")
        legacy_graph = _run_legacy_llm_first(
            client=client,
            system_prompt=system_prompt,
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            locations=locations,
            density=density,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
            snapshot_path=snapshot_path,
            progress_callback=progress_callback,
        )
        if legacy_graph is not None:
            errors = validate_clue_graph(plot, npcs, locations, legacy_graph)
            if not errors:
                if progress_callback is not None:
                    progress_callback("Clue graph: LLM-first succeeded")
                validation_log.write(
                    "[clue_chains] LLM-first mode produced a valid graph with "
                    f"{len(legacy_graph.clues)} clues"
                )
                return legacy_graph
        if progress_callback is not None:
            progress_callback("Clue graph: LLM-first failed; falling through to deterministic skeleton")
        validation_log.write("[clue_chains] LLM-first mode failed; falling through to deterministic skeleton")

    skeleton = build_clue_skeleton(plot=plot, npcs=npcs, locations=locations)
    skeleton_errors = validate_clue_graph(plot, npcs, locations, skeleton)
    if skeleton_errors:
        raise LLMError(
            "clue_chains deterministic skeleton failed validation; this indicates a bug. "
            f"Errors: {'; '.join(skeleton_errors)}"
        )

    enriched_clues: list[Clue] = []
    enriched_count = 0
    if prose_system_prompt is None:
        enriched_clues = list(skeleton.clues)
    else:
        for index, clue in enumerate(skeleton.clues, start=1):
            if progress_callback is not None:
                progress_callback(f"Enriching clue prose {index}/{len(skeleton.clues)}: {clue.id}")
            updated, used_llm = _enrich_clue_prose(
                client=client,
                system_prompt=prose_system_prompt,
                clue=clue,
                plot=plot,
                npcs=npcs,
                locations=locations,
                premise=premise,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            enriched_clues.append(updated)
            if used_llm:
                enriched_count += 1

    final_graph = ClueGraph(entry_clue_ids=skeleton.entry_clue_ids, clues=enriched_clues)
    final_errors = validate_clue_graph(plot, npcs, locations, final_graph)
    if final_errors:
        raise LLMError(
            "clue_chains failed validation after prose enrichment (this should not happen — "
            f"prose enrichment must not alter topology). Errors: {'; '.join(final_errors)}"
        )

    template_count = len(final_graph.clues) - enriched_count
    summary = (
        f"Clue graph: skeleton produced {len(final_graph.clues)} clues, "
        f"{enriched_count} enriched by LLM, {template_count} used template fallback"
    )
    validation_log.write(f"[clue_chains] {summary}")
    if progress_callback is not None:
        progress_callback(summary)

    if snapshot_path is not None:
        _write_snapshot(snapshot_path, serialize_clue_graph(final_graph, plot))

    return final_graph
