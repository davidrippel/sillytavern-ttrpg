"""Node-graph generator for node-mode campaigns.

Produces a NodeGraph deterministically from the plot's acts. Each act gets a
configurable number of nodes; the last node of each act is shared with the
first node of the next act (acting as a transition point). The very last
node of the campaign is the victory node.

Node count per act is configurable via `nodes_per_act` (default 5). With
3 acts × 5 nodes/act and shared transitions, the campaign has 13 distinct
nodes (5 + 4 + 4 = 13).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Optional

from ..schemas import Beat, NodeGraph, Node, PlotSkeleton


ProgressCallback = Optional[Callable[[str], None]]

DEFAULT_NODES_PER_ACT = 5


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:48] or "node"


def _classify_kind(text: str) -> str:
    t = text.lower()
    if any(w in t for w in (" meets ", " confronts ", "questions ", " asks ", " interrogates ", " bargains ", " accuses ")):
        return "npc_encounter"
    if any(w in t for w in ("attack", "ambush", "explosion", "earthquake", "ritual", "ceremony", "fire breaks", "alarm")):
        return "event"
    return "location"


def _distribute_beats(beats: list[Beat], slot_count: int) -> list[list[Beat]]:
    """Spread N beats across `slot_count` slots as evenly as possible.

    Earlier beats go into earlier slots. Beats are not split: a single beat
    lives in exactly one slot. If beats < slots, trailing slots get empty
    lists (callers handle that).
    """
    if slot_count <= 0:
        return []
    slots: list[list[Beat]] = [[] for _ in range(slot_count)]
    if not beats:
        return slots
    # Even distribution: every slot gets at least floor(N/slots), with the
    # first (N mod slots) slots taking one extra.
    n = len(beats)
    base, remainder = divmod(n, slot_count)
    cursor = 0
    for index in range(slot_count):
        take = base + (1 if index < remainder else 0)
        slots[index] = beats[cursor : cursor + take]
        cursor += take
    return slots


def _node_description(beats_in_slot: list[Beat], act_title: str, fallback_index: int) -> str:
    """Build the node description from the beats assigned to this slot.

    If the slot has beats, concatenate them. If empty, fall back to a stub
    referencing the act title and slot index.
    """
    if beats_in_slot:
        text = " | ".join(beat.text.strip() for beat in beats_in_slot if beat.text)
        return text[:400] if text else f"{act_title} — scene {fallback_index}"
    return f"{act_title} — scene {fallback_index}"


def _unique_id(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 1
    while candidate in used:
        suffix += 1
        candidate = f"{base}_{suffix}"
    used.add(candidate)
    return candidate


def build_node_graph(plot: PlotSkeleton, *, nodes_per_act: int = DEFAULT_NODES_PER_ACT) -> NodeGraph:
    """Deterministically construct the node graph from the plot skeleton.

    For each act, generate `nodes_per_act` nodes. The last node of each act
    (except the final act) is the same node as the first node of the next act:
    we materialize it once with `is_act_final=True` AND `is_act_start=True`
    (for the next act's perspective, this same node serves as its start), and
    its `act_number` is the *originating* act's number (clues *into* this node
    come from act N; clues *out of* this node lead into act N+1, see
    clue_chains stage). The campaign's last act's last node is the victory.

    Returns a NodeGraph whose `nodes` list is ordered: act 1's nodes (with the
    transition node shared with act 2), then act 2's intermediate nodes, ...,
    ending at the victory node.
    """
    if nodes_per_act < 3:
        raise ValueError("nodes_per_act must be at least 3 (constraints require >=3 inbound clues per non-start node)")

    acts = plot.acts
    if not acts:
        raise ValueError("plot must have at least one act")

    used_ids: set[str] = set()
    nodes: list[Node] = []
    # Track the most recently created node so the next act can reuse it as
    # its starting node.
    prev_act_final_node: Node | None = None

    for act_index, act in enumerate(acts):
        act_number = act.act_number or (act_index + 1)
        is_last_act = act_index == len(acts) - 1

        # If this isn't the first act, the act's first slot is the previous act's
        # final node (shared). Materialize remaining slots only.
        slots_to_create = nodes_per_act - (1 if prev_act_final_node is not None else 0)
        if slots_to_create < 2:
            raise ValueError("nodes_per_act too small to support shared act transitions; use at least 3")

        # Beat distribution: all beats from this act spread across this act's
        # owned slots (slots_to_create). The shared (prev) start node is owned
        # by the previous act and already has its description set.
        beat_slots = _distribute_beats(list(act.beats), slots_to_create)

        # The first new slot in this act is the act's start (unless it's a
        # shared transition, which is already act_start=True from prev act).
        first_owned_index = 0
        for slot_index in range(slots_to_create):
            beats_in_slot = beat_slots[slot_index]
            slot_position_in_act = (slot_index + 1) if prev_act_final_node is None else (slot_index + 2)
            description = _node_description(beats_in_slot, act.title, slot_position_in_act)
            kind_source = beats_in_slot[0].text if beats_in_slot else act.title
            kind = _classify_kind(kind_source)

            # Build a stable id from a slug of the description (or fallback).
            base = _slug(description) if description else f"act{act_number}_node{slot_position_in_act}"
            node_id = _unique_id(base, used_ids)

            is_act_start = (prev_act_final_node is None) and (slot_index == first_owned_index)
            is_act_final = (slot_index == slots_to_create - 1)
            # Mark this node a victory if it's the last node of the last act.
            is_victory = is_act_final and is_last_act

            node = Node(
                id=node_id,
                kind=kind,
                description=description,
                act_number=act_number,
                is_act_start=is_act_start,
                is_act_final=is_act_final,
                is_victory=is_victory,
                triggers="Resolve this node to advance toward the act's final scene." if not is_victory else "Campaign climax.",
            )
            nodes.append(node)
            if is_act_final and not is_last_act:
                # This node will be shared with the next act: mark it as the
                # next act's start node by also setting is_act_start=True.
                # We re-assign with the start flag preserved across acts.
                # (Note: act_number stays = current act; the next act 'inherits'
                # this same node as its start, but the act_number reflects the
                # act this node's *inbound* clues belong to. Outbound clues
                # from this node will belong to the next act.)
                # Cross-act sharing is encoded by leaving the node's act_number
                # alone but flagging is_act_start=True so the next iteration
                # of the loop skips creating a new start node.
                node_copy = node.model_copy(update={"is_act_start": True})
                # Replace the just-added node with the version that has both
                # flags set.
                nodes[-1] = node_copy
                prev_act_final_node = node_copy

        # If this act was not the last, the shared transition is set up.
        # If this act IS the last, prev_act_final_node is irrelevant for the
        # next iteration (loop ends).
        if is_last_act:
            prev_act_final_node = None
        else:
            # prev_act_final_node was set inside the loop above.
            pass

    return NodeGraph(nodes=nodes)


def run(*, plot: PlotSkeleton, nodes_per_act: int = DEFAULT_NODES_PER_ACT, progress_callback: ProgressCallback = None) -> NodeGraph:
    if progress_callback is not None:
        progress_callback(f"Building node graph (deterministic, {nodes_per_act} nodes/act with shared act transitions)")
    graph = build_node_graph(plot, nodes_per_act=nodes_per_act)
    if progress_callback is not None:
        starts = sum(1 for n in graph.nodes if n.is_act_start)
        finals = sum(1 for n in graph.nodes if n.is_act_final)
        progress_callback(
            f"Node graph: {len(graph.nodes)} distinct nodes "
            f"({starts} act-start, {finals} act-final, 1 victory)"
        )
    return graph
