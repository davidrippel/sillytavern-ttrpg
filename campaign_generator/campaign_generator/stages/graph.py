"""Render the campaign node/clue graph as Mermaid + a standalone HTML wrapper.

Pure serializer — no LLM calls, no I/O. Returns (mermaid_source, html_document)
for the caller to write wherever appropriate.
"""

from __future__ import annotations

import json
from collections import defaultdict

from ..schemas import ClueGraph, Node, NodeGraph, PlotSkeleton

_EDGE_LABEL_MAX = 40


def render(node_graph: NodeGraph, clue_graph: ClueGraph, plot: PlotSkeleton) -> tuple[str, str]:
    """Return (mermaid_source, html_document) for the campaign graph."""
    mermaid_src, ordered_clue_ids = _render_mermaid(node_graph, clue_graph, plot)
    node_details = _node_details(node_graph)
    clue_details = _clue_details(clue_graph, ordered_clue_ids)
    html_doc = _wrap_html(mermaid_src, node_details, clue_details)
    return mermaid_src, html_doc


def _render_mermaid(
    node_graph: NodeGraph, clue_graph: ClueGraph, plot: PlotSkeleton
) -> tuple[str, list[str]]:
    nodes_by_act: dict[int, list[Node]] = defaultdict(list)
    for node in node_graph.nodes:
        nodes_by_act[node.act_number].append(node)

    act_titles = {act.act_number or i + 1: act.title for i, act in enumerate(plot.acts)}
    node_act = {node.id: node.act_number for node in node_graph.nodes}

    lines: list[str] = ["flowchart TB"]

    for act_number in sorted(nodes_by_act):
        title = act_titles.get(act_number, f"Act {act_number}")
        lines.append(f'  subgraph act{act_number}["Act {act_number}: {_esc_label(title)}"]')
        lines.append("    direction TB")
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
    ordered_clue_ids: list[str] = []
    edge_index = 0
    for clue in clue_graph.clues:
        if clue.found_at_node == clue.points_to_node:
            continue
        label = _edge_label(clue.hint or f"via {clue.found_at}")
        lines.append(f'  {clue.found_at_node} -->|"{label}"| {clue.points_to_node}')
        ordered_clue_ids.append(clue.id)
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

    return "\n".join(lines) + "\n", ordered_clue_ids


def _node_details(node_graph: NodeGraph) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for node in node_graph.nodes:
        flags = []
        if node.is_victory:
            flags.append("victory")
        if node.is_act_start:
            flags.append("act start")
        if node.is_act_final:
            flags.append("act final")
        out[node.id] = {
            "id": node.id,
            "kind": node.kind,
            "act": node.act_number,
            "description": node.description,
            "flags": flags,
            "triggers": node.triggers or "",
            "relevant_npcs": list(node.relevant_npcs),
            "relevant_location": node.relevant_location or "",
            "gating": list(node.gating),
        }
    return out


