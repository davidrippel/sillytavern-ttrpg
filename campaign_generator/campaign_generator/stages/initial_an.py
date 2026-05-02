from __future__ import annotations

from ..schemas import InitialAuthorsNote, PlotSkeleton


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
