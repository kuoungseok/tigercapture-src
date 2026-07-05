from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .artifacts import relpath


def _node_id(kind: str, raw_id: str) -> str:
    return f"{kind}:{raw_id}"


def _append_node(nodes: dict[str, dict[str, Any]], node_id: str, **payload: Any) -> None:
    if node_id in nodes:
        nodes[node_id].update({key: value for key, value in payload.items() if value not in (None, "")})
        return
    nodes[node_id] = {"id": node_id, **payload}


def _append_edge(edges: list[dict[str, Any]], source: str, target: str, relation: str) -> None:
    edge = {"source": source, "target": target, "relation": relation}
    if edge not in edges:
        edges.append(edge)


def build_review_evidence_graph(report: Mapping[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    features = [row for row in list(report.get("features", []) or []) if isinstance(row, Mapping)]
    scenarios = [row for row in list(report.get("scenarios", []) or []) if isinstance(row, Mapping)]
    feature_action_scenarios = [
        row
        for row in list(report.get("feature_action_scenarios", []) or [])
        if isinstance(row, Mapping)
    ]
    artifacts = [row for row in list(report.get("artifacts", []) or []) if isinstance(row, Mapping)]
    resources = [
        row
        for row in list(((report.get("sample_report") or {}).get("resources") if isinstance(report.get("sample_report"), Mapping) else []) or [])
        if isinstance(row, Mapping)
    ]

    for feature in features:
        fid = str(feature.get("id") or "")
        if not fid:
            continue
        feature_node = _node_id("feature", fid)
        _append_node(
            nodes,
            feature_node,
            kind="feature",
            title=feature.get("title"),
            status=feature.get("status"),
            category=feature.get("category"),
            claim=feature.get("claim"),
        )
        for artifact_id in list(feature.get("artifact_ids", []) or []):
            artifact_node = _node_id("artifact", str(artifact_id))
            _append_node(nodes, artifact_node, kind="artifact", title=str(artifact_id))
            _append_edge(edges, feature_node, artifact_node, "has_artifact")
        for resource_id in list(feature.get("resource_ids", []) or []):
            sample_node = _node_id("sample", str(resource_id))
            _append_node(nodes, sample_node, kind="sample", title=str(resource_id))
            _append_edge(edges, feature_node, sample_node, "uses_sample")
        for qa_report in list(feature.get("qa_reports", []) or []):
            qa_node = _node_id("qa", str(qa_report))
            _append_node(nodes, qa_node, kind="qa_report", path=str(qa_report), state=(feature.get("qa_states") or {}).get(qa_report))
            _append_edge(edges, feature_node, qa_node, "checked_by")

    for scenario in scenarios:
        sid = str(scenario.get("id") or "")
        if not sid:
            continue
        scenario_node = _node_id("scenario", sid)
        _append_node(
            nodes,
            scenario_node,
            kind="scenario",
            title=scenario.get("title"),
            status=scenario.get("status"),
            mode=scenario.get("mode"),
            summary=scenario.get("summary"),
        )
        fid = str(scenario.get("feature_id") or "")
        if fid:
            feature_node = _node_id("feature", fid)
            _append_node(nodes, feature_node, kind="feature", title=fid)
            _append_edge(edges, feature_node, scenario_node, "has_scenario")
        for resource_id in list(scenario.get("sample_resource_ids", []) or []):
            sample_node = _node_id("sample", str(resource_id))
            _append_node(nodes, sample_node, kind="sample", title=str(resource_id))
            _append_edge(edges, scenario_node, sample_node, "uses_sample")
        for artifact_id in list(scenario.get("artifact_ids", []) or []):
            artifact_node = _node_id("artifact", str(artifact_id))
            _append_node(nodes, artifact_node, kind="artifact", title=str(artifact_id))
            _append_edge(edges, scenario_node, artifact_node, "produces_artifact")
        for action_id in list(scenario.get("action_ids", []) or []):
            action_node = _node_id("action", str(action_id))
            _append_node(nodes, action_node, kind="action", title=str(action_id))
            _append_edge(edges, scenario_node, action_node, "executes")

    for scenario in feature_action_scenarios:
        sid = str(scenario.get("id") or "")
        if not sid:
            continue
        scenario_node = _node_id("feature_action", sid)
        _append_node(
            nodes,
            scenario_node,
            kind="feature_action_scenario",
            title=scenario.get("title"),
            status=scenario.get("status"),
            topic_id=scenario.get("topic_id"),
            capture_method=scenario.get("capture_method"),
            automation_level=scenario.get("automation_level"),
            summary=scenario.get("summary"),
        )
        fid = str(scenario.get("feature_id") or "")
        if fid:
            feature_node = _node_id("feature", fid)
            _append_node(nodes, feature_node, kind="feature", title=fid)
            _append_edge(edges, feature_node, scenario_node, "has_feature_action_scenario")
        for resource_id in list(scenario.get("sample_resource_ids", []) or []):
            sample_node = _node_id("sample", str(resource_id))
            _append_node(nodes, sample_node, kind="sample", title=str(resource_id))
            _append_edge(edges, scenario_node, sample_node, "uses_sample")
        for artifact_id in list(scenario.get("artifact_ids", []) or []):
            artifact_node = _node_id("artifact", str(artifact_id))
            _append_node(nodes, artifact_node, kind="artifact", title=str(artifact_id))
            _append_edge(edges, scenario_node, artifact_node, "produces_artifact")
        for action_id in list(scenario.get("action_ids", []) or []):
            action_node = _node_id("action", str(action_id))
            _append_node(nodes, action_node, kind="action", title=str(action_id))
            _append_edge(edges, scenario_node, action_node, "executes")

    for resource in resources:
        rid = str(resource.get("id") or "")
        if not rid:
            continue
        _append_node(
            nodes,
            _node_id("sample", rid),
            kind="sample",
            title=resource.get("title") or rid,
            ready=bool(resource.get("ready")),
            path=resource.get("path"),
            role=resource.get("role"),
        )

    for artifact in artifacts:
        aid = str(artifact.get("id") or "")
        if not aid:
            continue
        _append_node(
            nodes,
            _node_id("artifact", aid),
            kind="artifact",
            title=artifact.get("title") or aid,
            artifact_kind=artifact.get("kind"),
            exists=bool(artifact.get("exists")),
            output_path=artifact.get("output_path"),
            size=artifact.get("size"),
        )

    return {
        "kind": "review_evidence_graph",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "features": len(features),
            "scenarios": len(scenarios),
            "feature_action_scenarios": len(feature_action_scenarios),
            "artifacts": len(artifacts),
            "samples": len(resources),
            "nodes": len(nodes),
            "edges": len(edges),
        },
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def write_review_evidence_graph(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    project_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    target = Path(path)
    graph = build_review_evidence_graph(report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact = {
        "id": "evidence_graph",
        "title": "Review evidence graph",
        "kind": "json",
        "source_path": "",
        "output_path": relpath(target, root=Path(project_root)),
        "exists": target.exists(),
        "size": int(target.stat().st_size) if target.exists() else 0,
    }
    return graph, artifact
