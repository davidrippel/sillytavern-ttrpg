from __future__ import annotations

import json

from common.llm import LLMClient, generate_structured
from common.pack import GenrePack

from ..schemas import ComplicationSet, FactionSet, NPCRoster, PlotSkeleton, PremiseDocument, TruthSet
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "07_complications.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    truths: TruthSet,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> ComplicationSet:
    """Generate campaign-specific narrative complications.

    These layer on top of the pack's universal complications list
    (which reaches the GM as ``__pack_complications``). Where the
    pack's complications are genre-flavored (e.g. "the shadows in the
    forest remember"), these are tied to the specific campaign's
    NPCs, locations, and factions.
    """
    context = {
        "premise": premise.model_dump(),
        "thematic_spine": plot.thematic_spine,
        "antagonist": plot.main_antagonist.model_dump(),
        "factions": [
            {"name": f.name, "description": f.description}
            for f in factions.factions
        ],
        "npc_names": [n.name for n in npcs.npcs],
        "truth_count": len(truths.truths),
        "pack_complications_excerpt": pack.complications[:1500] if pack.complications else "",
        "target_count": seed.num_complications or 12,
    }
    return generate_structured(
        client=client,
        stage_name="complications",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=ComplicationSet,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
