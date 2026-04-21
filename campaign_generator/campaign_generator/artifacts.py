from __future__ import annotations

from typing import Any

from .schemas import ClueGraph, Location, LocationCatalog, PlotSkeleton


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


def serialize_clue_graph(clue_graph: ClueGraph, plot: PlotSkeleton) -> dict[str, Any]:
    payload = clue_graph.model_dump()
    for clue_payload, clue in zip(payload["clues"], clue_graph.clues):
        clue_payload["supports_beats_detail"] = [beat_detail(plot, beat_ref) for beat_ref in clue.supports_beats]
        for target_payload, target in zip(clue_payload["points_to"], clue.points_to):
            if target.type == "beat":
                target_payload["beat_detail"] = beat_detail(plot, target.value)
    return payload
