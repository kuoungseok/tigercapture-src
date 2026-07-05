"""Deterministic Node Graph interaction fuzzer.

It exercises the dynamic QGraphicsScene paths that tend to produce hard Qt
crashes: drag-create links, reject bad links, delete selected nodes while
connections exist, move nodes, and load/save scene snapshots repeatedly.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _node_ports(scene) -> tuple[list, list]:
    outputs = []
    inputs = []
    for item in [scene._in_node, scene._out_node, *scene._serial_nodes]:
        for port in getattr(item, "all_ports", lambda: [])():
            if port.is_input:
                inputs.append(port)
            else:
                outputs.append(port)
    return outputs, inputs


def _validate_scene(scene) -> list[str]:
    issues: list[str] = []
    seen_connections = set()
    for conn in list(scene._connections):
        if id(conn) in seen_connections:
            issues.append("duplicate connection object")
        seen_connections.add(id(conn))
        if conn.source is None or conn.target is None:
            issues.append("committed connection missing endpoint")
            continue
        if conn not in conn.source.connections:
            issues.append("connection absent from source port")
        if conn not in conn.target.connections:
            issues.append("connection absent from target port")
        if conn.scene() is not scene:
            issues.append("connection absent from scene")
    for item in [scene._in_node, scene._out_node, *scene._serial_nodes]:
        for port in getattr(item, "all_ports", lambda: [])():
            for conn in list(port.connections):
                if conn not in scene._connections:
                    issues.append("port references orphan connection")
    return issues


def run_node_graph_fuzzer(*, iterations: int = 240, seed: int = 42) -> dict[str, Any]:
    _ensure_app()
    from PySide6.QtCore import QPointF

    from app.workbench.node_graph.scene import NodeGraphScene

    rng = random.Random(seed)
    scene = NodeGraphScene()
    failures: list[str] = []
    op_counts: dict[str, int] = {}

    for step in range(int(iterations)):
        op = rng.choice([
            "add_serial",
            "add_blur",
            "add_effect",
            "add_parallel",
            "connect",
            "reject",
            "move",
            "delete",
            "roundtrip",
        ])
        op_counts[op] = op_counts.get(op, 0) + 1
        try:
            if op == "add_serial":
                scene.add_serial_node(pos=QPointF(rng.randint(-120, 420), rng.randint(-120, 180)))
            elif op == "add_blur":
                scene.add_blur_node(pos=QPointF(rng.randint(-120, 420), rng.randint(-120, 180)), auto_connect=bool(rng.getrandbits(1)))
            elif op == "add_effect":
                scene.add_effect_node(
                    rng.choice(["curves", "glow", "vignette", "lut"]),
                    pos=QPointF(rng.randint(-120, 420), rng.randint(-120, 180)),
                    auto_connect=bool(rng.getrandbits(1)),
                )
            elif op == "add_parallel":
                scene.add_parallel_mixer(pos=QPointF(rng.randint(-120, 420), rng.randint(-120, 180)))
            elif op in {"connect", "reject"}:
                outputs, inputs = _node_ports(scene)
                if outputs and inputs:
                    src = rng.choice(outputs)
                    dst = rng.choice(inputs)
                    if op == "reject":
                        bad_targets = outputs + [src]
                        dst = rng.choice(bad_targets)
                    scene.start_connection_drag(src, src.scenePos())
                    scene.update_connection_drag(src.scenePos() + QPointF(rng.randint(10, 120), rng.randint(-20, 20)))
                    scene.end_connection_drag(dst)
            elif op == "move" and scene._serial_nodes:
                node = rng.choice(scene._serial_nodes)
                node.setPos(node.scenePos() + QPointF(rng.randint(-20, 25), rng.randint(-18, 18)))
            elif op == "delete" and scene._serial_nodes:
                scene.clearSelection()
                for node in rng.sample(scene._serial_nodes, k=1):
                    node.setSelected(True)
                scene.delete_selected()
            elif op == "roundtrip":
                data = scene.to_data()
                scene.load_from_data(data)

            issues = _validate_scene(scene)
            if issues:
                failures.append(f"step {step} {op}: " + "; ".join(issues[:5]))
                break
        except Exception as exc:
            failures.append(f"step {step} {op}: exception {exc!r}")
            break

    return {
        "ok": not failures,
        "summary": {
            "iterations": int(iterations),
            "seed": int(seed),
            "failures": len(failures),
            "operations": op_counts,
            "nodes": len(scene._serial_nodes),
            "connections": len(scene._connections),
        },
        "failures": failures,
        "final_scene": scene.to_data(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Node Graph fuzzer.")
    parser.add_argument("--iterations", type=int, default=240)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/node_graph_fuzzer_qa.json"))
    args = parser.parse_args()

    report = run_node_graph_fuzzer(iterations=args.iterations, seed=args.seed)
    out_path = ROOT / args.out if not args.out.is_absolute() else args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
