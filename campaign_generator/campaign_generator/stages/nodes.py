"""Node-graph generator for Alexandrian (node-mode) campaigns.

Produces a NodeGraph deterministically from the beat structure: one node per
beat plus a campaign-level victory node gating the ending. Entry clues are
sourced from the existing clue graph (clues that supports_beats this beat
become entry clues for that beat's node, and have node:<id> appended to their
points_to so the runtime can compute reachability).

This is the minimum viable node generator. An LLM-driven enrichment stage
(rewriting node descriptions, choosing kind based on plot context) can be
layered on later — the topology produced here is already correct and
playable.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Optional

from ..schemas import (
    Clue,
    ClueGraph,
    ClueTarget,
    Node,
    NodeGraph,
    PlotSkeleton,
)


ProgressCallback = Optional[Callable[[str], None]]


def _slug(text: str) -> str:
    """Convert arbitrary text to a snake_case node id."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:48] or "node"


def _classify_kind(beat_text: str) -> str:
    """Heuristic: derive node kind from beat text. Locations dominate; specific
    interaction or event language can flip the kind. Conservative defaults
    keep the runtime's resolution test simple to satisfy.
    """
    text = beat_text.lower()
    if any(w in text for w in (" meets ", " confronts ", "questions ", " asks ", " interrogates ", " bargains ", " accuses ")):
        return "npc_encounter"
    if any(w in text for w in ("attack", "ambush", "explosion", "earthquake", "ritual", "ceremony", "fire breaks", "alarm")):
        return "event"
    return "location"


def build_node_graph(plot: PlotSkeleton) -> NodeGraph:
    """One node per beat across the campaign, plus a victory node anchored to
    the final act. Entry-clue lists are filled by `wire_clues_to_nodes`."""
    nodes: list[Node] = []
    used_ids: set[str] = set()

    for act in plot.acts:
        for beat in act.beats:
            base = _slug(beat.text)
            node_id = base
            suffix = 1
            while node_id in used_ids:
                suffix += 1
                node_id = f"{base}_{suffix}"
            used_ids.add(node_id)
            nodes.append(
                Node(
                    id=node_id,
                    kind=_classify_kind(beat.text),
                    description=beat.text.strip()[:400],
                    act_number=act.act_number or 1,
                    entry_clues=[],
                    exit_clues=[],
                    gating=[],
                    underspecified=False,
                    is_victory=False,
                )
            )

    last_act = plot.acts[-1]
    victory_id = "victory"
    if victory_id in used_ids:
        victory_id = "victory_node"
    nodes.append(
        Node(
            id=victory_id,
            kind="event",
            description=f"Campaign victory — {last_act.title}: {last_act.goal}",
            act_number=last_act.act_number or len(plot.acts),
            entry_clues=[],
            exit_clues=[],
            gating=[n.id for n in nodes if n.act_number == (last_act.act_number or len(plot.acts))],
            triggers="Player has resolved every other node in the final act.",
            is_victory=True,
        )
    )
    return NodeGraph(nodes=nodes)


