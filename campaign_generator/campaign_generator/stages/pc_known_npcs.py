"""Partition the NPC roster into PC-knew-them-already vs. introduced-now.

The NPC stage asks the LLM for relationships *including* ties that
only form during the campaign. The opening-hook "What you already
know" section needs the narrower set — NPCs the protagonist knew
*before* play began. A single small LLM call does the vetting here.

Inputs: premise + plot + the NPC roster with each NPC's
``relationships`` blurb describing their tie to ``{{user}}`` + the
seed's optional ``protagonist_known_facts``.

Output: the v2 ``PCKnownNPCs`` shape — two lists of NPC names that
together cover only the NPCs that carried a ``{{user}}``-tagged
relationship in the roster.
"""
from __future__ import annotations

import json

from common.llm import LLMClient, generate_structured

from ..schemas import NPCRoster, PCKnownNPCs, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "09c_pc_known_npc_vet.md"

_USER_ALIASES = {"{{user}}", "user", "the protagonist", "protagonist", "the pc", "pc"}


def _candidate_npcs(npcs: NPCRoster) -> list[dict]:
    """NPCs whose roster entry flagged a relationship to ``{{user}}``."""
    out: list[dict] = []
    for npc in npcs.npcs:
        for rel in npc.relationships or []:
            if (rel.name or "").strip().lower() in _USER_ALIASES:
                out.append(
                    {
                        "name": npc.name,
                        "role": npc.role,
                        "relation_to_protagonist": rel.description,
                    }
                )
                break
    return out


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> PCKnownNPCs:
    candidates = _candidate_npcs(npcs)
    # Nothing flagged a {{user}} tie → nothing to vet.
    if not candidates:
        return PCKnownNPCs()

    context = {
        "premise": premise.model_dump(),
        "hook": plot.hook,
        "antagonist": plot.main_antagonist.model_dump(),
        "protagonist_archetype": seed.protagonist_archetype,
        "protagonist_known_facts": list(seed.protagonist_known_facts or []),
        "candidates": candidates,
    }
    result = generate_structured(
        client=client,
        stage_name="pc_known_npcs",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=PCKnownNPCs,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )

    # Defensive: clamp every name back to the candidate set so a confused
    # LLM can't ship a campaign that points the opening hook at someone
    # the roster never mentioned.
    candidate_names = {c["name"] for c in candidates}
    cleaned = PCKnownNPCs(
        known_names=[n for n in result.known_names if n in candidate_names],
        introduced_now_names=[n for n in result.introduced_now_names if n in candidate_names],
    )

    # If the LLM left some candidates uncategorised, surface that to the
    # log — but don't fail the run; the opening hook degrades gracefully.
    seen = set(cleaned.known_names) | set(cleaned.introduced_now_names)
    missing = sorted(candidate_names - seen)
    if missing:
        validation_log.write(
            f"[pc_known_npcs] LLM left {len(missing)} candidate(s) uncategorised: {missing}"
        )

    return cleaned
