import json
from pathlib import Path

from campaign_generator.lorebook import _name_variants, assemble_lorebook
from common.pack import load_pack
from campaign_generator.schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from campaign_generator.stages.branches import _build_reference_token_map
from campaign_generator.stages.npcs import _normalize_faction_affiliation
from campaign_generator.validation import validate_cross_stage


def _load_fixture(name: str):
    path = Path("tests/fixtures/canned_llm_responses") / f"{name}.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_lorebook_contains_pack_entries():
    pack = load_pack("genres/symbaroum_dark_fantasy")
    plot = PlotSkeleton.model_validate(_load_fixture("plot_skeleton"))
    lorebook = assemble_lorebook(
        pack=pack,
        premise=PremiseDocument.model_validate(_load_fixture("premise")),
        plot=plot,
        factions=FactionSet.model_validate(_load_fixture("factions")),
        npcs=NPCRoster.model_validate({"npcs": [_load_fixture(f"npc_{index}") for index in range(1, 7)]}),
        locations=LocationCatalog.model_validate({"locations": [_load_fixture(f"location_{index}") for index in range(1, 6)]}),
        clue_graph=ClueGraph.model_validate(_load_fixture("clue_chains")),
        branches=BranchPlan.model_validate(_load_fixture("branches")),
    )
    assert isinstance(lorebook["entries"], dict)
    entry_list = list(lorebook["entries"].values())
    comments = {entry["comment"] for entry in entry_list}
    assert "GM Prompt Overlay" in comments
    assert "Failure Moves" in comments
    assert any(c.startswith("Pack Reference:") for c in comments)
    assert any(c.startswith("Campaign Bible:") for c in comments)
    current_act = next(entry for entry in entry_list if entry["comment"].startswith("Current Act"))
    assert "Act 1:" in current_act["content"]
    assert "1.1 Recover the ferryman's satchel" in current_act["content"]
    assert plot.acts[0].beats[0].id == "act1_beat1"

    # Native ST shape: key/keysecondary/order, flat camelCase fields, no nested extensions.
    sample = entry_list[0]
    assert "key" in sample and "keysecondary" in sample and "order" in sample
    assert "extensions" not in sample
    assert "keys" not in sample and "secondary_keys" not in sample and "insertion_order" not in sample

    # Constant entries: GM overlay, failure moves, campaign bible, and the current (Act 1) entry.
    constant_comments = {e["comment"] for e in entry_list if e["constant"]}
    assert constant_comments == {
        "GM Prompt Overlay",
        "Failure Moves",
        next(c for c in comments if c.startswith("Campaign Bible:")),
        next(c for c in comments if c.startswith("Current Act:")),
    }

    # All acts are emitted as separate entries; later acts are non-constant.
    act_entries = [e for e in entry_list if e["comment"].startswith(("Current Act:", "Act "))]
    assert len(act_entries) == len(plot.acts)
    later_acts = [e for e in act_entries if e["comment"].startswith("Act ")]
    assert later_acts and all(not e["constant"] for e in later_acts)

    # Act keys are concise (titles + beat labels), not full beat sentences.
    current_act_keys = current_act["key"]
    assert all(len(k) <= 60 for k in current_act_keys), current_act_keys

    # Faction/NPC/location/clue content includes the entity name in the body.
    faction_entry_for_name = next(e for e in entry_list if e["comment"].startswith("Faction:"))
    assert faction_entry_for_name["comment"].split(": ", 1)[1] in faction_entry_for_name["content"]
    npc_entry = next(e for e in entry_list if e["comment"].startswith("NPC:"))
    assert npc_entry["comment"].split(": ", 1)[1] in npc_entry["content"]
    location_entry = next(e for e in entry_list if e["comment"].startswith("Location:"))
    assert location_entry["comment"].split(": ", 1)[1] in location_entry["content"]
    clue_entry = next(e for e in entry_list if e["comment"].startswith("Clue:"))
    assert clue_entry["comment"].split(": ", 1)[1] in clue_entry["content"]

    # Faction/NPC/location entries carry trigger keys and are not constant.
    faction_entry = next(e for e in entry_list if e["comment"].startswith("Faction:"))
    assert not faction_entry["constant"]
    assert faction_entry["selective"] is True
    assert len(faction_entry["key"]) >= 1
    # No machine-mangled name variants like "thechurchofprios(thesunknights)".
    assert all(" " in k or k.isalpha() for k in faction_entry["key"])

    # Lorebook name uses the campaign title, not the pack display name.
    assert lorebook["name"] == "The Ferryman's Satchel"


