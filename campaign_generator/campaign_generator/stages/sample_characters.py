from __future__ import annotations

import json

from common.llm import LLMClient, LLMError, generate_structured
from common.pack import GenrePack

from ..schemas import (
    FactionSet,
    LocationCatalog,
    NPCRoster,
    PlotSkeleton,
    PremiseDocument,
    SampleCharacterSet,
)
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "10_sample_characters.md"


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
    known_npc_names: set[str] | None = None,
) -> SampleCharacterSet:
    """Generate story-mode sample characters.

    v1 packs carried attribute scores and ability lists; samples had to
    validate against both. v2 packs are story-mode only, so each sample
    is just the v2 character template shape (name, concept, advantages,
    disadvantages, belongings, relationships) plus a hook into the
    campaign. The pack's ``advantages_disadvantages.md`` reference is
    passed in as a vocabulary hint.
    """

    count = seed.num_sample_characters or 4

    known_set = set(known_npc_names or ())
    known_npcs = [n for n in npcs.npcs if n.name in known_set]
    if not known_npcs:
        known_npcs = list(npcs.npcs)

    base_context = {
        "pack": {
            "pack_name": pack.metadata.pack_name,
            "display_name": pack.metadata.display_name,
            "advantages_disadvantages": pack.advantages_disadvantages[:4000],
            "character_template": pack.character_template.model_dump(),
        },
        "num_sample_characters": count,
        "protagonist": {
            "archetype": seed.protagonist_archetype,
            "known_facts": list(seed.protagonist_known_facts or []),
        },
        "premise": premise.model_dump(),
        "plot": plot.model_dump(),
        "factions": [{"name": f.name} for f in factions.factions],
        "npcs": [{"name": n.name} for n in known_npcs],
        "locations": [{"name": loc.name} for loc in locations.locations],
    }

    known_names = (
        {f.name for f in factions.factions}
        | {n.name for n in known_npcs}
        | {loc.name for loc in locations.locations}
    )

    repair_note: str | None = None
    last_errors: list[str] = []
    for attempt in range(1, 4):
        context = dict(base_context)
        if repair_note is not None:
            context["repair_note"] = repair_note

        result = generate_structured(
            client=client,
            stage_name="sample_characters",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=SampleCharacterSet,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )

        errors: list[str] = []
        if len(result.characters) != count:
            errors.append(f"expected exactly {count} characters, got {len(result.characters)}")
        for sample in result.characters:
            if len(sample.advantages) < 2:
                errors.append(f"{sample.name!r} needs at least 2 advantages")
            if not sample.disadvantages:
                errors.append(f"{sample.name!r} needs at least 1 disadvantage")

        if not errors:
            for sample in result.characters:
                if known_names and not any(name in sample.hook_into_campaign for name in known_names):
                    validation_log.write(
                        f"[sample-characters] {sample.name!r} hook does not reference any known-at-start faction/NPC/location"
                    )
            return result

        last_errors = errors
        validation_log.write(
            f"[sample-characters] attempt {attempt} semantic validation failed: {'; '.join(errors)}"
        )
        repair_note = "Repair these constraint failures: " + "; ".join(errors)

    raise LLMError(
        "sample_characters could not satisfy semantic constraints after 3 attempts: "
        + "; ".join(last_errors)
    )