def wire_clues_to_nodes(plot: PlotSkeleton, clues: ClueGraph, graph: NodeGraph) -> tuple[ClueGraph, NodeGraph, list[str]]:
    """Connect existing beat-anchored clues to their corresponding nodes.

    Returns (updated_clue_graph, updated_node_graph, warnings).

    For each beat → matching node we:
      - append node:<id> to the clue's points_to (so the runtime's clue parser
        sees the node reference);
      - append the clue id to the node's entry_clues list;
      - record the clue's id on the node's exit_clues if the clue's
        points_to contains a different beat (the clue surfaces information
        leading away from this node).

    Warnings include "node has fewer than 3 entry clues" per the proposal's
    three-clue rule (warn-and-accept).
    """
    nodes_by_id = {n.id: n for n in graph.nodes}
    # Build a beat-id -> node-id index from the deterministic mapping.
    # Generator preserves order; one node per beat; first len(beats) nodes are
    # the beat nodes in source order.
    beat_list = [b for act in plot.acts for b in act.beats]
    if len(beat_list) > len([n for n in graph.nodes if not n.is_victory]):
        raise ValueError("node graph beat-node count mismatch")
    beat_to_node: dict[str, str] = {}
    for beat, node in zip(beat_list, [n for n in graph.nodes if not n.is_victory]):
        if beat.id is not None:
            beat_to_node[beat.id] = node.id

    text_to_id = plot.beat_text_to_id()

    def _resolve_beat_ref(value: str) -> str | None:
        """Beat refs in the wild can be either IDs (act1_beat1) or beat text
        ('Recover the ferryman's satchel'). Map both to the canonical ID."""
        if value in beat_to_node:
            return value
        return text_to_id.get(value)

    new_clues: list[Clue] = []
    for clue in clues.clues:
        node_targets: list[str] = list(clue.points_to_nodes)
        # supports_beats can carry either beat IDs or beat text — normalize both.
        for beat_ref in clue.supports_beats:
            beat_id = _resolve_beat_ref(beat_ref)
            if beat_id is None:
                continue
            node_id = beat_to_node.get(beat_id)
            if node_id and node_id not in node_targets:
                node_targets.append(node_id)
        # Also harvest beat targets from points_to so legacy fixtures that
        # encoded beat references there still wire to the correct node.
        for target in clue.points_to:
            if target.type != "beat":
                continue
            beat_id = _resolve_beat_ref(target.value)
            if beat_id is None:
                continue
            node_id = beat_to_node.get(beat_id)
            if node_id and node_id not in node_targets:
                node_targets.append(node_id)
        # Mirror node targets onto points_to so the JS runtime's clue parser
        # (which reads "Points to: node:<id>" from the lorebook) sees them.
        new_points_to = list(clue.points_to)
        for nid in node_targets:
            if not any(t.type == "node" and t.value == nid for t in new_points_to):
                new_points_to.append(ClueTarget(type="node", value=nid))
        # Drop beat targets from points_to in node-mode — beats no longer exist
        # at runtime as discrete entities; the node references replace them.
        new_points_to = [t for t in new_points_to if t.type != "beat"]
        if not new_points_to:
            # Fall back to a node target so points_to remains non-empty per schema.
            if node_targets:
                new_points_to = [ClueTarget(type="node", value=node_targets[0])]
        updated_clue = clue.model_copy(update={
            "points_to": new_points_to,
            "points_to_nodes": node_targets,
            # supports_beats is left intact for spoilers/reference; runtime ignores it in node-mode.
        })
        new_clues.append(updated_clue)
        for node_id in node_targets:
            node = nodes_by_id.get(node_id)
            if node is None:
                continue
            if clue.id not in node.entry_clues:
                node.entry_clues.append(clue.id)

    # Warn-and-accept on the three-clue rule.
    warnings: list[str] = []
    for node in graph.nodes:
        if node.is_victory:
            continue
        if len(node.entry_clues) < 3:
            node.underspecified = True
            warnings.append(
                f"node '{node.id}' has only {len(node.entry_clues)} entry clue(s); "
                "marked underspecified (player may get stuck here)."
            )

    new_clue_graph = clues.model_copy(update={"clues": new_clues})
    return new_clue_graph, graph, warnings


def run(*, plot: PlotSkeleton, clues: ClueGraph, progress_callback: ProgressCallback = None) -> tuple[ClueGraph, NodeGraph, list[str]]:
    if progress_callback is not None:
        progress_callback("Building node graph (deterministic, one node per beat + victory node)")
    graph = build_node_graph(plot)
    wired_clues, wired_graph, warnings = wire_clues_to_nodes(plot, clues, graph)
    if progress_callback is not None:
        progress_callback(
            f"Node graph: {len(wired_graph.nodes)} nodes "
            f"({sum(1 for n in wired_graph.nodes if n.underspecified)} underspecified). "
            f"Re-wired {len(wired_clues.clues)} clues to point at nodes."
        )
    return wired_clues, wired_graph, warnings
