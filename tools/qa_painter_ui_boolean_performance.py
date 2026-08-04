"""Measure deterministic Painter Boolean authoring costs at milestone scales."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _milliseconds(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def _path_hash(path) -> str:
    from app.painter_ui_boolean_geometry import qpath_to_svg_path

    return hashlib.sha256(qpath_to_svg_path(path).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(
            ROOT
            / "debugCapture"
            / "painter_ui_boolean_m1"
            / "boolean_performance_report.json"
        ),
    )
    args = parser.parse_args()

    from PySide6.QtCore import QRectF

    from app.painter_ui_boolean import compose_ui_boolean, set_ui_boolean
    from app.painter_ui_boolean_geometry import resolve_ui_boolean_path
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
        update_ui_object,
    )

    document = create_ui_document(2400, 1600, name="Boolean 100")
    operand_ids: list[str] = []
    for index in range(100):
        column = index % 10
        row = index // 10
        document, operand = add_ui_object(
            document,
            kind="ellipse" if index % 3 == 0 else "rectangle",
            name=f"Operand {index + 1}",
            x=100 + column * 78,
            y=100 + row * 58,
            width=130,
            height=100,
            style={"fill": "#5599DDFF", "radius": 12},
        )
        operand_ids.append(operand["id"])

    start = time.perf_counter()
    document, group = compose_ui_boolean(document, "union", operand_ids)
    compose_100_ms = _milliseconds(start)
    by_id = {row["id"]: row for row in document["objects"]}
    group_row = by_id[group["id"]]
    rect_for = lambda row: QRectF(
        float(row.get("x") or 0.0),
        float(row.get("y") or 0.0),
        float(row.get("width") or 0.0),
        float(row.get("height") or 0.0),
    )
    resolve_samples: list[float] = []
    hashes: list[str] = []
    for _index in range(5):
        start = time.perf_counter()
        path = resolve_ui_boolean_path(document["objects"], group_row, rect_for)
        resolve_samples.append(_milliseconds(start))
        hashes.append(_path_hash(path))

    document = select_ui_objects(document, [group["id"]])
    start = time.perf_counter()
    document, _moved = update_ui_object(
        document,
        operand_ids[0],
        {"x": float(by_id[operand_ids[0]]["x"]) + 1.0},
    )
    move_one_of_100_ms = _milliseconds(start)
    start = time.perf_counter()
    document, _changed = set_ui_boolean(
        document,
        group["id"],
        "exclude",
        operand_ids,
        group=True,
    )
    change_operation_100_ms = _milliseconds(start)

    # A closed 10,000-node vector network measures the path-parser and Boolean
    # resolver cost without manufacturing 10,000 separate document objects.
    node_count = 10_000
    nodes = [
        {
            "id": f"node-{index}",
            "x": index / (node_count - 1),
            "y": 0.45 + (0.05 if index % 2 else -0.05),
        }
        for index in range(node_count)
    ]
    segments = [
        {
            "id": f"segment-{index}",
            "start_node_id": f"node-{index}",
            "end_node_id": f"node-{(index + 1) % node_count}",
            "kind": "line",
        }
        for index in range(node_count)
    ]
    vector = {
        "id": "vector-10000",
        "kind": "path",
        "x": 20.0,
        "y": 20.0,
        "width": 1200.0,
        "height": 600.0,
        "rotation": 0.0,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "style": {"fill": "#FFFFFFFF"},
        "content": {
            "vector_network": {
                "closed": True,
                "nodes": nodes,
                "segments": segments,
            }
        },
    }
    cutter = {
        "id": "cutter",
        "kind": "ellipse",
        "x": 400.0,
        "y": 100.0,
        "width": 500.0,
        "height": 400.0,
        "rotation": 0.0,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "style": {"fill": "#FFFFFFFF"},
        "content": {},
    }
    vector_group = {
        "id": "vector-boolean",
        "kind": "path",
        "content": {
            "boolean": {
                "enabled": True,
                "group": True,
                "operation": "subtract",
                "operand_ids": [vector["id"], cutter["id"]],
            }
        },
    }
    start = time.perf_counter()
    vector_path = resolve_ui_boolean_path(
        [vector, cutter, vector_group],
        vector_group,
        rect_for,
    )
    resolve_10000_nodes_ms = _milliseconds(start)

    report = {
        "schema": "tigerstudio.painter.ui.boolean.performance.v1",
        "ok": bool(
            len(set(hashes)) == 1
            and vector_path is not None
            and not vector_path.isEmpty()
        ),
        "environment": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
        },
        "operand_100": {
            "compose_ms": compose_100_ms,
            "resolve_samples_ms": resolve_samples,
            "resolve_median_ms": round(statistics.median(resolve_samples), 3),
            "move_one_operand_ms": move_one_of_100_ms,
            "change_operation_ms": change_operation_100_ms,
            "deterministic_hash": hashes[0],
            "hashes_identical": len(set(hashes)) == 1,
        },
        "vector_10000_nodes": {
            "resolve_ms": resolve_10000_nodes_ms,
            "result_hash": _path_hash(vector_path),
        },
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(output)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
