from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..llm import LLMClient, generate_structured
from ..pack import GenrePack
from ..schemas import FactionSet, NPC, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "04_npc.md"


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    progress_callback: Callable[[str], None] | None = None,
    snapshot_path: Path | None = None,
) -> NPCRoster:
    target_count = seed.num_npcs or 10
    roster: list[NPC] = []
    for index in range(target_count):
        if progress_callback is not None:
            progress_callback(f"Generating NPC {index + 1}/{target_count}")
        context = {
            "premise": premise.model_dump(),
            "plot": plot.model_dump(),
            "factions": factions.model_dump(),
            "existing_npcs": [npc.model_dump() for npc in roster],
            "ability_catalog": sorted(pack.ability_names),
            "target_index": index + 1,
            "target_count": target_count,
        }
        npc = generate_structured(
            client=client,
            stage_name=f"npc_{index + 1}",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=NPC,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
        roster.append(npc)
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, {"npcs": [item.model_dump() for item in roster]})
        if progress_callback is not None:
            progress_callback(f"Completed NPC {index + 1}/{target_count}: {npc.name}")
    return NPCRoster.model_validate({"npcs": [npc.model_dump() for npc in roster]})
