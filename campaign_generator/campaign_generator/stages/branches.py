from __future__ import annotations

import json

from ..llm import LLMClient, generate_structured
from ..schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "07_branches.md"


def _normalize_reference(reference: str, token_map: dict[str, str]) -> str:
    return token_map.get(reference, reference)


def _build_reference_token_map(
    *,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clue_graph: ClueGraph,
) -> dict[str, str]:
    token_map: dict[str, str] = {}

    def register(value: str) -> None:
        token_map.setdefault(value, value)
        if value.startswith("The "):
            token_map.setdefault(value[4:], value)

    for faction in factions.factions:
        register(faction.name)
    for npc in npcs.npcs:
        register(npc.name)
    for location in locations.locations:
        register(location.name)
    for clue in clue_graph.clues:
        register(clue.id)
    for beat_id, beat_text in plot.beat_id_to_text().items():
        token_map.setdefault(beat_id, beat_id)
        token_map.setdefault(beat_text, beat_id)

    return token_map


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
    reference_token_map = _build_reference_token_map(
        plot=plot,
        factions=factions,
        npcs=npcs,
        locations=locations,
        clue_graph=clue_graph,
    )
    context = {
        "premise": premise.model_dump(),
        "plot": plot.model_dump(),
        "factions": factions.model_dump(),
        "npcs": npcs.model_dump(),
        "locations": locations.model_dump(),
        "clues": clue_graph.model_dump(),
        "reference_menu": sorted(reference_token_map),
        "target_count": seed.branch_points,
    }
    raw_plan = generate_structured(
        client=client,
        stage_name="branches",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=BranchPlan,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
    normalized_payload = raw_plan.model_dump()
    for branch in normalized_payload["branches"]:
        branch["references"] = [_normalize_reference(reference, reference_token_map) for reference in branch["references"]]
    return BranchPlan.model_validate(normalized_payload)