def test_cross_stage_validation_allows_user_relationship_placeholder():
    pack = load_pack("genres/symbaroum_dark_fantasy")
    plot = PlotSkeleton.model_validate(_load_fixture("plot_skeleton"))
    factions = FactionSet.model_validate(_load_fixture("factions"))
    npc_payloads = [_load_fixture(f"npc_{index}") for index in range(1, 7)]
    npc_payloads[0]["relationships"].append(
        {
            "name": "{{user}}",
            "description": "The player character is directly entangled in the conspiracy.",
        }
    )
    errors = validate_cross_stage(
        pack=pack,
        plot=plot,
        factions=factions,
        npcs=NPCRoster.model_validate({"npcs": npc_payloads}),
        locations=LocationCatalog.model_validate({"locations": [_load_fixture(f"location_{index}") for index in range(1, 6)]}),
        clue_graph=ClueGraph.model_validate(_load_fixture("clue_chains")),
        branches=BranchPlan.model_validate(_load_fixture("branches")),
    )

    assert not any("{{user}}" in error for error in errors)


def test_npc_secret_is_segregated_into_disabled_entry():
    pack = load_pack("genres/symbaroum_dark_fantasy")
    plot = PlotSkeleton.model_validate(_load_fixture("plot_skeleton"))
    npc_roster = NPCRoster.model_validate({"npcs": [_load_fixture(f"npc_{index}") for index in range(1, 7)]})
    lorebook = assemble_lorebook(
        pack=pack,
        premise=PremiseDocument.model_validate(_load_fixture("premise")),
        plot=plot,
        factions=FactionSet.model_validate(_load_fixture("factions")),
        npcs=npc_roster,
        locations=LocationCatalog.model_validate({"locations": [_load_fixture(f"location_{index}") for index in range(1, 6)]}),
        clue_graph=ClueGraph.model_validate(_load_fixture("clue_chains")),
        branches=BranchPlan.model_validate(_load_fixture("branches")),
    )
    entry_list = list(lorebook["entries"].values())

    public_npc_entries = [e for e in entry_list if e["comment"].startswith("NPC: ")]
    secret_entries = [e for e in entry_list if e["comment"].startswith("NPC Secret: ")]
    assert len(public_npc_entries) == len(npc_roster.npcs)
    assert len(secret_entries) >= 1

    for entry in public_npc_entries:
        assert "Secret:" not in entry["content"], (
            f"public NPC entry {entry['comment']!r} leaks a Secret: line"
        )
    for npc in npc_roster.npcs:
        if not (npc.secret or "").strip():
            continue
        match = next(e for e in secret_entries if e["comment"] == f"NPC Secret: {npc.name}")
        assert match["disable"] is True
        assert match["key"] == []
        assert match["selective"] is False
        assert npc.secret in match["content"]


def test_name_variants_includes_first_name_and_strips_articles():
    variants = _name_variants("Sister Valeria")
    assert "Sister Valeria" in variants
    assert "Valeria" in variants

    variants = _name_variants("Lord Cassius Valerius")
    assert "Lord Cassius Valerius" in variants
    assert "Cassius" in variants
    assert "Cassius Valerius" in variants

    variants = _name_variants("The Gilded Raven Tavern", type_hint="Tavern")
    assert "The Gilded Raven Tavern" in variants
    assert "Gilded Raven Tavern" in variants
    assert "Gilded Raven" in variants

    variants = _name_variants("The Church of Prios (Thistle Hold Chapter)")
    assert "Church of Prios" in variants
    assert "Thistle Hold Chapter" in variants


def test_normalize_faction_affiliation_treats_none_string_as_independent():
    factions = {"The Valerius Family", "The Iron Pact"}
    canonical, error = _normalize_faction_affiliation(None, factions)
    assert canonical is None and error is None
    canonical, error = _normalize_faction_affiliation("None", factions)
    assert canonical is None and error is None
    canonical, error = _normalize_faction_affiliation("the valerius family", factions)
    assert canonical == "The Valerius Family" and error is None
    canonical, error = _normalize_faction_affiliation("None (Formerly The Valerius Family)", factions)
    assert canonical is None and error is not None
    canonical, error = _normalize_faction_affiliation("The Forgotten Cabal", factions)
    assert canonical is None and "unknown faction" in error


def test_branch_reference_token_map_accepts_faction_aliases_and_beats():
    plot = PlotSkeleton.model_validate(_load_fixture("plot_skeleton"))
    factions = FactionSet.model_validate(_load_fixture("factions"))
    npcs = NPCRoster.model_validate({"npcs": [_load_fixture(f"npc_{index}") for index in range(1, 7)]})
    locations = LocationCatalog.model_validate({"locations": [_load_fixture(f"location_{index}") for index in range(1, 6)]})
    clues = ClueGraph.model_validate(_load_fixture("clue_chains"))

    token_map = _build_reference_token_map(
        plot=plot,
        factions=factions,
        npcs=npcs,
        locations=locations,
        clue_graph=clues,
    )

    assert token_map["Lantern Carters Guild"] == "Lantern Carters Guild"
    assert token_map["act1_beat1"] == "act1_beat1"
    assert token_map["Recover the ferryman's satchel"] == "act1_beat1"
