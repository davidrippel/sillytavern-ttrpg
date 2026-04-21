from __future__ import annotations

import json

from ..llm import LLMClient, generate_structured
from ..schemas import FactionSet, Location, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "05_location.md"


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
) -> LocationCatalog:
    target_count = seed.num_locations or 8
    catalog: list[Location] = []
    all_beats = [beat for act in plot.acts for beat in act.beats]
    for index in range(target_count):
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
        catalog.append(location)
    return LocationCatalog.model_validate({"locations": [location.model_dump() for location in catalog]})
