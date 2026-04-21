from __future__ import annotations

from ..schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument


def render(
    *,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clues: ClueGraph,
    branches: BranchPlan,
) -> str:
    lines = [
        "# Full Campaign Spoilers",
        "",
        "## Premise",
        premise.premise_text,
        "",
        f"Central conflict: {premise.central_conflict}",
        f"Tone: {premise.tone_statement}",
        "",
        "## Acts",
    ]
    for index, act in enumerate(plot.acts, start=1):
        lines.extend(
            [
                f"### Act {index}: {act.title}",
                f"Goal: {act.goal}",
                "Beats:",
                *(f"- {beat.rendered}" for beat in act.beats),
                "",
            ]
        )

    lines.extend(
        [
            "## Antagonist",
            f"- Name: {plot.main_antagonist.name}",
            f"- Motivation: {plot.main_antagonist.motivation}",
            f"- Secret: {plot.main_antagonist.secret}",
            f"- Relationship to protagonist: {plot.main_antagonist.relationship_to_protagonist}",
            "",
            "## Factions",
        ]
    )
    for faction in factions.factions:
        lines.append(f"### {faction.name}")
        lines.append(faction.description)
        lines.append(f"Goals: {', '.join(faction.goals)}")
        lines.append(f"Methods: {', '.join(faction.methods)}")
        lines.append(f"Tensions: {', '.join(faction.internal_tensions)}")
        lines.append("")

    lines.append("## NPCs")
    for npc in npcs.npcs:
        lines.append(f"### {npc.name}")
        lines.append(f"Role: {npc.role}")
        lines.append(f"Motivation: {npc.motivation}")
        lines.append(f"Secret: {npc.secret}")
        lines.append("")

    lines.append("## Locations")
    for location in locations.locations:
        lines.append(f"### {location.name}")
        lines.append(f"Type: {location.type}")
        lines.append("Hidden elements:")
        lines.extend(f"- {item}" for item in location.hidden_elements)
        lines.append("")

    lines.append("## Clues")
    for clue in clues.clues:
        lines.append(f"### {clue.id}")
        lines.append(f"Found at: {clue.found_at_type} {clue.found_at}")
        lines.append(f"Reveals: {clue.reveals}")
        lines.append("Points to:")
        lines.extend(
            f"- {target.type}: {plot.format_beat_reference(target.value) if target.type == 'beat' else target.value}"
            for target in clue.points_to
        )
        lines.append("")

    lines.append("## Branches")
    for branch in branches.branches:
        lines.append(f"- If {branch.if_condition}, then {branch.then_outcome}. Later: {', '.join(branch.later_act_consequences)}")
    lines.append("")
    return "\n".join(lines)
