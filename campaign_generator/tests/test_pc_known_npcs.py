import json
from pathlib import Path

from common.llm import LLMError
from common.validation import ValidationLog

from campaign_generator.schemas import (
    NPC,
    NPCRelationship,
    NPCRoster,
    Node,
    NodeGraph,
    PlotSkeleton,
    PremiseDocument,
)
from campaign_generator.seed import CampaignSeed
from campaign_generator.stages import opening_hook as opening_hook_stage
from campaign_generator.stages import pc_known_npcs as pc_stage


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "canned_llm_responses"


def _load(name: str) -> dict:
    with (FIXTURE_DIR / f"{name}.json").open() as handle:
        return json.load(handle)


def _premise() -> PremiseDocument:
    return PremiseDocument.model_validate(_load("premise"))


def _plot() -> PlotSkeleton:
    return PlotSkeleton.model_validate(_load("plot_skeleton"))


def _roster_with(names: list[str]) -> NPCRoster:
    base = _load("npc_1")
    npcs = []
    for idx, n in enumerate(names):
        npc = dict(base)
        npc["name"] = n
        npc["relationships"] = [{"name": "{{user}}", "description": f"Knows {n}."}]
        npcs.append(npc)
    # pad to minimum length of 6
    while len(npcs) < 6:
        filler = dict(base)
        filler["name"] = f"Filler{len(npcs)}"
        filler["relationships"] = []
        npcs.append(filler)
    return NPCRoster.model_validate({"npcs": npcs})


def _node_graph(relevant_npcs: list[str], relevant_location: str = "The Dusk Tide Lounge") -> NodeGraph:
    def make(node_id, act_number, is_act_start, is_act_final=False, is_victory=False, npcs=None):
        return {
            "id": node_id,
            "kind": "location",
            "description": "{{user}} arrives.",
            "act_number": act_number,
            "entry_clues": [],
            "exit_clues": [],
            "gating": [],
            "triggers": "x",
            "is_act_start": is_act_start,
            "is_act_final": is_act_final,
            "is_victory": is_victory,
            "relevant_npcs": npcs or [],
            "relevant_location": relevant_location,
        }

    nodes = [
        make("a1_start", 1, True, npcs=relevant_npcs),
        make("a1_mid", 1, False),
        make("a1_final", 1, False, is_act_final=True),
        make("a2_start", 2, True),
        make("a2_final", 2, False, is_act_final=True),
        make("a3_start", 3, True),
        make("a3_victory", 3, False, is_victory=True),
    ]
    return NodeGraph.model_validate({"nodes": nodes})


def _seed() -> CampaignSeed:
    return CampaignSeed.model_validate(
        {"genre": "symbaroum_dark_fantasy", "campaign_pitch": "x", "protagonist_known_facts": []}
    )


def _log(tmp_path: Path) -> ValidationLog:
    return ValidationLog(tmp_path / "log.txt")


def test_stage_intersects_roster_with_node(tmp_path, monkeypatch):
    captured = {}

    def fake_generate(*, schema, user_prompt, **kwargs):
        captured["user_prompt"] = user_prompt
        return schema.model_validate(
            {"known_names": ["Chloe"], "introduced_now_names": ["Leo Vargas"], "rationale": ""}
        )

    monkeypatch.setattr(pc_stage, "generate_structured", fake_generate)

    roster = _roster_with(["Chloe", "Leo Vargas"])
    graph = _node_graph(relevant_npcs=["Chloe", "Ghost", "Leo Vargas"])

    result = pc_stage.run(
        client=object(),
        system_prompt="sys",
        premise=_premise(),
        plot=_plot(),
        node_graph=graph,
        npcs=roster,
        seed=_seed(),
        model="m",
        temperature=0.0,
        validation_log=_log(tmp_path),
    )
    payload = json.loads(captured["user_prompt"])
    assert [c["name"] for c in payload["candidate_npcs"]] == ["Chloe", "Leo Vargas"]
    assert result.known_names == ["Chloe"]
    assert result.introduced_now_names == ["Leo Vargas"]
    assert result.start_location_name == "The Dusk Tide Lounge"
    assert result.start_node_id == "a1_start"


