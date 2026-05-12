"""Render the campaign node/clue graph as Mermaid + a standalone HTML wrapper.

Pure serializer — no LLM calls, no I/O. Returns (mermaid_source, html_document)
for the caller to write wherever appropriate.
"""

from __future__ import annotations

from collections import defaultdict

from ..schemas import ClueGraph, Node, NodeGraph, PlotSkeleton

_EDGE_LABEL_MAX = 40


def render(node_graph: NodeGraph, clue_graph: ClueGraph, plot: PlotSkeleton) -> tuple[str, str]:
    """Return (mermaid_source, html_document) for the campaign graph."""
    mermaid_src = _render_mermaid(node_graph, clue_graph, plot)
    html_doc = _wrap_html(mermaid_src)
    return mermaid_src, html_doc


def _render_mermaid(node_graph: NodeGraph, clue_graph: ClueGraph, plot: PlotSkeleton) -> str:
    nodes_by_act: dict[int, list[Node]] = defaultdict(list)
    for node in node_graph.nodes:
        nodes_by_act[node.act_number].append(node)

    act_titles = {act.act_number or i + 1: act.title for i, act in enumerate(plot.acts)}
    node_act = {node.id: node.act_number for node in node_graph.nodes}

    lines: list[str] = ["flowchart LR"]

    for act_number in sorted(nodes_by_act):
        title = act_titles.get(act_number, f"Act {act_number}")
        lines.append(f'  subgraph act{act_number}["Act {act_number}: {_esc_label(title)}"]')
        lines.append("    direction LR")
        for node in nodes_by_act[act_number]:
            lines.append(f"    {_node_decl(node)}")
        lines.append("  end")

    classed: dict[str, list[str]] = defaultdict(list)
    for node in node_graph.nodes:
        classed[f"kind_{node.kind}"].append(node.id)
        if node.is_victory:
            classed["victory"].append(node.id)
        elif node.is_act_start and node.is_act_final:
            classed["gateway"].append(node.id)
        elif node.is_act_start:
            classed["act_start"].append(node.id)
        elif node.is_act_final:
            classed["act_final"].append(node.id)

    cross_act_edge_indices: list[int] = []
    edge_index = 0
    for clue in clue_graph.clues:
        if clue.found_at_node == clue.points_to_node:
            continue
        label = _edge_label(clue.hint or f"via {clue.found_at}")
        lines.append(f'  {clue.found_at_node} -->|"{label}"| {clue.points_to_node}')
        src_act = node_act.get(clue.found_at_node)
        dst_act = node_act.get(clue.points_to_node)
        if src_act is not None and dst_act is not None and src_act != dst_act:
            cross_act_edge_indices.append(edge_index)
        edge_index += 1

    for node in node_graph.nodes:
        for prereq in node.gating:
            lines.append(f"  {prereq} -.->|gates| {node.id}")
            edge_index += 1

    for cls_name, ids in classed.items():
        if ids:
            lines.append(f"  class {','.join(ids)} {cls_name}")

    lines.extend(_class_defs())

    for idx in cross_act_edge_indices:
        lines.append(f"  linkStyle {idx} stroke:#b33,stroke-width:3px")

    for node in node_graph.nodes:
        tooltip = _esc_tooltip(node.description)
        lines.append(f'  click {node.id} "#" "{tooltip}"')

    return "\n".join(lines) + "\n"


def _node_decl(node: Node) -> str:
    label = _node_label(node)
    if node.kind == "location":
        shape_open, shape_close = "[", "]"
    elif node.kind == "npc_encounter":
        shape_open, shape_close = "(", ")"
    elif node.kind == "event":
        shape_open, shape_close = "{{", "}}"
    else:
        shape_open, shape_close = "[", "]"
    return f'{node.id}{shape_open}"{label}"{shape_close}'


def _node_label(node: Node) -> str:
    parts = [_esc_label(node.id)]
    flags: list[str] = []
    if node.is_victory:
        flags.append("VICTORY")
    if node.is_act_start and node.is_act_final and not node.is_victory:
        flags.append(f"gateway → Act {node.act_number + 1}")
    elif node.is_act_start:
        flags.append(f"start of Act {node.act_number}")
    elif node.is_act_final:
        flags.append(f"final of Act {node.act_number}")
    if flags:
        parts.append("<br/>" + " · ".join(flags))
    return "".join(parts)


def _edge_label(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) > _EDGE_LABEL_MAX:
        cleaned = cleaned[: _EDGE_LABEL_MAX - 1].rstrip() + "…"
    return _esc_label(cleaned)


def _esc_label(text: str) -> str:
    return text.replace('"', "'").replace("|", "/")


def _esc_tooltip(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) > 240:
        cleaned = cleaned[:239] + "…"
    return cleaned.replace('"', "'")


def _class_defs() -> list[str]:
    return [
        "  classDef kind_location fill:#e8f1ff,stroke:#4a7bbd,color:#102a43",
        "  classDef kind_npc_encounter fill:#fff4e6,stroke:#c47a1a,color:#3a2410",
        "  classDef kind_event fill:#f1e8ff,stroke:#7a4abd,color:#22103a",
        "  classDef act_start stroke:#1a7a3a,stroke-width:3px",
        "  classDef act_final stroke-dasharray:6 3,stroke-width:2px",
        "  classDef gateway fill:#ffe8b3,stroke:#b3811a,stroke-width:4px,color:#3a2410",
        "  classDef victory fill:#ffd76e,stroke:#a07000,stroke-width:4px,color:#3a2410",
    ]


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Campaign Graph</title>
<style>
  body {{ margin: 0; padding: 16px; font-family: -apple-system, system-ui, sans-serif; background: #fafafa; }}
  .legend {{ font-size: 13px; margin-bottom: 12px; color: #444; }}
  .legend span {{ display: inline-block; padding: 2px 8px; margin-right: 8px; border-radius: 3px; }}
  .mermaid {{ background: white; padding: 12px; border: 1px solid #ddd; border-radius: 4px; }}
</style>
</head>
<body>
<div class="legend">
  <strong>Kinds:</strong>
  <span style="background:#e8f1ff;border:1px solid #4a7bbd">location</span>
  <span style="background:#fff4e6;border:1px solid #c47a1a">npc_encounter</span>
  <span style="background:#f1e8ff;border:1px solid #7a4abd">event</span>
  <strong style="margin-left:12px">Flags:</strong>
  <span style="border:3px solid #1a7a3a">act start</span>
  <span style="border:2px dashed #888">act final</span>
  <span style="background:#ffe8b3;border:4px solid #b3811a">gateway</span>
  <span style="background:#ffd76e;border:4px solid #a07000">victory</span>
  <strong style="margin-left:12px">Edges:</strong>
  solid = clue, dotted = gating, thick red = cross-act transition
</div>
<pre class="mermaid">
{mermaid}
</pre>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{
    startOnLoad: true,
    securityLevel: 'loose',
    maxTextSize: 200000,
    flowchart: {{ useMaxWidth: true, htmlLabels: true }},
  }});
</script>
</body>
</html>
"""


def _wrap_html(mermaid_src: str) -> str:
    return _HTML_TEMPLATE.format(mermaid=mermaid_src)
