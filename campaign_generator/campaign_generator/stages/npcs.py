from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from ..llm import LLMClient, LLMError, generate_structured
from ..pack import GenrePack
from ..schemas import FactionSet, NPC, NPCRoster, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "04_npc.md"

TITLE_NAME_PATTERN = re.compile(
    r"\b(?:Lady|Lord|Sister|Brother|Foreman|Captain|Master|Mistress|Marshal|Inquisitor|Father|Mother|Baron|Baroness|"
    r"Count|Countess|Duke|Duchess|King|Queen|Prince|Princess|Magister)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
)


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _extract_required_npc_names(plot: PlotSkeleton) -> list[str]:
    names: list[str] = []

    def add(name: str | None) -> None:
        if name and name not in names:
            names.append(name)

    add(plot.main_antagonist.name)
    text_blobs = [
        plot.hook,
        plot.driving_mystery,
        plot.escalation_arc,
        plot.main_antagonist.motivation,
        plot.main_antagonist.secret,
        plot.main_antagonist.relationship_to_protagonist,
    ]
    for act in plot.acts:
        text_blobs.extend([act.title, act.goal])
        text_blobs.extend(beat.text for beat in act.beats)

    for blob in text_blobs:
        for match in TITLE_NAME_PATTERN.findall(blob):
            add(match)

    return names


def _initial_npc_errors(
    *,
    npc: NPC,
    existing_names: set[str],
    must_use_names: set[str],
    faction_names: set[str],
    ability_names: set[str],
) -> list[str]:
    errors: list[str] = []
    if npc.name in existing_names:
        errors.append(f"duplicate NPC name {npc.name!r}")
    if must_use_names and npc.name not in must_use_names:
        errors.append(f"NPC name must be one of {sorted(must_use_names)!r}, got {npc.name!r}")
    if npc.faction_affiliation and npc.faction_affiliation not in faction_names:
        errors.append(f"NPC {npc.name} references unknown faction {npc.faction_affiliation!r}")
    invalid_abilities = [ability for ability in npc.abilities if ability not in ability_names]
    if invalid_abilities:
        errors.append(f"NPC {npc.name} references unknown abilities {invalid_abilities!r}")
    return errors


def _relationship_errors(npc: NPC, roster_names: set[str]) -> list[str]:
    allowed = roster_names | {"{{user}}", npc.name}
    return [
        f"NPC {npc.name} references unknown related NPC {relationship.name!r}"
        for relationship in npc.relationships
        if relationship.name not in allowed
    ]


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
    required_names = _extract_required_npc_names(plot)
    target_count = max(seed.num_npcs or 10, len(required_names))
    roster: list[NPC] = []
    for index in range(target_count):
        if progress_callback is not None:
            progress_callback(f"Generating NPC {index + 1}/{target_count}")
        repair_note = ""
        for semantic_attempt in range(1, 4):
            existing_names = {item.name for item in roster}
            outstanding_required = [name for name in required_names if name not in existing_names]
            slots_remaining = target_count - index
            must_use_names = set(outstanding_required) if slots_remaining == len(outstanding_required) else set()
            context = {
                "premise": premise.model_dump(),
                "plot": plot.model_dump(),
                "factions": factions.model_dump(),
                "existing_npcs": [npc.model_dump() for npc in roster],
                "required_npc_names": required_names,
                "outstanding_required_npc_names": outstanding_required,
                "must_use_one_of_names": sorted(must_use_names),
                "ability_catalog": sorted(pack.ability_names),
                "target_index": index + 1,
                "target_count": target_count,
                "repair_note": repair_note,
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
            errors = _initial_npc_errors(
                npc=npc,
                existing_names=existing_names,
                must_use_names=must_use_names,
                faction_names={faction.name for faction in factions.factions},
                ability_names=pack.ability_names,
            )
            if not errors:
                break
            validation_log.write(f"[npc_{index + 1}] semantic validation failed: {'; '.join(errors)}")
            repair_note = "Repair these constraint failures: " + "; ".join(errors)
        else:
            raise LLMError(f"npc_{index + 1} could not satisfy semantic constraints after 3 attempts")
        roster.append(npc)
        if snapshot_path is not None:
            _write_snapshot(snapshot_path, {"npcs": [item.model_dump() for item in roster]})
        if progress_callback is not None:
            progress_callback(f"Completed NPC {index + 1}/{target_count}: {npc.name}")

    for attempt in range(1, 4):
        roster_names = {npc.name for npc in roster}
        invalid_indexes = [index for index, npc in enumerate(roster) if _relationship_errors(npc, roster_names)]
        if not invalid_indexes:
            return NPCRoster.model_validate({"npcs": [npc.model_dump() for npc in roster]})
        for index in invalid_indexes:
            current_npc = roster[index]
            errors = _relationship_errors(current_npc, roster_names)
            validation_log.write(f"[npc_{index + 1}] relationship repair attempt {attempt}: {'; '.join(errors)}")
            repaired = generate_structured(
                client=client,
                stage_name=f"npc_{index + 1}",
                system_prompt=system_prompt,
                user_prompt=json.dumps(
                    {
                        "premise": premise.model_dump(),
                        "plot": plot.model_dump(),
                        "factions": factions.model_dump(),
                        "existing_npcs": [npc.model_dump() for npc in roster if npc.name != current_npc.name],
                        "required_npc_names": required_names,
                        "outstanding_required_npc_names": [],
                        "must_use_one_of_names": [current_npc.name],
                        "ability_catalog": sorted(pack.ability_names),
                        "allowed_relationship_names": sorted(roster_names | {"{{user}}"}),
                        "target_index": index + 1,
                        "target_count": target_count,
                        "repair_note": "Repair these constraint failures: "
                        + "; ".join(errors)
                        + f". Keep the NPC name exactly {current_npc.name!r}.",
                    },
                    indent=2,
                ),
                schema=NPC,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            repair_errors = _initial_npc_errors(
                npc=repaired,
                existing_names={npc.name for i, npc in enumerate(roster) if i != index},
                must_use_names={current_npc.name},
                faction_names={faction.name for faction in factions.factions},
                ability_names=pack.ability_names,
            ) + _relationship_errors(repaired, roster_names)
            if repair_errors:
                raise LLMError(
                    f"npc relationship repair failed for {current_npc.name!r}: {'; '.join(repair_errors)}"
                )
            roster[index] = repaired

    raise LLMError("NPC roster failed semantic validation after 3 repair attempts")
