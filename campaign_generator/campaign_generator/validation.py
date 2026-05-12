from __future__ import annotations

from collections import defaultdict

from common.pack import GenrePack
from common.validation import ValidationLog

from .schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NodeGraph, NPCRoster, PlotSkeleton

__all__ = [
    "ValidationLog",
    "validate_clue_graph",
    "validate_cross_stage",
    "find_phantom_plot_names",
]


def find_phantom_plot_names(
    plot: PlotSkeleton,
    npcs: NPCRoster,
    *,
    factions: FactionSet | None = None,
    locations: LocationCatalog | None = None,
    protagonist_names: set[str] | None = None,
    extra_known_names: set[str] | None = None,
) -> list[str]:
    """Return supporting_cast names that the plot declared but the NPC roster
    failed to produce, plus the main antagonist if missing.

    The plot stage prompt requires that any named character in plot prose be
    enumerated in `supporting_cast` (or be the main antagonist or `{{user}}`).
    That declaration is the contract. This validator therefore checks the
    contract against the roster: every name the plot promised must exist as
    an NPC. Scanning prose directly would generate too many false positives
    (sentence-initial words, beat-title casing, faction names) — we trust the
    plot stage's structured declaration instead.

    `factions`, `locations`, `protagonist_names`, `extra_known_names` are
    accepted for forward-compatibility but currently unused; declared cast
    failures are the only signal we act on.
    """
    del factions, locations, protagonist_names, extra_known_names  # reserved for future use

    roster_names = {npc.name for npc in npcs.npcs}
    declared = [plot.main_antagonist.name] + [member.name for member in plot.supporting_cast]

    missing: list[str] = []
    seen: set[str] = set()
    for name in declared:
        if not name or name in seen:
            continue
        seen.add(name)
        if name not in roster_names:
            missing.append(name)
    return missing


def _token_aliases(value: str) -> set[str]:
    aliases = {value}
    if value.startswith("The "):
        aliases.add(value[4:])
    return aliases


