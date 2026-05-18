from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from common.llm import LLMClient, LLMError, generate_structured

from ..artifacts import serialize_location_list
from ..schemas import FactionSet, Location, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "05_location.md"


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _location_errors(
    location: Location,
    npc_names: set[str],
    existing_names: set[str],
) -> list[str]:
    errors: list[str] = []
    if location.name in existing_names:
        errors.append(f"duplicate location name {location.name!r}")
    invalid_npcs = [name for name in location.npc_names if name not in npc_names]
    if invalid_npcs:
        errors.append(f"location {location.name} references unknown NPCs {invalid_npcs!r}")
    return errors


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
    avoid_names: list[str] | None = None,
    diversity_seed: dict[str, str] | None = None,
) -> LocationCatalog:
    target_count = seed.num_locations or 12
    catalog: list[Location] = []
    roster_names = {npc.name for npc in npcs.npcs}
    for index in range(target_count):
        if progress_callback is not None:
            progress_callback(f"Generating location {index + 1}/{target_count}")
        repair_note = ""
        for attempt in range(1, 4):
            context = {
                "premise": premise.model_dump(),
                "plot": plot.model_dump(),
                "factions": factions.model_dump(),
                "npcs": npcs.model_dump(),
                "npc_name_menu": sorted(roster_names),
                "existing_locations": [location.model_dump() for location in catalog],
                "avoid_names": avoid_names or [],
                "diversity_seed": diversity_seed or {},
                "target_index": index + 1,
                "target_count": target_count,
                "repair_note": repair_note,
            }
            location = generate_structured(
                client=client,
                stage_name=f"location_{index + 1}",
                system_prompt=system_prompt,
                user_prompt=json.dumps(context, indent=2),
                schema=Location,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            existing_names = {item.name for item in catalog}
            errors = _location_errors(location, roster_names, existing_names)
            if not errors:
                break
            validation_log.write(f"[location_{index + 1}] semantic validation failed: {'; '.join(errors)}")
            repair_note = "Repair these constraint failures: " + "; ".join(errors)
        else:
            raise LLMError(f"location_{index + 1} could not satisfy semantic constraints")
        catalog.append(location)
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, serialize_location_list(catalog))
        if progress_callback is not None:
            progress_callback(f"Completed location {index + 1}/{target_count}: {location.name}")
    return LocationCatalog.model_validate({"locations": [location.model_dump() for location in catalog]})