def test_stage_fallback_on_llm_error(tmp_path, monkeypatch):
    def fake_generate(**kwargs):
        raise LLMError("boom")

    monkeypatch.setattr(pc_stage, "generate_structured", fake_generate)
    result = pc_stage.run(
        client=object(),
        system_prompt="sys",
        premise=_premise(),
        plot=_plot(),
        node_graph=_node_graph(["Chloe", "Leo Vargas"]),
        npcs=_roster_with(["Chloe", "Leo Vargas"]),
        seed=_seed(),
        model="m",
        temperature=0.0,
        validation_log=_log(tmp_path),
    )
    assert set(result.known_names) == {"Chloe", "Leo Vargas"}


def test_stage_invalid_partition_defaults_uncovered_to_introduced(tmp_path, monkeypatch):
    def fake_generate(*, schema, **kwargs):
        return schema.model_validate(
            {"known_names": ["Chloe", "Ghost"], "introduced_now_names": [], "rationale": ""}
        )

    monkeypatch.setattr(pc_stage, "generate_structured", fake_generate)
    result = pc_stage.run(
        client=object(),
        system_prompt="sys",
        premise=_premise(),
        plot=_plot(),
        node_graph=_node_graph(["Chloe", "Leo Vargas"]),
        npcs=_roster_with(["Chloe", "Leo Vargas"]),
        seed=_seed(),
        model="m",
        temperature=0.0,
        validation_log=_log(tmp_path),
    )
    assert result.known_names == ["Chloe"]
    assert result.introduced_now_names == ["Leo Vargas"]


def test_stage_returns_empty_known_when_no_candidates(tmp_path):
    result = pc_stage.run(
        client=None,
        system_prompt=None,
        premise=_premise(),
        plot=_plot(),
        node_graph=_node_graph(["Ghost"]),
        npcs=_roster_with(["Chloe"]),
        seed=_seed(),
        model=None,
        temperature=None,
        validation_log=_log(tmp_path),
    )
    assert result.known_names == []
    assert result.start_location_name == "The Dusk Tide Lounge"


def test_collect_pc_prior_knowledge_uses_passed_known_set():
    roster = _roster_with(["Chloe", "Leo Vargas", "Sasha Petrova"])
    result = opening_hook_stage._collect_pc_prior_knowledge(
        npcs=roster,
        locations=None,
        seed=_seed(),
        known_npc_names={"Chloe"},
        start_location_name=None,
    )
    assert [k["name"] for k in result["known_npcs"]] == ["Chloe"]


def test_collect_pc_prior_knowledge_uses_relevant_location_not_substring():
    from campaign_generator.schemas import LocationCatalog

    base_loc = _load("location_1")
    locations = [
        dict(base_loc, name=name, type="rooftop")
        for name in [
            "The Dusk Tide Lounge",
            "The High Tide Bar",
            "The Golden Hour Patio",
            "The Pacific Echo Alcove",
            "The Solstice Nook",
        ]
    ]
    catalog = LocationCatalog.model_validate({"locations": locations})
    result = opening_hook_stage._collect_pc_prior_knowledge(
        npcs=None,
        locations=catalog,
        seed=_seed(),
        known_npc_names=set(),
        start_location_name="The Dusk Tide Lounge",
    )
    assert [k["name"] for k in result["known_locations"]] == ["The Dusk Tide Lounge"]


def test_npc_prompt_no_longer_mentions_known_at_start():
    prompt = (Path(__file__).resolve().parents[1] / "prompts" / "04_npc.md").read_text(encoding="utf-8")
    assert "known_at_start" not in prompt


def test_npc_relationship_silently_drops_legacy_known_at_start():
    rel = NPCRelationship.model_validate(
        {"name": "{{user}}", "description": "hi", "known_at_start": True}
    )
    assert "known_at_start" not in rel.model_dump()
