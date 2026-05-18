from __future__ import annotations

import json

from common.llm import LLMClient, generate_structured

from ..schemas import BranchPlan, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument, TruthSet
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "08_branches.md"


def _build_reference_token_map(
    *,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    truths: TruthSet,
) -> dict[str, str]:
    """v2: branches reference NPCs, locations, factions, and (optionally)
    truth ids by name. v1 also let them reference beat ids and clue
    ids; both concepts are retired.
    """
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
    for truth in truths.truths:
        register(truth.id)

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
    truths: TruthSet,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> BranchPlan:
    reference_token_map = _build_reference_token_map(
        factions=factions,
        npcs=npcs,
        locations=locations,
        truths=truths,
    )
    context = {
        "premise": premise.model_dump(),
        "plot": plot.model_dump(),
        "factions": factions.model_dump(),
        "npcs": npcs.model_dump(),
        "locations": locations.model_dump(),
        "truths": truths.model_dump(),
        "reference_menu": sorted(reference_token_map),
        "target_count": 6,
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
    valid_values = set(reference_token_map.values())
    for branch in normalized_payload["branches"]:
        cleaned: list[str] = []
        for raw_reference in branch["references"]:
            normalized = reference_token_map.get(raw_reference, raw_reference)
            if normalized in valid_values:
                cleaned.append(normalized)
            else:
                validation_log.write(
                    f"[branches] dropped unresolvable reference {raw_reference!r} from branch "
                    f"{branch['name']!r} (not in reference_menu)"
                )
        branch["references"] = cleaned
    return BranchPlan.model_validate(normalized_payload)
