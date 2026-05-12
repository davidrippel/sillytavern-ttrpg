"""Deterministic node-edge clue generator.

A clue is a directed edge from a source node (`found_at_node`) to a target
node (`points_to_node`). For each act independently, we build a clue graph
that satisfies:

- Every non-act-start node has >=3 inbound clues (from same-act sources).
- Every non-terminal source node emits >=1 outbound clue.
- The act-start node emits >=3 outbound clues (so the player has leads
  upon entering the act).
- No self-loops (source != target).
- Source and target belong to the same act (act-final/act-start sharing is
  resolved by the rule: the shared node belongs to act N for inbound clues
  and to act N+1 for outbound clues).

Topology is built deterministically. The LLM is used only to enrich the
`hint` and `reveals` prose (the 06b_clue_prose.md path).
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..artifacts import serialize_clue_graph
from common.llm import LLMClient, LLMError, generate_structured
from ..schemas import (
    Clue,
    ClueGraph,
    LocationCatalog,
    Node,
    NodeGraph,
    NPCRoster,
    PlotSkeleton,
    PremiseDocument,
)
from ..validation import ValidationLog


PROMPT_FILE = "06_clue_chains.md"  # legacy; topology is now deterministic
PROSE_PROMPT_FILE = "06b_clue_prose.md"

# Re-export a tiny shim so existing imports `from .stages.clue_chains import StageClue`
# do not break if used elsewhere. The schema is for prose enrichment only.
from pydantic import BaseModel, Field as _PField


class StageClue(BaseModel):
    id: str
    found_at_type: str
    found_at: str
    hint: str = _PField(default="", max_length=120)
    reveals: str = _PField(max_length=280)


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _nodes_in_act_inbound(node_graph: NodeGraph, act_number: int) -> list[Node]:
    """Nodes that receive inbound clues belonging to this act.

    Shared act-final/act-start nodes are owned (for inbound) by their
    originating act (the act whose `act_number` matches the node's stored
    `act_number`). They also serve as the *start* of the next act for
    outbound purposes — see _nodes_in_act_outbound.
    """
    return [n for n in node_graph.nodes if n.act_number == act_number]


def _nodes_in_act_outbound(node_graph: NodeGraph, act_number: int) -> list[Node]:
    """Nodes that emit outbound clues belonging to this act.

    A "transition node" is a node with is_act_final=True AND is_act_start=True
    (and not victory) — it's the final node of one act AND the start node of
    the next. Its inbound clues belong to its `act_number`; its outbound clues
    belong to `act_number + 1`.

    For act N's outbound sources, return all nodes with `act_number == N`
    EXCEPT a transition node owned by act N (its outbounds belong to N+1),
    PLUS the transition node owned by act N-1 (if any; it acts as act N's
    start node and its outbounds belong to act N).
    """
    sources: list[Node] = []
    for node in node_graph.nodes:
        is_transition = node.is_act_final and node.is_act_start and not node.is_victory
        if node.act_number == act_number:
            # Exclude transition nodes owned by this act (their outbound act = N+1).
            if is_transition:
                continue
            sources.append(node)
        elif node.act_number == act_number - 1 and is_transition:
            # Previous act's transition node = this act's start node.
            sources.append(node)
    return sources


def _act_start_node(node_graph: NodeGraph, act_number: int) -> Node | None:
    """Find the node that serves as act N's start node.

    For act 1: the node with act_number=1 and is_act_start=True.
    For act N>1: the previous act's transition node (act_number=N-1, is_act_final=True, not victory).
    """
    if act_number == 1:
        for node in node_graph.nodes:
            if node.act_number == 1 and node.is_act_start:
                return node
        return None
    # For act N>1, find the (N-1)-th act's transition node (is_act_final, not victory).
    for node in node_graph.nodes:
        if node.act_number == act_number - 1 and node.is_act_final and not node.is_victory:
            return node
    return None


def _select_found_at(
    source_node: Node,
    *,
    npcs: NPCRoster,
    locations: LocationCatalog,
    used_anchors: dict[str, int],
) -> tuple[str, str]:
    """Pick an NPC or location to anchor a clue at this source node.

    Preference order:
      1. NPCs/location explicitly marked relevant to this node (best — most grounded).
      2. The global NPC/location pool (fallback when the node has no relevance hints).

    Within the chosen pool, prefer NPCs vs locations based on `source_node.kind`,
    and round-robin to avoid reusing the same anchor for every clue at this node.
    """
    npc_pool_global = [npc.name for npc in npcs.npcs]
    loc_pool_global = [loc.name for loc in locations.locations]

    node_npcs = list(source_node.relevant_npcs)
    node_location = source_node.relevant_location

    prefer_npc = source_node.kind == "npc_encounter"

    # Tier 1: the node's own relevant NPCs/location.
    if prefer_npc and node_npcs:
        chosen = min(node_npcs, key=lambda n: used_anchors.get(n, 0))
        used_anchors[chosen] = used_anchors.get(chosen, 0) + 1
        return ("npc", chosen)
    if node_location:
        used_anchors[node_location] = used_anchors.get(node_location, 0) + 1
        return ("location", node_location)
    if node_npcs:
        chosen = min(node_npcs, key=lambda n: used_anchors.get(n, 0))
        used_anchors[chosen] = used_anchors.get(chosen, 0) + 1
        return ("npc", chosen)

    # Tier 2: global pools.
    primary = npc_pool_global if prefer_npc else loc_pool_global
    secondary = loc_pool_global if prefer_npc else npc_pool_global

    def pick(pool: list[str]) -> str | None:
        if not pool:
            return None
        return min(pool, key=lambda n: used_anchors.get(n, 0))

    chosen = pick(primary) or pick(secondary)
    if chosen is None:
        raise LLMError("cannot anchor clue: no NPCs or locations available")
    used_anchors[chosen] = used_anchors.get(chosen, 0) + 1
    if chosen in npc_pool_global and chosen not in loc_pool_global:
        anchor_type = "npc"
    elif chosen in loc_pool_global and chosen not in npc_pool_global:
        anchor_type = "location"
    else:
        anchor_type = "npc" if prefer_npc else "location"
    return anchor_type, chosen


def _templated_hint(source: Node, target: Node) -> str:
    return f"A lead found in {source.id} pointing toward {target.id}."[:120]


def _templated_reveals(source: Node, target: Node) -> str:
    return (
        f"Evidence at {source.id} suggests the next thread runs through {target.id}: "
        f"{target.description.strip()[:140]}"
    )[:280]


def _assign_clue_edges(
    *,
    node_graph: NodeGraph,
    act_count: int,
) -> list[tuple[Node, Node]]:
    """For each act, decide the (source, target) edges for that act's clues.

    Returns a flat list of (source_node, target_node) pairs across all acts,
    in deterministic order. Constraints satisfied:
      - every non-start target gets >=3 inbound edges from same-act sources;
      - act-start emits >=3 outbound edges;
      - every non-terminal source emits >=1 outbound edge;
      - no self-loops.
    """
    edges: list[tuple[Node, Node]] = []
    for act_number in range(1, act_count + 1):
        inbound_targets = _nodes_in_act_inbound(node_graph, act_number)
        outbound_sources = _nodes_in_act_outbound(node_graph, act_number)
        start_node = _act_start_node(node_graph, act_number)
        if not outbound_sources:
            continue
        # Targets needing inbound clues are all non-start nodes in this act.
        # The act-1 self-contained start node (is_act_start=True, is_act_final=False)
        # is the only one in `inbound_targets` we exclude — it has no inbound role.
        # Transition nodes (is_act_final=True, is_act_start=True) DO need inbound
        # clues from their owning act (the act whose number matches their act_number).
        non_start_targets = [
            n for n in inbound_targets
            if not (n.is_act_start and not n.is_act_final and n.act_number == act_number)
        ]

        # Build inbound demand: 3 clues per non-start target.
        # Multiple clues from the same source to the same target are allowed
        # (clues are not uniquely keyed by (source, target)). When the act has
        # fewer than 3 distinct sources, sources cycle (the same source
        # contributes multiple clues at this target).
        for target in non_start_targets:
            candidates = [s for s in outbound_sources if s.id != target.id]
            if not candidates:
                continue
            target_index = inbound_targets.index(target)
            for offset in range(3):
                source = candidates[(target_index + offset) % len(candidates)]
                edges.append((source, target))

        # Top up act-start outbound count to >=3. Duplicate edges allowed when
        # the act has fewer than 3 available targets.
        if start_node is not None:
            outbound_from_start = sum(1 for s, _ in edges if s.id == start_node.id)
            possible_start_targets = [
                t for t in non_start_targets if t.id != start_node.id
            ]
            cursor = 0
            while outbound_from_start < 3 and possible_start_targets:
                extra_target = possible_start_targets[cursor % len(possible_start_targets)]
                edges.append((start_node, extra_target))
                outbound_from_start += 1
                cursor += 1
    return edges


def build_clue_graph(
    *,
    node_graph: NodeGraph,
    npcs: NPCRoster,
    locations: LocationCatalog,
    plot: PlotSkeleton,
) -> ClueGraph:
    """Deterministic clue graph builder: produces edges, anchors them, and
    fills in templated hint/reveals prose.
    """
    act_count = len(plot.acts)
    edges = _assign_clue_edges(node_graph=node_graph, act_count=act_count)
    used_anchors: dict[str, int] = {}
    clues: list[Clue] = []
    for index, (source, target) in enumerate(edges, start=1):
        anchor_type, anchor_name = _select_found_at(
            source, npcs=npcs, locations=locations, used_anchors=used_anchors,
        )
        clues.append(
            Clue(
                id=f"clue_{index:02d}",
                found_at_node=source.id,
                points_to_node=target.id,
                found_at_type=anchor_type,
                found_at=anchor_name,
                hint=_templated_hint(source, target),
                reveals=_templated_reveals(source, target),
            )
        )
    return ClueGraph(clues=clues)


def _enrich_clue_prose(
    *,
    client: LLMClient,
    system_prompt: str,
    clue: Clue,
    source: Node,
    target: Node,
    npcs: NPCRoster,
    locations: LocationCatalog,
    premise: PremiseDocument,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> tuple[Clue, bool]:
    """Ask the LLM to rewrite `hint` and `reveals` for a single clue.

    Returns (clue, used_llm). On any failure, returns the input clue unchanged.
    """
    def _npc_context() -> dict | None:
        for npc in npcs.npcs:
            if npc.name == clue.found_at:
                return {
                    "name": npc.name,
                    "role": npc.role,
                    "speaking_style": npc.speaking_style,
                    "motivation": npc.motivation,
                }
        return None

    def _location_context() -> dict | None:
        for loc in locations.locations:
            if loc.name == clue.found_at:
                return {
                    "name": loc.name,
                    "type": loc.type,
                    "notable_features": loc.notable_features,
                }
        return None

    anchor_ctx = _npc_context() if clue.found_at_type == "npc" else _location_context()
    context = {
        "premise_summary": {
            "central_conflict": premise.central_conflict,
            "tone_statement": premise.tone_statement,
        },
        "clue": {
            "id": clue.id,
            "found_at_type": clue.found_at_type,
            "found_at": clue.found_at,
            "found_at_node": clue.found_at_node,
            "points_to_node": clue.points_to_node,
        },
        "found_at_context": anchor_ctx or {"name": clue.found_at},
        "source_node": {"id": source.id, "description": source.description},
        "target_node": {"id": target.id, "description": target.description},
    }

    try:
        result = generate_structured(
            client=client,
            stage_name=f"clue_prose_{clue.id}",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=StageClue,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
            attempts=5,
        )
    except LLMError as exc:
        validation_log.write(
            f"[clue_chains] prose enrichment for {clue.id} failed; keeping templated text. {exc}"
        )
        return clue, False

    new_hint = (result.hint or "").strip()
    new_reveals = (result.reveals or "").strip()
    if not new_hint or len(new_hint) > 120 or not new_reveals or len(new_reveals) > 280:
        validation_log.write(
            f"[clue_chains] prose enrichment for {clue.id} returned out-of-bounds text; keeping templated text."
        )
        return clue, False

    return clue.model_copy(update={"hint": new_hint, "reveals": new_reveals}), True


def run(
    *,
    client: LLMClient,
    node_graph: NodeGraph,
    npcs: NPCRoster,
    locations: LocationCatalog,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    snapshot_path: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
    prose_system_prompt: str | None = None,
) -> ClueGraph:
    """Build the clue graph deterministically from the node graph, then
    optionally enrich `hint`/`reveals` prose via the LLM.
    """
    if progress_callback is not None:
        progress_callback("Building clue graph (deterministic edges between nodes)")

    skeleton = build_clue_graph(node_graph=node_graph, npcs=npcs, locations=locations, plot=plot)

    node_by_id = {n.id: n for n in node_graph.nodes}
    enriched_clues: list[Clue] = []
    enriched_count = 0
    if prose_system_prompt is None:
        enriched_clues = list(skeleton.clues)
    else:
        for index, clue in enumerate(skeleton.clues, start=1):
            if progress_callback is not None:
                progress_callback(f"Enriching clue prose {index}/{len(skeleton.clues)}: {clue.id}")
            source = node_by_id[clue.found_at_node]
            target = node_by_id[clue.points_to_node]
            updated, used_llm = _enrich_clue_prose(
                client=client,
                system_prompt=prose_system_prompt,
                clue=clue,
                source=source,
                target=target,
                npcs=npcs,
                locations=locations,
                premise=premise,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
            enriched_clues.append(updated)
            if used_llm:
                enriched_count += 1

    final_graph = ClueGraph(clues=enriched_clues)
    template_count = len(final_graph.clues) - enriched_count
    summary = (
        f"Clue graph: {len(final_graph.clues)} clues, "
        f"{enriched_count} enriched by LLM, {template_count} used template fallback"
    )
    validation_log.write(f"[clue_chains] {summary}")
    if progress_callback is not None:
        progress_callback(summary)

    if snapshot_path is not None:
        _write_snapshot(snapshot_path, serialize_clue_graph(final_graph, node_graph))

    return final_graph
