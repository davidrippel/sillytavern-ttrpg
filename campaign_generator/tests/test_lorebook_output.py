import json
from pathlib import Path

from campaign_generator.lorebook import assemble_lorebook
from campaign_generator.pack import load_pack
from campaign_generator.schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
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
    comments = {entry["comment"] for entry in lorebook["entries"]}
    assert "__pack_gm_overlay" in comments
    assert "__pack_failure_moves" in comments
    assert "__pack_reference" in comments
    current_act = next(entry for entry in lorebook["entries"] if entry["comment"] == "Current Act")
    assert "Act 1:" in current_act["content"]
    assert "1.1 Recover the ferryman's satchel" in current_act["content"]
    assert plot.acts[0].beats[0].id == "act1_beat1"


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
