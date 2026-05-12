"""LLM-driven node graph generator.

Per act, generates:
  1. A start node (act 1 only; acts 2+ inherit prev act's final node).
  2. A final node (the act's culmination — the player must reach it to advance).
  3. Three intermediate "points of interest" — optional, unordered, parallel
     scenes the player can engage with on the way to the final node.

The LLM picks the act's relevant NPCs and locations as part of generating
the first node it produces for that act (start for act 1, final for acts 2+).
Subsequent prompts for that act reuse the picked subset.

Total LLM calls per campaign with N acts: `1 + N*(1 + 3) = 4N + 1`.
With the default 3 acts: 13 calls.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from common.llm import LLMClient, LLMError, generate_structured
from ..schemas import (
    LocationCatalog,
    Node,
    NodeGraph,
    NPCRoster,
    PlotSkeleton,
    PremiseDocument,
)
from ..validation import ValidationLog


PROMPT_START = "08a_node_start.md"
PROMPT_FINAL = "08b_node_final.md"
PROMPT_INTERMEDIATE = "08c_node_intermediate.md"

DEFAULT_NODES_PER_ACT = 5
MIN_NODES_PER_ACT = 3
MAX_NODES_PER_ACT = 10


# ---- LLM response schemas ----


class _ActSelection(BaseModel):
    """Subset of NPCs/locations relevant to this act, picked by the LLM
    alongside the first node it generates."""
    relevant_npcs_for_act: list[str] = Field(min_length=1)
    relevant_locations_for_act: list[str] = Field(min_length=1)


class _NodeProposal(BaseModel):
    """A single node proposal from the LLM."""
    kind: Literal["location", "npc_encounter", "event"]
    description: str = Field(min_length=20, max_length=400)
    relevant_npcs: list[str] = Field(default_factory=list)
    relevant_location: str | None = None


class _StartNodeWithActSelection(_NodeProposal, _ActSelection):
    """First node of act 1 — bundles the act-1 NPC/location selection."""


class _FinalNodeWithActSelection(_NodeProposal, _ActSelection):
    """Final node of acts 2+ — bundles the act's NPC/location selection."""


class _FinalNode(_NodeProposal):
    """Final node of act 1 (act selection already picked at start)."""


class _IntermediateNode(_NodeProposal):
    """Intermediate (point of interest) node."""


# ---- Helpers ----


def _slug(text: str, used: set[str]) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    base = cleaned[:48] or "node"
    candidate = base
    suffix = 1
    while candidate in used:
        suffix += 1
        candidate = f"{base}_{suffix}"
    used.add(candidate)
    return candidate


def _filter_relevant_npcs(picked: list[str], allowed: set[str]) -> list[str]:
    """Keep only NPC names that exist in the allowed set (silently drop hallucinations)."""
    out: list[str] = []
    for name in picked:
        if name in allowed and name not in out:
            out.append(name)
    return out


def _filter_relevant_location(picked: str | None, allowed: set[str]) -> str | None:
    if picked and picked in allowed:
        return picked
    return None


def _build_node(
    *,
    proposal: _NodeProposal,
    act_number: int,
    act_npcs: set[str],
    act_locations: set[str],
    used_ids: set[str],
    is_act_start: bool,
    is_act_final: bool,
    is_victory: bool,
    triggers: str,
) -> Node:
    description = proposal.description.strip()[:400]
    relevant_npcs = _filter_relevant_npcs(proposal.relevant_npcs, act_npcs)
    relevant_location = _filter_relevant_location(proposal.relevant_location, act_locations)
    node_id = _slug(description, used_ids)
    return Node(
        id=node_id,
        kind=proposal.kind,
        description=description,
        act_number=act_number,
        is_act_start=is_act_start,
        is_act_final=is_act_final,
        is_victory=is_victory,
        triggers=triggers,
        relevant_npcs=relevant_npcs,
        relevant_location=relevant_location,
    )


def _summarize_npcs(npcs: NPCRoster) -> list[dict]:
    return [
        {
            "name": npc.name,
            "role": npc.role,
            "motivation": npc.motivation,
            "speaking_style": npc.speaking_style,
        }
        for npc in npcs.npcs
    ]


def _summarize_locations(locations: LocationCatalog) -> list[dict]:
    return [
        {
            "name": loc.name,
            "type": loc.type,
            "notable_features": loc.notable_features,
        }
        for loc in locations.locations
    ]


