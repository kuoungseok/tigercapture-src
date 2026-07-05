"""Fast QA for color preview/export parity and node-graph repair.

This intentionally avoids FFmpeg. It validates the shared CPU render contracts
that decide whether the editor preview, saved node graph, and export bake path
see the same color node chain.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": str(detail or "")}


def run_color_preview_parity_qa() -> dict:
    _qapp()

    from app.color_grading import ColorGrade
    from app.project_player import (
        _apply_node_chain_preview_compare,
        _apply_node_effect_player,
    )
    from app.video_exporter import VideoExportThread
    from app.workbench.node_graph.items.node_item import NodeItem
    from app.workbench.node_graph.widget import NodeGraphWidget

    checks: list[dict] = []

    fresh_track = SimpleNamespace(node_graph_view_data=None)
    widget = NodeGraphWidget()
    try:
        widget.set_track(fresh_track)
        chain_ids = [
            getattr(node, "node_id", "")
            for node in widget.scene.evaluate_chain_nodes_to(widget.scene._out_node)
        ]
        checks.append(_check("default_node_wired", chain_ids == ["N1"], ",".join(chain_ids)))
    finally:
        widget.close()

    legacy_track = SimpleNamespace(
        node_graph_view_data={
            "nodes": [
                {
                    "id": "N1",
                    "kind": "serial",
                    "label": "Node 1",
                    "x": -200,
                    "y": -45,
                }
            ],
            "connections": [],
            "next_id": 2,
        }
    )
    widget = NodeGraphWidget()
    try:
        widget.set_track(legacy_track)
        saved = legacy_track.node_graph_view_data
        checks.append(
            _check(
                "legacy_graph_repaired",
                len(saved.get("connections", [])) == 2,
                f"connections={len(saved.get('connections', []))}",
            )
        )
    finally:
        widget.close()

    rgb = np.array(
        [
            [[20, 40, 60], [180, 160, 140], [80, 90, 100], [220, 200, 180]],
            [[30, 50, 70], [170, 150, 130], [70, 80, 90], [210, 190, 170]],
        ],
        dtype=np.uint8,
    )
    node = NodeItem("N1", "Node 1")
    node.color_grade = ColorGrade(brightness=28, contrast=22, saturation=18)
    preview = _apply_node_effect_player(node, rgb.copy(), [], 0)
    exporter = VideoExportThread(
        ROOT / "qa_corpus" / "synthetic_source.mp4",
        ROOT / "qa_corpus" / "synthetic_out.mp4",
        [(0, 1000, 1.0)],
        node_item_chain=[(node, [])],
    )
    try:
        exported = exporter._apply_node_chain_cpu(rgb.copy(), 0)
    finally:
        exporter.deleteLater()
    checks.append(
        _check(
            "preview_export_parity",
            np.array_equal(preview, exported),
            f"preview_sum={int(preview.sum())} export_sum={int(exported.sum())}",
        )
    )

    before = _apply_node_chain_preview_compare(rgb.copy(), [(node, [])], 0, "before")
    split = _apply_node_chain_preview_compare(rgb.copy(), [(node, [])], 0, "split")
    checks.append(
        _check(
            "preview_compare_modes",
            before is not None
            and split is not None
            and np.array_equal(before, rgb)
            and not np.array_equal(split, rgb),
            "before skips color grade; split composites before/after",
        )
    )

    ok = all(row["ok"] for row in checks)
    return {"ok": ok, "checks": checks}


def main() -> int:
    report = run_color_preview_parity_qa()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
