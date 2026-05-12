import json
from pathlib import Path

from campaign_generator.schemas import (
    ClueGraph,
    LocationCatalog,
    NodeGraph,
    NPCRoster,
    PlotSkeleton,
)
from campaign_generator.stages.clue_chains import build_clue_graph
from campaign_generator.stages.graph import render
from campaign_generator.stages.nodes import build_node_graph


def _load_fixture(name: str):
    path = Path("tests/fixtures/canned_llm_responses") / f"{name}.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_graphs():
    plot = PlotSkeleton.model_validate(_load_fixture("plot_skeleton"))
    npcs = NPCRoster.model_validate({"npcs": [_load_fixture(f"npc_{i}") for i in range(1, 7)]})
    locations = LocationCatalog.model_validate(
        {"locations": [_load_fixture(f"location_{i}") for i in range(1, 6)]}
    )
    node_graph = build_node_graph(plot, nodes_per_act=5)
    clue_graph = build_clue_graph(
        node_graph=node_graph, npcs=npcs, locations=locations, plot=plot
    )
    return plot, node_graph, clue_graph


def test_render_contains_every_node_and_clue_edge():
    plot, node_graph, clue_graph = _build_graphs()

    mermaid_src, html_doc = render(node_graph, clue_graph, plot)

    assert mermaid_src.startswith("flowchart TB")
    for node in node_graph.nodes:
        assert node.id in mermaid_src
    for clue in clue_graph.clues:
        assert f"{clue.found_at_node} -->" in mermaid_src
        assert clue.points_to_node in mermaid_src

    for act_number in {node.act_number for node in node_graph.nodes}:
        assert f"subgraph act{act_number}" in mermaid_src

    assert "<pre class=\"mermaid\">" in html_doc
    assert mermaid_src.strip() in html_doc
    assert "mermaid.esm.min.mjs" in html_doc


def test_render_marks_gateway_and_victory_nodes():
    plot, node_graph, clue_graph = _build_graphs()

    gateways = [n for n in node_graph.nodes if n.is_act_start and n.is_act_final]
    victories = [n for n in node_graph.nodes if n.is_victory]
    assert gateways, "fixture should include at least one gateway node"

    mermaid_src, _ = render(node_graph, clue_graph, plot)

    if gateways:
        assert "classDef gateway" in mermaid_src
        for node in gateways:
            assert node.id in mermaid_src
    if victories:
        assert "classDef victory" in mermaid_src


def test_render_handles_empty_clue_graph():
    plot, node_graph, _ = _build_graphs()
    empty = ClueGraph(clues=[])

    mermaid_src, _ = render(node_graph, empty, plot)

    assert mermaid_src.startswith("flowchart TB")
    for node in node_graph.nodes:
        assert node.id in mermaid_src
    assert "-->|" not in mermaid_src


def test_render_emits_cross_act_link_style():
    plot, node_graph, clue_graph = _build_graphs()
    node_act = {n.id: n.act_number for n in node_graph.nodes}
    has_cross_act = any(
        node_act[c.found_at_node] != node_act[c.points_to_node] for c in clue_graph.clues
    )

    mermaid_src, _ = render(node_graph, clue_graph, plot)

    if has_cross_act:
        assert "linkStyle " in mermaid_src
        assert "stroke-width:3px" in mermaid_src