def _act_summary(plot: PlotSkeleton, act_index: int) -> dict:
    act = plot.acts[act_index]
    return {
        "act_number": act.act_number,
        "title": act.title,
        "goal": act.goal,
        "beats_as_texture": [b.text for b in act.beats],
    }


# ---- Stage entry ----


def run(
    *,
    client: LLMClient,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    snapshot_path: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
    prompts: dict[str, str] | None = None,
    nodes_per_act: int = DEFAULT_NODES_PER_ACT,
) -> NodeGraph:
    """Generate the node graph via per-act LLM calls.

    Each act has `nodes_per_act` nodes: a start (act 1 only; acts 2+ inherit
    the previous act's final), `nodes_per_act - 2` intermediates, and a final.

    `prompts` is a mapping from prompt-file basename to its loaded text.
    """
    if not (MIN_NODES_PER_ACT <= nodes_per_act <= MAX_NODES_PER_ACT):
        raise ValueError(
            f"nodes_per_act must be in [{MIN_NODES_PER_ACT}, {MAX_NODES_PER_ACT}]; got {nodes_per_act}"
        )
    intermediate_count = nodes_per_act - 2
    prompts = prompts or {}
    npc_names = {n.name for n in npcs.npcs}
    location_names = {l.name for l in locations.locations}

    nodes: list[Node] = []
    used_ids: set[str] = set()
    previous_acts_finals: list[dict] = []  # for acts 2+, pass prior finals as context

    for act_index, act in enumerate(plot.acts):
        act_number = act.act_number or (act_index + 1)
        is_last_act = act_index == len(plot.acts) - 1
        act_npcs: set[str] = set()
        act_locations: set[str] = set()

        # --- Step 1: act 1's start node (with act-1 selection bundled).
        if act_index == 0:
            if progress_callback is not None:
                progress_callback(f"Generating act {act_number} start node")
            context = {
                "premise": {
                    "title": premise.title,
                    "central_conflict": premise.central_conflict,
                    "tone_statement": premise.tone_statement,
                },
                "plot": {
                    "hook": plot.hook,
                    "driving_mystery": plot.driving_mystery,
                },
                "act": _act_summary(plot, act_index),
                "npc_roster": _summarize_npcs(npcs),
                "location_catalog": _summarize_locations(locations),
            }
            proposal: _StartNodeWithActSelection = generate_structured(
                client=client,
                stage_name=f"act_{act_number}_start",
                system_prompt=prompts.get(PROMPT_START, ""),
                user_prompt=json.dumps(context, indent=2),
                schema=_StartNodeWithActSelection,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            act_npcs = set(_filter_relevant_npcs(proposal.relevant_npcs_for_act, npc_names))
            act_locations = set(_filter_relevant_locations(proposal.relevant_locations_for_act, location_names))
            if not act_npcs:
                act_npcs = set(npc_names)
            if not act_locations:
                act_locations = set(location_names)
            start_node = _build_node(
                proposal=proposal,
                act_number=act_number,
                act_npcs=act_npcs,
                act_locations=act_locations,
                used_ids=used_ids,
                is_act_start=True,
                is_act_final=False,
                is_victory=False,
                triggers="Opening scene of the act.",
            )
            nodes.append(start_node)
        else:
            # Reuse the previous act's final node as this act's start. We don't
            # create a new node — the previous loop iteration already appended
            # the transition node with both is_act_final and is_act_start set.
            prev_final = nodes[-1]
            # Confirm the previous act's final was a transition (not a victory).
            if not (prev_final.is_act_final and prev_final.is_act_start and not prev_final.is_victory):
                raise LLMError(
                    f"expected act {act_number-1}'s final node to be a transition; got {prev_final}"
                )
            # We'll need the act's NPC/location selection — done in the final
            # node prompt below, since acts 2+ have no separate "start" prompt.

        # --- Step 2: this act's final node.
        if progress_callback is not None:
            progress_callback(f"Generating act {act_number} final node")
        final_context = {
            "premise": {
                "central_conflict": premise.central_conflict,
                "tone_statement": premise.tone_statement,
            },
            "plot": {"driving_mystery": plot.driving_mystery},
            "act": _act_summary(plot, act_index),
            "act_start_node": {
                "id": nodes[-1].id if act_index > 0 else nodes[-1].id,
                "description": nodes[-1].description,
            },
            "previous_acts_finals": previous_acts_finals,
            "is_campaign_climax": is_last_act,
        }
        if act_index == 0:
            # Act 1: selection already made; pass it in for grounding.
            final_context["act_npcs"] = sorted(act_npcs)
            final_context["act_locations"] = sorted(act_locations)
            final_proposal: _FinalNode = generate_structured(
                client=client,
                stage_name=f"act_{act_number}_final",
                system_prompt=prompts.get(PROMPT_FINAL, ""),
                user_prompt=json.dumps(final_context, indent=2),
                schema=_FinalNode,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
        else:
            # Acts 2+: selection picked here.
            final_context["npc_roster"] = _summarize_npcs(npcs)
            final_context["location_catalog"] = _summarize_locations(locations)
            final_with_sel: _FinalNodeWithActSelection = generate_structured(
                client=client,
                stage_name=f"act_{act_number}_final",
                system_prompt=prompts.get(PROMPT_FINAL, ""),
                user_prompt=json.dumps(final_context, indent=2),
                schema=_FinalNodeWithActSelection,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            act_npcs = set(_filter_relevant_npcs(final_with_sel.relevant_npcs_for_act, npc_names))
            act_locations = set(_filter_relevant_locations(final_with_sel.relevant_locations_for_act, location_names))
            if not act_npcs:
                act_npcs = set(npc_names)
            if not act_locations:
                act_locations = set(location_names)
            final_proposal = _FinalNode(
                kind=final_with_sel.kind,
                description=final_with_sel.description,
                relevant_npcs=final_with_sel.relevant_npcs,
                relevant_location=final_with_sel.relevant_location,
            )

        final_node = _build_node(
            proposal=final_proposal,
            act_number=act_number,
            act_npcs=act_npcs,
            act_locations=act_locations,
            used_ids=used_ids,
            is_act_start=False,  # set to True below if this is a transition node
            is_act_final=True,
            is_victory=is_last_act,
            triggers="Campaign climax." if is_last_act else "Reaching this node ends the act and opens the next.",
        )
        if not is_last_act:
            # Mark the final node as also-act-start so the next act inherits it.
            final_node = final_node.model_copy(update={"is_act_start": True})

        # --- Step 3+: intermediate (point-of-interest) nodes — count = nodes_per_act - 2.
        intermediates: list[Node] = []
        for intermediate_index in range(1, intermediate_count + 1):
            if progress_callback is not None:
                progress_callback(
                    f"Generating act {act_number} intermediate {intermediate_index}/{intermediate_count}"
                )
            intermediate_context = {
                "premise": {
                    "central_conflict": premise.central_conflict,
                    "tone_statement": premise.tone_statement,
                },
                "act": _act_summary(plot, act_index),
                "act_start_node": {
                    "id": nodes[-1].id,
                    "description": nodes[-1].description,
                },
                "act_final_node": {
                    "description": final_node.description,
                },
                "act_npcs": sorted(act_npcs),
                "act_locations": sorted(act_locations),
                "previous_intermediates": [
                    {"description": n.description} for n in intermediates
                ],
                "intermediate_index": intermediate_index,
            }
            intermediate_proposal: _IntermediateNode = generate_structured(
                client=client,
                stage_name=f"act_{act_number}_intermediate_{intermediate_index}",
                system_prompt=prompts.get(PROMPT_INTERMEDIATE, ""),
                user_prompt=json.dumps(intermediate_context, indent=2),
                schema=_IntermediateNode,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            intermediates.append(
                _build_node(
                    proposal=intermediate_proposal,
                    act_number=act_number,
                    act_npcs=act_npcs,
                    act_locations=act_locations,
                    used_ids=used_ids,
                    is_act_start=False,
                    is_act_final=False,
                    is_victory=False,
                    triggers="Optional point of interest — explore in any order.",
                )
            )

        # Append intermediates first, then final (final is the last node of the act).
        nodes.extend(intermediates)
        nodes.append(final_node)

        previous_acts_finals.append(
            {"act_number": act_number, "description": final_node.description}
        )

    graph = NodeGraph(nodes=nodes)
    if snapshot_path is not None:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(graph.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    if progress_callback is not None:
        progress_callback(
            f"Node graph: {len(graph.nodes)} nodes "
            f"({sum(1 for n in graph.nodes if n.is_act_start)} act-start, "
            f"{sum(1 for n in graph.nodes if n.is_act_final)} act-final, "
            f"1 victory)"
        )
    return graph


def _filter_relevant_locations(picked: list[str], allowed: set[str]) -> list[str]:
    out: list[str] = []
    for name in picked:
        if name in allowed and name not in out:
            out.append(name)
    return out
