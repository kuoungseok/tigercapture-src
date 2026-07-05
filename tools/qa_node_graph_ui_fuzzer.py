"""Widget-level Node Graph fuzzer.

The scene fuzzer catches low-level connection integrity.  This one exercises
the actual NodeGraphWidget API, persistence binding, minimap refresh, selection,
bypass, fit/zoom, and delete paths.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def run_node_graph_ui_fuzzer(*, iterations: int = 160, seed: int = 42) -> dict[str, Any]:
    app = _ensure_app()
    from app.workbench.node_graph.widget import NodeGraphWidget
    from tools.qa_node_graph_fuzzer import _validate_scene

    rng = random.Random(seed)
    widget = NodeGraphWidget()
    track = SimpleNamespace(node_graph_view_data=None)
    widget.set_track(track)
    widget.resize(760, 420)
    widget.show()
    app.processEvents()

    failures: list[str] = []
    op_counts: dict[str, int] = {}
    for step in range(int(iterations)):
        op = rng.choice([
            "add_serial",
            "add_blur",
            "add_effect",
            "add_parallel",
            "select",
            "bypass",
            "delete",
            "fit",
            "save_reload",
            "set_track_roundtrip",
        ])
        op_counts[op] = op_counts.get(op, 0) + 1
        try:
            if op == "add_serial":
                widget.add_serial_node()
            elif op == "add_blur":
                widget.add_blur_node()
            elif op == "add_effect":
                widget.add_effect_node(rng.choice(["curves", "glow", "vignette", "lut"]))
            elif op == "add_parallel":
                widget.add_parallel_mixer()
            elif op == "select" and widget.scene._serial_nodes:
                widget.scene.clearSelection()
                rng.choice(widget.scene._serial_nodes).setSelected(True)
            elif op == "bypass":
                widget.bypass_selected()
            elif op == "delete" and widget.scene._serial_nodes:
                widget.scene.clearSelection()
                rng.choice(widget.scene._serial_nodes).setSelected(True)
                widget.delete_selected()
            elif op == "fit":
                widget.fit_all()
            elif op == "save_reload":
                data = widget.scene.to_data()
                widget.scene.load_from_data(data)
            elif op == "set_track_roundtrip":
                widget.set_track(SimpleNamespace(node_graph_view_data=widget.scene.to_data()))
            app.processEvents()
            issues = _validate_scene(widget.scene)
            if issues:
                failures.append(f"step {step} {op}: " + "; ".join(issues[:5]))
                break
        except Exception as exc:
            failures.append(f"step {step} {op}: exception {exc!r}")
            break

    report = {
        "ok": not failures,
        "summary": {
            "iterations": int(iterations),
            "seed": int(seed),
            "failures": len(failures),
            "operations": op_counts,
            "nodes": len(widget.scene._serial_nodes),
            "connections": len(widget.scene._connections),
        },
        "failures": failures,
        "final_scene": widget.scene.to_data(),
    }
    widget.close()
    app.processEvents()
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run widget-level Node Graph fuzzer.")
    parser.add_argument("--iterations", type=int, default=160)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/node_graph_ui_fuzzer_qa.json"))
    args = parser.parse_args()
    report = run_node_graph_ui_fuzzer(iterations=args.iterations, seed=args.seed)
    out_path = ROOT / args.out if not args.out.is_absolute() else args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
