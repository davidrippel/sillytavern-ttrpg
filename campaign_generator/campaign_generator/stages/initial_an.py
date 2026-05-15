from __future__ import annotations

from ..schemas import ClueGraph, InitialAuthorsNote, Node, NodeGraph, PlotSkeleton


def find_act_one_start_node(plot: PlotSkeleton, node_graph: NodeGraph) -> Node | None:
    """Return the node that opens act 1, or None if no such node exists.

    The act-1 start node is identified by `act_number == act_one.act_number`
    and `is_act_start == True`. Its `relevant_npcs` and `relevant_location`
    drive the opening scene's PC prior-knowledge logic.
    """
    act_one = plot.acts[0]
    act_one_number = act_one.act_number or 1
    for node in node_graph.nodes:
        if node.act_number == act_one_number and node.is_act_start:
            return node
    return None

RESPONSE_LENGTH_BLOCK = "\n".join(
    [
        "",
        "Response length (HARD CAP — applies to THIS turn):",
        "- Default: 2 short paragraphs, ~120 words total.",
        "- Scene transitions or climaxes only: up to 3 paragraphs, ~200 words.",
        "- If you exceed either limit, you have failed the task.",
        "- End at the first natural beat. Do not continue the scene.",
    ]
)


def append_response_length_cap(text: str) -> str:
    return f"{text.rstrip()}\n{RESPONSE_LENGTH_BLOCK}"


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


def render_node_mode(plot: PlotSkeleton, node_graph: NodeGraph, clue_graph: ClueGraph | None = None) -> str:
    """Render the initial Author's Note for a node-mode campaign.

    Seeds `Available clues` with the start node's outbound clues (so the GM
    can drop them on turn 1). Reachable nodes is empty at turn 1 because no
    clues are discovered yet; the count of latent (undiscovered) paths is
    surfaced so the GM knows how many directions to foreshadow without
    naming the targets.
    """
    act_one = plot.acts[0]

    start_node = find_act_one_start_node(plot, node_graph)

    # Outbound clues from the start node.
    outbound_clues = []
    if clue_graph is not None and start_node is not None:
        for clue in clue_graph.clues:
            if clue.found_at_node == start_node.id:
                outbound_clues.append(clue)

    available_lines = [f"- {clue.id} — {clue.hint or clue.reveals[:80]}" for clue in outbound_clues]
    latent_targets = {clue.points_to_node for clue in outbound_clues if clue.points_to_node}
    reachable_lines = []
    if latent_targets:
        n = len(latent_targets)
        reachable_lines.append(
            f"- ({n} undiscovered path{'' if n == 1 else 's'} from here — surface clue opportunities, do not name targets)"
        )

    threads = [plot.hook, plot.driving_mystery, act_one.goal]
    sections = [
        f"Current Act: Act {act_one.act_number}: {act_one.title}",
        "Reachable nodes:",
        *(reachable_lines or ["(none)"]),
        "Recently visited: (none)",
        "On-screen NPCs: (none)",
        "Discovered clues: (none)",
        "Available clues:",
        *(available_lines or ["(none)"]),
        "Active threads:",
        *(f"- {t}" for t in threads),
        "Recent scenes: (empty at start)",
        "Reminders: (none)",
    ]
    return append_response_length_cap("\n".join(sections))
