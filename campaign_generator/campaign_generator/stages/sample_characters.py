from __future__ import annotations

import json

from common.llm import LLMClient, generate_structured
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


PROMPT_FILE = "12_sample_characters.md"


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
) -> SampleCharacterSet:
    pack_attribute_keys = list(pack.attribute_keys)
    ability_names = sorted(pack.ability_names)

    count = seed.num_sample_characters or 5

    known_npcs = [
        n for n in npcs.npcs
        if any(getattr(rel, "known_at_start", True) for rel in (n.relationships or []))
    ]
    if not known_npcs:
        validation_log.write(
            "[sample-characters] no NPCs marked known_at_start; falling back to full roster for hooks"
        )
        known_npcs = list(npcs.npcs)

    context = {
        "pack": {
            "pack_name": pack.metadata.pack_name,
            "display_name": pack.metadata.display_name,
            "attributes": [
                {"key": attr.key, "display": attr.display, "description": attr.description}
                for attr in pack.attributes.attributes
            ],
            "attribute_keys": pack_attribute_keys,
            "abilities": ability_names,
            "character_template": pack.character_template,
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

    if len(result.characters) != count:
        raise ValueError(
            f"sample_characters: expected exactly {count} characters, got {len(result.characters)}"
        )

    valid_keys = set(pack_attribute_keys)
    valid_abilities = set(ability_names)
    known_names = (
        {f.name for f in factions.factions}
        | {n.name for n in known_npcs}
        | {loc.name for loc in locations.locations}
    )

    for sample in result.characters:
        bad_attrs = [key for key in sample.pack.attributes if key not in valid_keys]
        if bad_attrs:
            raise ValueError(
                f"sample character {sample.archetype!r} references unknown attribute keys: {bad_attrs}"
            )
        bad_abilities = [name for name in sample.pack.abilities if name not in valid_abilities]
        if bad_abilities:
            raise ValueError(
                f"sample character {sample.archetype!r} references unknown abilities: {bad_abilities}"
            )
        if known_names and not any(name in sample.hook_into_campaign for name in known_names):
            validation_log.write(
                f"[sample-characters] {sample.archetype!r} hook does not reference any known-at-start faction/NPC/location"
            )

    return result
