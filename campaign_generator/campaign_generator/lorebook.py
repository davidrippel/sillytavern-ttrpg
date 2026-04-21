from __future__ import annotations

from typing import Any

from .pack import GenrePack
from .schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument


def _slug_variants(name: str) -> list[str]:
    lowered = name.lower()
    compact = lowered.replace("'", "").replace(",", "")
    pieces = {lowered, compact, compact.replace("-", " "), compact.replace(" ", "")}
    return [piece for piece in pieces if piece]


def _entry(uid: int, *, comment: str, content: str, keys: list[str] | None = None, constant: bool = False, order: int = 100) -> dict[str, Any]:
    return {
        "uid": uid,
        "keys": keys or [],
        "secondary_keys": [],
        "comment": comment,
        "content": content,
        "constant": constant,
        "selective": False,
        "enabled": True,
        "insertion_order": order,
        "position": 0,
        "extensions": {
            "exclude_recursion": False,
            "probability": 100,
            "useProbability": True,
            "display_index": uid,
            "match_whole_words": False,
            "case_sensitive": False,
            "use_group_scoring": False,
        },
    }


def assemble_lorebook(
    *,
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clue_graph: ClueGraph,
    branches: BranchPlan,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    uid = 1

    entries.append(
        _entry(
            uid,
            comment="__pack_gm_overlay",
            content=pack.gm_prompt_overlay,
            keys=[],
            constant=True,
            order=1000,
        )
    )
    uid += 1
    entries.append(
        _entry(
            uid,
            comment="__pack_failure_moves",
            content=pack.failure_moves,
            keys=[],
            constant=True,
            order=950,
        )
    )
    uid += 1
    entries.append(
        _entry(
            uid,
            comment="__pack_reference",
            content=(
                f'{{"pack_name":"{pack.metadata.pack_name}","pack_version":"{pack.metadata.version}",'
                f'"display_name":"{pack.metadata.display_name}"}}'
            ),
            keys=[],
            constant=False,
            order=0,
        )
    )
    uid += 1

    campaign_bible = "\n".join(
        [
            premise.premise_text,
            "",
            f"Central conflict: {premise.central_conflict}",
            f"Tone: {premise.tone_statement}",
            "Themes:",
            *(f"- {theme}" for theme in premise.thematic_pillars),
        ]
    )
    entries.append(_entry(uid, comment="Campaign Bible", content=campaign_bible, keys=[], constant=True, order=900))
    uid += 1

    act_one = plot.acts[0]
    current_act = "\n".join(
        [
            f"Act {act_one.act_number}: {act_one.title}",
            f"Goal: {act_one.goal}",
            "Beats:",
            *(f"- {beat.rendered}" for beat in act_one.beats),
        ]
    )
    entries.append(_entry(uid, comment="Current Act", content=current_act, keys=[], constant=True, order=850))
    uid += 1

    for faction in factions.factions:
        content = "\n".join(
            [
                faction.description,
                f"Goals: {', '.join(faction.goals)}",
                f"Methods: {', '.join(faction.methods)}",
                f"Internal tensions: {', '.join(faction.internal_tensions)}",
                f"Plot role: {faction.relationship_to_plot}",
            ]
        )
        entries.append(
            _entry(
                uid,
                comment=f"Faction: {faction.name}",
                content=content,
                keys=_slug_variants(faction.name),
                constant=False,
                order=500,
            )
        )
        uid += 1

    for npc in npcs.npcs:
        relationships = ", ".join(f"{rel.name} ({rel.description})" for rel in npc.relationships) or "none recorded"
        content = "\n".join(
            [
                f"Role: {npc.role}",
                f"Faction: {npc.faction_affiliation or 'independent'}",
                f"Description: {npc.physical_description}",
                f"Voice: {npc.speaking_style}",
                f"Motivation: {npc.motivation}",
                f"Secret: {npc.secret}",
                f"Relationships: {relationships}",
                f"Abilities: {', '.join(npc.abilities) if npc.abilities else 'none'}",
            ]
        )
        entries.append(
            _entry(
                uid,
                comment=f"NPC: {npc.name}",
                content=content,
                keys=_slug_variants(npc.name),
                constant=False,
                order=450,
            )
        )
        uid += 1

    for location in locations.locations:
        content = "\n".join(
            [
                f"Type: {location.type}",
                "Sensory details:",
                *(f"- {sense}: {value}" for sense, value in location.sensory_description.model_dump(exclude_none=True).items()),
                "Notable features:",
                *(f"- {item}" for item in location.notable_features),
                "Hidden elements:",
                *(f"- {item}" for item in location.hidden_elements),
                f"NPCs present: {', '.join(location.npc_names) if location.npc_names else 'varies'}",
            ]
        )
        entries.append(
            _entry(
                uid,
                comment=f"Location: {location.name}",
                content=content,
                keys=_slug_variants(location.name),
                constant=False,
                order=350,
            )
        )
        uid += 1

    for clue in clue_graph.clues:
        rendered_targets = []
        for target in clue.points_to:
            value = plot.format_beat_reference(target.value) if target.type == "beat" else target.value
            rendered_targets.append(f"- {target.type}: {value}")
        content = "\n".join(
            [
                f"Found at: {clue.found_at_type} {clue.found_at}",
                f"Reveals: {clue.reveals}",
                "Points to:",
                *rendered_targets,
            ]
        )
        entries.append(
            _entry(
                uid,
                comment=f"Clue: {clue.id}",
                content=content,
                keys=[clue.id.lower()],
                constant=False,
                order=300,
            )
        )
        uid += 1

    branch_content = "\n".join(
        [
            f"{branch.name}: if {branch.if_condition}, then {branch.then_outcome}. Consequences: {', '.join(branch.later_act_consequences)}"
            for branch in branches.branches
        ]
    )
    entries.append(_entry(uid, comment="Branch Contingencies", content=branch_content, keys=[], constant=True, order=700))

    return {
        "name": pack.metadata.display_name,
        "description": f"Generated campaign lorebook for {pack.metadata.display_name}",
        "entries": entries,
    }
