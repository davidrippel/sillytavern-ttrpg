from __future__ import annotations

import json

from common.llm import LLMClient, generate_structured
from common.pack import GenrePack

from ..schemas import FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument, TruthSet
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "06_truths.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> TruthSet:
    """Generate the campaign's authored truth set.

    Truths are atomic facts that define the underlying situation
    (who's really behind it, what's actually in the cellar, what the
    relic does). They are never injected into the GM's context as a
    set — the extension's pacing module picks one at a time as a
    director's note and the GM is allowed to land *only* that truth
    in fiction.

    Each truth carries `adjacency_keys` — lowercase tokens (NPC names,
    location names, faction names, concept words) the runtime matches
    against live threads and recent facts to decide when this truth
    becomes reveal-eligible.
    """
    context = {
        "premise": premise.model_dump(),
        "central_conflict": premise.central_conflict,
        "thematic_spine": plot.thematic_spine,
        "antagonist": plot.main_antagonist.model_dump(),
        "driving_mystery": plot.driving_mystery,
        "factions": [
            {"name": f.name, "description": f.description, "moral_alignment": f.moral_alignment}
            for f in factions.factions
        ],
        "npc_names": [n.name for n in npcs.npcs],
        "location_names": [l.name for l in locations.locations],
        "target_count": seed.num_truths or 7,
    }
    return generate_structured(
        client=client,
        stage_name="truths",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=TruthSet,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
