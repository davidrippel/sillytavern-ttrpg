from __future__ import annotations

from ..schemas import InitialAuthorsNote, PlotSkeleton


def render(plot: PlotSkeleton) -> InitialAuthorsNote:
    act_one = plot.acts[0]
    return InitialAuthorsNote(
        current_act=f"Act 1 - {act_one.title}",
        pending_beats=act_one.beats[:3],
        active_threads=[plot.hook, plot.driving_mystery, act_one.goal][:3],
        recent_beats=[],
        reminders=[
            "Stay within the opening situation and do not surface later-act antagonist secrets.",
            "Escalate through clues, faction pressure, and the first act beats.",
        ],
    )