def _clue_details(clue_graph: ClueGraph, ordered_clue_ids: list[str]) -> list[dict]:
    by_id = {clue.id: clue for clue in clue_graph.clues}
    out: list[dict] = []
    for clue_id in ordered_clue_ids:
        clue = by_id[clue_id]
        out.append({
            "id": clue.id,
            "from": clue.found_at_node,
            "to": clue.points_to_node,
            "found_at_type": clue.found_at_type,
            "found_at": clue.found_at,
            "hint": clue.hint,
            "reveals": clue.reveals,
        })
    return out


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
  body { margin: 0; padding: 16px; font-family: -apple-system, system-ui, sans-serif; background: #fafafa; }
  .legend { font-size: 13px; margin-bottom: 12px; color: #444; }
  .legend span { display: inline-block; padding: 2px 8px; margin-right: 8px; border-radius: 3px; }
  .mermaid { background: white; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 22px; overflow-x: auto; }
  .mermaid svg { display: block; }
  #zoom-controls { position: fixed; bottom: 16px; left: 16px; background: white; border: 1px solid #bbb; border-radius: 6px; padding: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); z-index: 11; }
  #zoom-controls button { font-size: 16px; padding: 4px 10px; margin: 0 2px; cursor: pointer; border: 1px solid #ccc; background: #f5f5f5; border-radius: 3px; }
  #zoom-controls button:hover { background: #e5e5e5; }
  #detail-panel {
    position: fixed; width: 340px; max-height: 60vh; overflow-y: auto;
    background: white; border: 1px solid #bbb; border-radius: 6px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.18); padding: 14px 28px 14px 14px;
    font-size: 13px; line-height: 1.45; z-index: 20; pointer-events: auto;
    display: none;
  }
  #detail-panel.visible { display: block; }
  #panel-close {
    position: absolute; top: 4px; right: 6px; background: none; border: none; font-size: 20px;
    line-height: 1; color: #888; cursor: pointer; padding: 2px 6px; border-radius: 3px;
  }
  #panel-close:hover { background: #eee; color: #222; }
  #detail-panel h2 { font-size: 14px; margin: 0 0 8px 0; color: #222; }
  #detail-panel .kind { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #eee; color: #444; margin-right: 6px; }
  #detail-panel .flag { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #ffe8b3; color: #5a3a10; margin-right: 4px; }
  #detail-panel dl { margin: 8px 0 0 0; }
  #detail-panel dt { font-weight: 600; color: #555; margin-top: 8px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
  #detail-panel dd { margin: 2px 0 0 0; color: #222; word-wrap: break-word; }
  #detail-panel .placeholder { color: #888; font-style: italic; }
  .flowchart-link { cursor: pointer; }
  .node { cursor: pointer; }
  .node-hover > * { filter: brightness(0.92); }
  .edge-hover path { stroke-width: 4px !important; }
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
<div id="detail-panel">
  <button id="panel-close" title="Hide details panel">×</button>
  <div id="detail-content"></div>
</div>
<div id="zoom-controls">
  <button id="zoom-out" title="Zoom out">−</button>
  <button id="zoom-reset" title="Reset zoom">⤢</button>
  <button id="zoom-in" title="Zoom in">+</button>
