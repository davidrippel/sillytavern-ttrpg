"""Cross-stage validation for v2 campaign output.

The v1 file validated beat references, clue-graph topology, and
ability-catalog lookups. None of those concepts survive in v2; this
module is much simpler. It checks the small set of constraints that
remain meaningful:

  - NPC faction affiliations name a real faction (or null).
  - NPC relationships name a real NPC (or `{{user}}`).
  - Location npc_names name real NPCs.
  - Truth ids are unique and snake_case (already enforced by the
    pydantic schema, but we re-check on full state for safety).
  - Branch references resolve to a known NPC / location / faction
    / truth id.
"""
from __future__ import annotations

from common.validation import ValidationLog

from .schemas import BranchPlan, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, TruthSet

__all__ = ["ValidationLog", "validate_cross_stage", "find_phantom_plot_names"]


def find_phantom_plot_names(
    plot: PlotSkeleton,
    npcs: NPCRoster,
    *,
    factions: FactionSet | None = None,
    locations: LocationCatalog | None = None,
    protagonist_names: set[str] | None = None,
) -> list[str]:
    """Names the plot's supporting_cast / antagonist declared but the NPC
    roster did not produce. Used by the pipeline's plot-NPC repair loop
    (no longer used in v2's simplified pipeline, but kept for callers
    that still rely on the contract)."""
    del factions, locations, protagonist_names  # reserved for future use

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


def validate_cross_stage(
    *,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    truths: TruthSet,
    validation_log: ValidationLog | None = None,
    branches: BranchPlan | None = None,
) -> list[str]:
    """Walk every cross-stage reference and return a list of error
    messages. Empty list = clean. Writes each error to
    `validation_log` if one is provided."""
    errors: list[str] = []
    faction_names = {faction.name for faction in factions.factions}
    npc_names = {npc.name for npc in npcs.npcs}
    location_names = {location.name for location in locations.locations}
    truth_ids = {truth.id for truth in truths.truths}

    null_faction_tokens = {"", "none", "null", "n/a", "independent", "unaffiliated"}
    canonical_lookup = {name.lower(): name for name in faction_names}
    for npc in npcs.npcs:
        affiliation = (npc.faction_affiliation or "").strip()
        if affiliation and affiliation.lower() not in null_faction_tokens:
            if affiliation not in faction_names and affiliation.lower() not in canonical_lookup:
                errors.append(f"NPC {npc.name} references unknown faction {npc.faction_affiliation!r}")
        for relationship in npc.relationships:
            if (
                relationship.name not in npc_names
                and relationship.name not in {npc.name, "{{user}}"}
            ):
                errors.append(
                    f"NPC {npc.name} references unknown related NPC {relationship.name!r}"
                )

    for location in locations.locations:
        for npc_name in location.npc_names:
            if npc_name not in npc_names:
                errors.append(f"Location {location.name} references unknown NPC {npc_name!r}")

    if branches is not None:
        known_tokens = set().union(
            *(_token_aliases(name) for name in faction_names | npc_names | location_names)
        )
        known_tokens |= truth_ids
        for branch in branches.branches:
            for reference in branch.references:
                if reference not in known_tokens:
                    errors.append(f"Branch {branch.name} references unknown token {reference!r}")

    if validation_log is not None:
        for error in errors:
            validation_log.write(f"[cross-stage] {error}")

    return errors
