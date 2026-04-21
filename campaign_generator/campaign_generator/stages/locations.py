from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..artifacts import serialize_location_catalog, serialize_location_list
from ..llm import LLMClient, generate_structured
from ..schemas import FactionSet, Location, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "05_location.md"


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_plot_beats(plot: PlotSkeleton, beat_refs: list[str]) -> list[str]:
    beat_id_to_text = plot.beat_id_to_text()
    beat_text_to_id = plot.beat_text_to_id()
    normalized: list[str] = []
    for beat_ref in beat_refs:
        if beat_ref in beat_id_to_text:
            normalized.append(beat_ref)
        else:
            normalized.append(beat_text_to_id.get(beat_ref, beat_ref))
    return normalized


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    progress_callback: Callable[[str], None] | None = None,
    snapshot_path: Path | None = None,
) -> LocationCatalog:
    target_count = seed.num_locations or 8
    catalog: list[Location] = []
    all_beats = plot.beat_id_to_text()
    for index in range(target_count):
        if progress_callback is not None:
            progress_callback(f"Generating location {index + 1}/{target_count}")
        context = {
            "premise": premise.model_dump(),
            "plot": plot.model_dump(),
            "factions": factions.model_dump(),
            "npcs": npcs.model_dump(),
            "existing_locations": [location.model_dump() for location in catalog],
            "available_plot_beats": all_beats,
            "target_index": index + 1,
            "target_count": target_count,
        }
        raw_location = generate_structured(
            client=client,
            stage_name=f"location_{index + 1}",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=Location,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
        location = raw_location.model_copy(update={"plot_beats": _normalize_plot_beats(plot, raw_location.plot_beats)})
        catalog.append(location)
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, serialize_location_list(catalog, plot))
        if progress_callback is not None:
            progress_callback(f"Completed location {index + 1}/{target_count}: {location.name}")
    return LocationCatalog.model_validate({"locations": [location.model_dump() for location in catalog]})
