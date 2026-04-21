from __future__ import annotations

from collections import Counter, defaultdict, deque
from pathlib import Path

from .pack import GenrePack
from .schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton


def _token_aliases(value: str) -> set[str]:
    aliases = {value}
    if value.startswith("The "):
        aliases.add(value[4:])
    return aliases


class ValidationLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")


def validate_clue_graph(plot: PlotSkeleton, npcs: NPCRoster, locations: LocationCatalog, clue_graph: ClueGraph) -> list[str]:
    errors: list[str] = []
    clue_ids = {clue.id for clue in clue_graph.clues}
    npc_names = {npc.name for npc in npcs.npcs}
    location_names = {location.name for location in locations.locations}
    beat_ids = set(plot.beat_id_to_text())
    beat_text_to_id = plot.beat_text_to_id()
    beat_names = beat_ids | set(beat_text_to_id)

    for entry_id in clue_graph.entry_clue_ids:
        if entry_id not in clue_ids:
            errors.append(f"entry clue id {entry_id!r} does not exist")

    for clue in clue_graph.clues:
        if clue.found_at_type == "npc" and clue.found_at not in npc_names:
            errors.append(f"clue {clue.id} references unknown NPC {clue.found_at!r}")
        if clue.found_at_type == "location" and clue.found_at not in location_names:
            errors.append(f"clue {clue.id} references unknown location {clue.found_at!r}")
        for target in clue.points_to:
            if target.type == "clue" and target.value not in clue_ids:
                errors.append(f"clue {clue.id} points to unknown clue {target.value!r}")
            if target.type == "npc" and target.value not in npc_names:
                errors.append(f"clue {clue.id} points to unknown NPC {target.value!r}")
            if target.type == "location" and target.value not in location_names:
                errors.append(f"clue {clue.id} points to unknown location {target.value!r}")
            if target.type == "beat" and target.value not in beat_names:
                errors.append(f"clue {clue.id} points to unknown beat {target.value!r}")
        for beat in clue.supports_beats:
            if beat not in beat_names:
                errors.append(f"clue {clue.id} supports unknown beat {beat!r}")

    if errors:
        return errors

    adjacency: dict[str, list[str]] = defaultdict(list)
    for clue in clue_graph.clues:
        for target in clue.points_to:
            if target.type == "clue":
                adjacency[clue.id].append(target.value)

    visited: set[str] = set()
    queue = deque(clue_graph.entry_clue_ids)
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        queue.extend(adjacency.get(current, []))

    unreachable = sorted(clue_ids - visited)
    if unreachable:
        errors.append(f"unreachable clues from opening hook: {unreachable}")

    beat_path_counts: Counter[str] = Counter()
    for clue in clue_graph.clues:
        for target in clue.points_to:
            if target.type == "beat":
                beat_path_counts[beat_text_to_id.get(target.value, target.value)] += 1

    weak_beats = sorted(beat_id for beat_id in beat_ids if beat_path_counts[beat_id] < 2)
    if weak_beats:
        errors.append(
            "major beats missing two clue paths: "
            + str([plot.format_beat_reference(beat_id) for beat_id in weak_beats])
        )

    return errors


def validate_cross_stage(
    pack: GenrePack,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clue_graph: ClueGraph,
    branches: BranchPlan,
) -> list[str]:
    errors: list[str] = []
    faction_names = {faction.name for faction in factions.factions}
    npc_names = {npc.name for npc in npcs.npcs}
    location_names = {location.name for location in locations.locations}

    for npc in npcs.npcs:
        if npc.faction_affiliation and npc.faction_affiliation not in faction_names:
            errors.append(f"NPC {npc.name} references unknown faction {npc.faction_affiliation!r}")
        for ability in npc.abilities:
            if ability not in pack.ability_names:
                errors.append(f"NPC {npc.name} references unknown ability {ability!r}")
        for relationship in npc.relationships:
            if relationship.name not in npc_names and relationship.name not in {npc.name, "{{user}}"}:
                errors.append(f"NPC {npc.name} references unknown related NPC {relationship.name!r}")

    beat_ids = set(plot.beat_id_to_text())
    beat_text_to_id = plot.beat_text_to_id()
    all_beats = beat_ids | set(beat_text_to_id)
    for location in locations.locations:
        for npc_name in location.npc_names:
            if npc_name not in npc_names:
                errors.append(f"Location {location.name} references unknown NPC {npc_name!r}")
        for beat in location.plot_beats:
            if beat not in all_beats:
                errors.append(f"Location {location.name} references unknown beat {beat!r}")

    errors.extend(validate_clue_graph(plot, npcs, locations, clue_graph))

    beat_ids = set(plot.beat_id_to_text())
    beat_texts = set(plot.beat_text_to_id())
    known_tokens = set().union(
        *( _token_aliases(name) for name in faction_names | npc_names | location_names )
    )
    known_tokens |= {clue.id for clue in clue_graph.clues}
    known_tokens |= beat_ids | beat_texts
    for branch in branches.branches:
        for reference in branch.references:
            if reference not in known_tokens:
                errors.append(f"Branch {branch.name} references unknown token {reference!r}")

    return errors
