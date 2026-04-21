from __future__ import annotations

import json

from ..llm import LLMClient, generate_structured
from ..schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "07_branches.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clue_graph: ClueGraph,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> BranchPlan:
    context = {
        "premise": premise.model_dump(),
        "plot": plot.model_dump(),
        "factions": factions.model_dump(),
        "npcs": npcs.model_dump(),
        "locations": locations.model_dump(),
        "clues": clue_graph.model_dump(),
        "target_count": seed.branch_points,
    }
    return generate_structured(
        client=client,
        stage_name="branches",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=BranchPlan,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
