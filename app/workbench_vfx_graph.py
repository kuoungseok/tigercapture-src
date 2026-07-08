"""VFX graph summary helpers for the Workbench panel."""
from __future__ import annotations

import json
from typing import Any


def vfx_node_graphs_from_track(track: Any) -> list[dict[str, Any]]:
    """Collect mini VFX graph payloads attached to track/node objects."""
    graphs: list[dict[str, Any]] = []

    def _append_payload(payload: Any) -> None:
        if callable(payload):
            try:
                payload = payload()
            except Exception:
                return
        if isinstance(payload, dict) and payload.get("nodes"):
            graphs.append(payload)

    _append_payload(getattr(track, "vfx_node_graph", None))
    for raw in list(getattr(track, "vfx_node_graphs", []) or []):
        _append_payload(raw)
    for entry in list(getattr(track, "node_item_chain", []) or []):
        node = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        if isinstance(node, dict):
            _append_payload(node.get("vfx_node_graph"))
            _append_payload(node.get("vfx_node_graph_payload"))
            continue
        _append_payload(getattr(node, "vfx_node_graph", None))
        _append_payload(getattr(node, "vfx_node_graph_payload", None))
    return graphs


def vfx_node_graph_status_for_track(track: Any) -> dict[str, Any]:
    """Return a compact Workbench-ready VFX graph QA payload."""
    graphs = vfx_node_graphs_from_track(track)
    if not graphs:
        return {
            "ok": False,
            "graph_count": 0,
            "node_count": 0,
            "summary": "VFX graph: none",
            "warnings": [],
        }
    from app.post_pipeline_workflow import vfx_node_graph_qa_report

    report = vfx_node_graph_qa_report(graphs)
    kinds = ", ".join(sorted(str(k) for k in report.get("kind_counts", {}).keys())[:5])
    state = "OK" if report.get("ok") else "Review"
    warnings = [str(v) for v in report.get("warnings", []) or [] if str(v)]
    detail = f"{int(report.get('graph_count', 0) or 0)} graph(s), {int(report.get('node_count', 0) or 0)} node(s)"
    if kinds:
        detail = f"{detail} | {kinds}"
    if warnings:
        detail = f"{detail} | {warnings[0]}"
    payload = dict(report)
    payload["summary"] = f"VFX graph: {state} | {detail}"
    return payload


def vfx_node_graph_overview_for_track(track: Any, *, limit: int = 7) -> list[dict[str, str]]:
    """Return ordered mini-node labels for the Workbench VFX graph strip."""
    graphs = vfx_node_graphs_from_track(track)
    if not graphs:
        return []
    graph = graphs[0]
    nodes = list(graph.get("nodes", []) or []) if isinstance(graph, dict) else []
    warnings = set(str(v) for v in (graph.get("validation_warnings", []) or []) if str(v))
    if not warnings and isinstance(graph, dict):
        try:
            from app.post_pipeline_workflow import VFXNodeGraph

            warnings = set(VFXNodeGraph.from_dict(graph).validation_warnings())
        except Exception:
            warnings = set()
    label_map = {
        "media_in": "Media",
        "chroma_key": "Keyer",
        "b_spline_roto": "Roto",
        "clean_plate": "Clean",
        "planar_tracker": "Track",
        "merge": "Merge",
        "title": "Title",
        "output": "Out",
    }
    rows: list[dict[str, str]] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or raw.get("type") or "")
        node_id = str(raw.get("id") or kind or "node")
        label = label_map.get(kind, kind.replace("_", " ").title() or node_id)
        state = "ok"
        if any(node_id in warning for warning in warnings):
            state = "review"
        rows.append({
            "id": node_id,
            "kind": kind or "node",
            "label": label,
            "state": state,
        })
        if len(rows) >= max(1, int(limit)):
            break
    if len(nodes) > len(rows):
        rows.append({
            "id": "more",
            "kind": "more",
            "label": f"+{len(nodes) - len(rows)}",
            "state": "info",
        })
    return rows


def vfx_node_graph_detail_text_for_track(track: Any) -> str:
    """Return a readable VFX graph QA/details report for Workbench dialogs."""
    graphs = vfx_node_graphs_from_track(track)
    if not graphs:
        return "VFX Graph\n\nNo VFX graph payload is attached to this track."
    status = vfx_node_graph_status_for_track(track)
    lines = [
        "VFX Graph",
        "",
        str(status.get("summary") or "VFX graph: Review"),
        f"Graphs: {int(status.get('graph_count', 0) or 0)}",
        f"Nodes: {int(status.get('node_count', 0) or 0)}",
    ]
    qa_gates = [str(v) for v in status.get("qa_gates", []) or [] if str(v)]
    if qa_gates:
        lines.extend(["", "QA Gates:"])
        lines.extend(f"- {gate}" for gate in qa_gates)
    warnings = [str(v) for v in status.get("warnings", []) or [] if str(v)]
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
    for graph_idx, graph in enumerate(graphs, start=1):
        if not isinstance(graph, dict):
            continue
        lines.extend([
            "",
            f"Graph {graph_idx}",
            f"Output: {graph.get('output_node', 'out')}",
            f"Cache: {graph.get('cache_policy', 'preview_export_locked')}",
            "Nodes:",
        ])
        for node in list(graph.get("nodes", []) or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "")
            kind = str(node.get("kind") or node.get("type") or "")
            inputs = ", ".join(str(v) for v in (node.get("inputs", []) or [])) or "-"
            params = node.get("params", {}) or {}
            compact_params = ""
            if isinstance(params, dict) and params:
                compact_params = " | " + json.dumps(params, ensure_ascii=False, sort_keys=True)[:140]
            lines.append(f"- {node_id}: {kind} <- {inputs}{compact_params}")
    return "\n".join(lines)