def validate_clue_graph(
    plot: PlotSkeleton,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clue_graph: ClueGraph,
    node_graph: NodeGraph | None = None,
) -> list[str]:
    """Validate the node-edge clue graph against the new constraints.

    Requires `node_graph` to enforce node existence, same-act, inbound/outbound
    counts, and act-start outbound. If `node_graph` is None, only checks the
    NPC/location anchor existence and self-loop absence (relaxed mode for
    fixture replay where node graph isn't yet available at the clue-stage step).
    """
    errors: list[str] = []
    npc_names = {npc.name for npc in npcs.npcs}
    location_names = {location.name for location in locations.locations}

    for clue in clue_graph.clues:
        if clue.found_at_type == "npc" and clue.found_at not in npc_names:
            errors.append(f"clue {clue.id} references unknown NPC {clue.found_at!r}")
        if clue.found_at_type == "location" and clue.found_at not in location_names:
            errors.append(f"clue {clue.id} references unknown location {clue.found_at!r}")
        if clue.found_at_node == clue.points_to_node:
            errors.append(f"clue {clue.id} has self-loop ({clue.found_at_node})")

    if node_graph is None:
        return errors

    node_by_id = {node.id: node for node in node_graph.nodes}
    for clue in clue_graph.clues:
        if clue.found_at_node not in node_by_id:
            errors.append(f"clue {clue.id} references unknown source node {clue.found_at_node!r}")
        if clue.points_to_node not in node_by_id:
            errors.append(f"clue {clue.id} references unknown target node {clue.points_to_node!r}")

    if errors:
        return errors

    # Same-act constraint: for each clue, source and target must share an act.
    # Shared transition nodes (is_act_final on act N AND is_act_start on act N+1)
    # are tricky: their stored act_number is N, but outbound clues belong to act N+1.
    # We use the "effective act" of the source: if source is a shared transition,
    # its outbound act is source.act_number + 1.
    def _effective_outbound_act(node) -> int:
        if node.is_act_final and node.is_act_start and not node.is_victory:
            return node.act_number + 1
        return node.act_number

    for clue in clue_graph.clues:
        source = node_by_id[clue.found_at_node]
        target = node_by_id[clue.points_to_node]
        if _effective_outbound_act(source) != target.act_number:
            errors.append(
                f"clue {clue.id} crosses acts: source effective act={_effective_outbound_act(source)}, "
                f"target act={target.act_number}"
            )

    # Inbound count: every non-act-start node needs >=3 inbound clues.
    inbound_counts: dict[str, int] = defaultdict(int)
    outbound_counts: dict[str, int] = defaultdict(int)
    for clue in clue_graph.clues:
        inbound_counts[clue.points_to_node] += 1
        outbound_counts[clue.found_at_node] += 1

    for node in node_graph.nodes:
        # Only the act-1 self-contained start node (is_act_start, not is_act_final)
        # is exempt from the >=3 inbound rule. Transition nodes (is_act_start AND
        # is_act_final) DO need inbound clues from their owning act.
        if node.is_act_start and not node.is_act_final and node.act_number == 1:
            continue
        if inbound_counts[node.id] < 3:
            errors.append(
                f"node {node.id} has only {inbound_counts[node.id]} inbound clue(s); needs >=3"
            )

    # Outbound count: every non-victory node should emit >=1 outbound clue.
    for node in node_graph.nodes:
        if node.is_victory:
            continue
        if outbound_counts[node.id] < 1:
            errors.append(f"node {node.id} emits 0 outbound clues; needs >=1")

    # Act-start outbound: each act's start node emits >=3 outbound clues.
    # Clues are not uniquely keyed by (source, target), so a start node can
    # satisfy this by emitting 3 clues at the same target if the act only has
    # one downstream node (e.g. nodes_per_act=3).
    act_count = len({n.act_number for n in node_graph.nodes})
    for act_number in range(1, act_count + 1):
        start_node = None
        if act_number == 1:
            for node in node_graph.nodes:
                if node.act_number == 1 and node.is_act_start and not node.is_act_final:
                    start_node = node
                    break
        else:
            for node in node_graph.nodes:
                if node.act_number == act_number - 1 and node.is_act_final and not node.is_victory:
                    start_node = node
                    break
        if start_node is None:
            continue
        if outbound_counts[start_node.id] < 3:
            errors.append(
                f"act {act_number} start node {start_node.id} emits "
                f"{outbound_counts[start_node.id]} outbound clues; needs >=3"
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
    node_graph: NodeGraph | None = None,
) -> list[str]:
    errors: list[str] = []
    faction_names = {faction.name for faction in factions.factions}
    npc_names = {npc.name for npc in npcs.npcs}
    location_names = {location.name for location in locations.locations}

    null_faction_tokens = {"", "none", "null", "n/a", "independent", "unaffiliated"}
    canonical_lookup = {name.lower(): name for name in faction_names}
    for npc in npcs.npcs:
        affiliation = (npc.faction_affiliation or "").strip()
        if not affiliation or affiliation.lower() in null_faction_tokens:
            continue
        if affiliation in faction_names:
            continue
        if affiliation.lower() in canonical_lookup:
            continue
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

    errors.extend(validate_clue_graph(plot, npcs, locations, clue_graph, node_graph))

    known_tokens = set().union(
        *( _token_aliases(name) for name in faction_names | npc_names | location_names )
    )
    known_tokens |= {clue.id for clue in clue_graph.clues}
    if node_graph is not None:
        known_tokens |= {node.id for node in node_graph.nodes}
    known_tokens |= beat_ids | set(beat_text_to_id)
    for branch in branches.branches:
        for reference in branch.references:
            if reference not in known_tokens:
                errors.append(f"Branch {branch.name} references unknown token {reference!r}")

    return errors