</div>
<pre class="mermaid">
__MERMAID_SOURCE__
</pre>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    maxTextSize: 200000,
    flowchart: { useMaxWidth: false, htmlLabels: true, nodeSpacing: 60, rankSpacing: 80 },
    themeVariables: { fontSize: '18px' },
  });

  const NODE_DETAILS = __NODE_DETAILS__;
  const CLUE_DETAILS = __CLUE_DETAILS__;

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fieldOrPlaceholder = (value, placeholder = '—') => {
    if (value == null) return `<span class="placeholder">${placeholder}</span>`;
    if (Array.isArray(value)) return value.length ? value.map(esc).join(', ') : `<span class="placeholder">${placeholder}</span>`;
    const s = String(value).trim();
    return s ? esc(s) : `<span class="placeholder">${placeholder}</span>`;
  };

  function renderNode(node) {
    const flags = (node.flags || []).map((f) => `<span class="flag">${esc(f)}</span>`).join('');
    return `
      <h2>${esc(node.id)}</h2>
      <div><span class="kind">${esc(node.kind)}</span><span class="kind">Act ${esc(node.act)}</span>${flags}</div>
      <dl>
        <dt>Description</dt><dd>${fieldOrPlaceholder(node.description)}</dd>
        <dt>Triggers</dt><dd>${fieldOrPlaceholder(node.triggers)}</dd>
        <dt>Relevant NPCs</dt><dd>${fieldOrPlaceholder(node.relevant_npcs)}</dd>
        <dt>Relevant location</dt><dd>${fieldOrPlaceholder(node.relevant_location)}</dd>
        <dt>Gating prerequisites</dt><dd>${fieldOrPlaceholder(node.gating)}</dd>
      </dl>`;
  }

  function renderClue(clue) {
    return `
      <h2>Clue: ${esc(clue.id)}</h2>
      <div><span class="kind">${esc(clue.from)} → ${esc(clue.to)}</span></div>
      <dl>
        <dt>Found at (${esc(clue.found_at_type)})</dt><dd>${fieldOrPlaceholder(clue.found_at)}</dd>
        <dt>Hint</dt><dd>${fieldOrPlaceholder(clue.hint)}</dd>
        <dt>Reveals</dt><dd>${fieldOrPlaceholder(clue.reveals)}</dd>
      </dl>`;
  }

  const panel = document.getElementById('detail-panel');
  const panelContent = document.getElementById('detail-content');
  let panelPinned = false;
  let lastMouse = { x: 0, y: 0 };

  function positionPanelNear(x, y) {
    const margin = 16;
    const rect = panel.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let left = x + 16;
    let top = y + 16;
    if (left + rect.width + margin > vw) left = x - rect.width - 16;
    if (left < margin) left = margin;
    if (top + rect.height + margin > vh) top = y - rect.height - 16;
    if (top < margin) top = margin;
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
  }

  function showPanel(html, evt) {
    panelContent.innerHTML = html;
    panel.classList.add('visible');
    panelPinned = true;
    if (evt) { lastMouse = { x: evt.clientX, y: evt.clientY }; }
    positionPanelNear(lastMouse.x, lastMouse.y);
  }

  function hidePanel() {
    panel.classList.remove('visible');
    panelPinned = false;
  }

  document.addEventListener('mousemove', (e) => {
    lastMouse = { x: e.clientX, y: e.clientY };
    if (panelPinned) positionPanelNear(e.clientX, e.clientY);
  });
  document.getElementById('panel-close').addEventListener('click', hidePanel);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hidePanel(); });

  async function run() {
    await mermaid.run({ querySelector: '.mermaid' });

    let currentScale = 1.5;
    function applyScale() {
      document.querySelectorAll('.mermaid svg').forEach((svg) => {
        const vb = svg.viewBox && svg.viewBox.baseVal;
        if (!vb || !vb.width) return;
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        const container = svg.parentElement;
        const fitWidth = Math.max(container.clientWidth - 24, 0);
        const scaledWidth = vb.width * currentScale;
        const targetWidth = Math.max(scaledWidth, fitWidth);
        svg.style.setProperty('width', targetWidth + 'px', 'important');
        svg.style.setProperty('max-width', 'none', 'important');
        svg.style.setProperty('height', 'auto', 'important');
      });
    }
    applyScale();
    window.addEventListener('resize', applyScale);
    document.getElementById('zoom-in').addEventListener('click', () => { currentScale = Math.min(currentScale + 0.25, 4); applyScale(); });
    document.getElementById('zoom-out').addEventListener('click', () => { currentScale = Math.max(currentScale - 0.25, 0.5); applyScale(); });
    document.getElementById('zoom-reset').addEventListener('click', () => { currentScale = 1.5; applyScale(); });

    document.querySelectorAll('.mermaid .node').forEach((el) => {
      const id = (el.id || '').replace(/^flowchart-/, '').replace(/-\\d+$/, '');
      const detail = NODE_DETAILS[id];
      if (!detail) return;
      el.addEventListener('mouseenter', (e) => {
        el.classList.add('node-hover');
        showPanel(renderNode(detail), e);
      });
      el.addEventListener('mouseleave', () => { el.classList.remove('node-hover'); hidePanel(); });
    });

    const edges = document.querySelectorAll('.mermaid .flowchart-link');
    edges.forEach((el, idx) => {
      const detail = CLUE_DETAILS[idx];
      if (!detail) return;
      el.addEventListener('mouseenter', (e) => {
        el.classList.add('edge-hover');
        showPanel(renderClue(detail), e);
      });
      el.addEventListener('mouseleave', () => { el.classList.remove('edge-hover'); hidePanel(); });
    });
  }
  run();
</script>
</body>
</html>
"""


def _wrap_html(mermaid_src: str, node_details: dict, clue_details: list) -> str:
    return (
        _HTML_TEMPLATE
        .replace("__MERMAID_SOURCE__", mermaid_src)
        .replace("__NODE_DETAILS__", json.dumps(node_details, ensure_ascii=False))
        .replace("__CLUE_DETAILS__", json.dumps(clue_details, ensure_ascii=False))
    )
