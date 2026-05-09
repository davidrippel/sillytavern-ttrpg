from __future__ import annotations

from ..schemas import InitialAuthorsNote, NodeGraph, PlotSkeleton


def render(plot: PlotSkeleton) -> InitialAuthorsNote:
    act_one = plot.acts[0]
    beats = act_one.beats
    current = beats[0].rendered if beats else ""
    nxt = beats[1].rendered if len(beats) > 1 else None
    return InitialAuthorsNote(
        current_act=f"Act {act_one.act_number}: {act_one.title}",
        current_beat=current,
        next_beat=nxt,
        active_threads=[plot.hook, plot.driving_mystery, act_one.goal][:3],
        recent_beats=[],
        reminders=[],
    )


def render_node_mode(plot: PlotSkeleton, node_graph: NodeGraph) -> str:
    """Render the initial Author's Note for a node-mode campaign.

    No InitialAuthorsNote model is used because that schema's required fields
    (current_beat, next_beat) are beat-mode concepts. We return a plain string
    that matches the node-mode section list the JS runtime parses.
    """
    act_one = plot.acts[0]
    act_one_nodes = [n for n in node_graph.nodes if n.act_number == (act_one.act_number or 1) and not n.is_victory]
    reachable_lines = [f"- {n.id}: {n.description[:80]}" for n in act_one_nodes[:8]] or ["(none)"]
    threads = [plot.hook, plot.driving_mystery, act_one.goal]
    sections = [
        f"Current Act: Act {act_one.act_number}: {act_one.title}",
        "Reachable nodes:",
        *reachable_lines,
        "Recently visited: (none)",
        "On-screen NPCs: (none)",
        "Discovered clues: (none)",
        "Available clues: (none)",
        "Active threads:",
        *(f"- {t}" for t in threads),
        "Recent scenes: (empty at start)",
        "Reminders: (none)",
    ]
    return "\n".join(sections)
