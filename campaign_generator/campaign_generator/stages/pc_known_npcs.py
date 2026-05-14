from __future__ import annotations

import json

from pydantic import BaseModel, Field

from common.llm import LLMClient, LLMError, generate_structured

from ..schemas import NodeGraph, NPCRoster, PCKnownNPCs, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog
from .initial_an import find_act_one_start_node


PROMPT_FILE = "09c_pc_known_npc_vet.md"


class _VetResponse(BaseModel):
    known_names: list[str] = Field(default_factory=list)
    introduced_now_names: list[str] = Field(default_factory=list)
    rationale: str = ""


_USER_ALIASES = {"{{user}}", "user", "protagonist", "pc", "the protagonist", "the pc", "player"}


def _is_user_alias(name: str | None) -> bool:
    if not name:
        return False
    return name.strip().lower() in _USER_ALIASES


def _user_relationship_description(npc) -> str:
    for relation in npc.relationships:
        if _is_user_alias(relation.name):
            return relation.description
    return ""


def run(
    *,
    client: LLMClient | None,
    system_prompt: str | None,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    node_graph: NodeGraph,
    npcs: NPCRoster,
    seed: CampaignSeed,
    opening_scene: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    validation_log: ValidationLog,
) -> PCKnownNPCs:
    start_node = find_act_one_start_node(plot, node_graph)
    if start_node is None:
        validation_log.write(
            "[pc_known_npcs] no act-1 start node found; returning empty result"
        )
        return PCKnownNPCs()

    roster_names = {npc.name for npc in npcs.npcs}
    npc_by_name = {npc.name: npc for npc in npcs.npcs}
    candidate_names = [name for name in start_node.relevant_npcs if name in roster_names]
    missing = [name for name in start_node.relevant_npcs if name not in roster_names]
    if missing:
        validation_log.write(
            f"[pc_known_npcs] start node references NPCs not in roster: {missing}"
        )

    base = PCKnownNPCs(
        start_location_name=start_node.relevant_location or None,
        start_node_id=start_node.id,
    )

    if not candidate_names:
        validation_log.write(
            "[pc_known_npcs] start node has no candidate NPCs from the roster; nothing to vet"
        )
        return base

    can_call_llm = (
        client is not None
        and system_prompt is not None
        and model is not None
        and temperature is not None
    )

    if not can_call_llm:
        validation_log.write(
            "[pc_known_npcs] LLM unavailable; falling back to candidates-as-known"
        )
        return base.model_copy(update={"known_names": list(candidate_names)})

    candidate_payload = []
    for name in candidate_names:
        npc = npc_by_name[name]
        candidate_payload.append(
            {
                "name": npc.name,
                "role": npc.role,
                "summary": npc.motivation,
                "relationship_to_user": _user_relationship_description(npc),
            }
        )

    context = {
        "premise_paragraphs": premise.paragraphs,
        "tone_statement": premise.tone_statement,
        "central_conflict": premise.central_conflict,
        "opening_scene": opening_scene or "",
        "opening_node_description": start_node.description,
        "protagonist_known_facts": list(seed.protagonist_known_facts or []),
        "candidate_npcs": candidate_payload,
    }

    try:
        response = generate_structured(
            client=client,
            stage_name="pc_known_npcs",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=_VetResponse,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
    except LLMError as exc:
        validation_log.write(
            f"[pc_known_npcs] LLM call failed ({exc}); falling back to candidates-as-known"
        )
        return base.model_copy(update={"known_names": list(candidate_names)})

    candidate_set = set(candidate_names)
    known = [name for name in response.known_names if name in candidate_set]
    introduced = [name for name in response.introduced_now_names if name in candidate_set]
    known_set = set(known)
    introduced_set = set(introduced)

    overlap = known_set & introduced_set
    if overlap:
        validation_log.write(
            f"[pc_known_npcs] LLM produced overlapping names {sorted(overlap)}; treating as known"
        )
        introduced = [name for name in introduced if name not in known_set]
        introduced_set = set(introduced)

    covered = known_set | introduced_set
    uncovered = candidate_set - covered
    if uncovered:
        validation_log.write(
            f"[pc_known_npcs] LLM did not classify {sorted(uncovered)}; defaulting them to introduced_now"
        )
        introduced.extend(sorted(uncovered))

    return base.model_copy(
        update={
            "known_names": known,
            "introduced_now_names": introduced,
        }
    )
