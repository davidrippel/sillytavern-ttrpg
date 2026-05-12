from __future__ import annotations

from typing import Any

from .schemas import ClueGraph, Location, LocationCatalog, NodeGraph, PlotSkeleton


def beat_detail(plot: PlotSkeleton, beat_ref: str) -> dict[str, str]:
    beat_id_to_text = plot.beat_id_to_text()
    beat_text_to_id = plot.beat_text_to_id()

    if beat_ref in beat_id_to_text:
        beat_id = beat_ref
        text = beat_id_to_text[beat_ref]
    else:
        beat_id = beat_text_to_id.get(beat_ref, beat_ref)
        text = beat_ref if beat_ref in beat_text_to_id else beat_id_to_text.get(beat_ref, beat_ref)

    label = plot.format_beat_reference(beat_id).split(" ", 1)[0] if beat_id.startswith("act") else beat_id
    rendered = plot.format_beat_reference(beat_id)
    return {
        "id": beat_id,
        "label": label,
        "text": text,
        "rendered": rendered,
    }


def serialize_plot_skeleton(plot: PlotSkeleton) -> dict[str, Any]:
    payload = plot.model_dump()
    for act_payload, act in zip(payload["acts"], plot.acts):
        act_payload["act_number"] = act.act_number
        act_payload["beats"] = [
            {
                "id": beat.id,
                "label": beat.label,
                "text": beat.text,
                "rendered": beat.rendered,
            }
            for beat in act.beats
        ]
    return payload


def serialize_location_catalog(locations: LocationCatalog, plot: PlotSkeleton) -> dict[str, Any]:
    payload = {"locations": [location.model_dump() for location in locations.locations]}
    for location_payload, location in zip(payload["locations"], locations.locations):
        location_payload["plot_beats_detail"] = [beat_detail(plot, beat_ref) for beat_ref in location.plot_beats]
    return payload


def serialize_location_list(locations: list[Location], plot: PlotSkeleton) -> dict[str, Any]:
    payload = {"locations": [location.model_dump() for location in locations]}
    for location_payload, location in zip(payload["locations"], locations):
        location_payload["plot_beats_detail"] = [beat_detail(plot, beat_ref) for beat_ref in location.plot_beats]
    return payload


def serialize_clue_graph(clue_graph: ClueGraph, node_graph: NodeGraph | None = None) -> dict[str, Any]:
    """Serialize the node-edge clue graph. If `node_graph` is provided, enrich
    each clue's payload with the source/target node descriptions for easier
    spoiler-side inspection.
    """
    payload = clue_graph.model_dump()
    if node_graph is None:
        return payload
    node_by_id = {n.id: n for n in node_graph.nodes}
    for clue_payload, clue in zip(payload["clues"], clue_graph.clues):
        source = node_by_id.get(clue.found_at_node)
        target = node_by_id.get(clue.points_to_node)
        if source is not None:
            clue_payload["found_at_node_detail"] = {
                "id": source.id,
                "description": source.description,
                "act_number": source.act_number,
            }
        if target is not None:
            clue_payload["points_to_node_detail"] = {
                "id": target.id,
                "description": target.description,
                "act_number": target.act_number,
            }
    return payload
