from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _application():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _source_image(path: Path) -> None:
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    image = QImage(240, 160, QImage.Format.Format_ARGB32)
    image.fill(QColor("#18263A"))
    painter = QPainter(image)
    painter.fillRect(0, 0, 120, 80, QColor("#E84D62"))
    painter.fillRect(120, 0, 120, 80, QColor("#36B66F"))
    painter.fillRect(0, 80, 120, 80, QColor("#3F79E8"))
    painter.fillRect(120, 80, 120, 80, QColor("#F2C94C"))
    painter.setPen(QPen(QColor("#FFFFFFFF"), 4.0))
    painter.drawLine(0, 0, 240, 160)
    painter.drawLine(0, 160, 240, 0)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Unable to write source image: {path}")


def _payload() -> dict:
    cases = [
        (
            "1:10",
            "Fill",
            40,
            60,
            {"scaleMode": "FILL"},
        ),
        (
            "1:11",
            "Fit rotated 90",
            300,
            60,
            {"scaleMode": "FIT", "rotation": 90},
        ),
        (
            "1:12",
            "REST stretch crop",
            560,
            60,
            {
                "scaleMode": "STRETCH",
                "imageTransform": [[0.5, 0.0, 0.5], [0.0, 1.0, 0.0]],
            },
        ),
        (
            "1:13",
            "Tile quarter rotated",
            40,
            260,
            {"scaleMode": "TILE", "scalingFactor": 0.25, "rotation": 90},
        ),
        (
            "1:14",
            "Affine skew",
            300,
            260,
            {
                "scaleMode": "STRETCH",
                "imageTransform": [[0.8, 0.2, 0.0], [0.0, 0.8, 0.1]],
            },
        ),
        (
            "1:15",
            "Crop opacity",
            560,
            260,
            {
                "scaleMode": "STRETCH",
                "imageTransform": [[1.0, 0.0, 0.0], [0.0, 0.5, 0.25]],
                "opacity": 0.55,
            },
        ),
    ]
    children = []
    for node_id, name, x, y, paint in cases:
        children.append(
            {
                "id": node_id,
                "type": "RECTANGLE",
                "name": name,
                "absoluteBoundingBox": {
                    "x": x,
                    "y": y,
                    "width": 220,
                    "height": 150,
                },
                "cornerRadius": 12,
                "fills": [
                    {
                        "type": "IMAGE",
                        "imageRef": "qa-image",
                        **paint,
                    }
                ],
            }
        )
    return {
        "name": "Figma image fill QA",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "QA",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Image Fill Modes",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 820,
                                "height": 470,
                            },
                            "backgrounds": [
                                {
                                    "type": "SOLID",
                                    "color": {"r": 0.94, "g": 0.96, "b": 0.99},
                                }
                            ],
                            "children": children,
                        }
                    ],
                }
            ],
        },
    }


def run(output: Path) -> dict:
    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    _application()
    output.mkdir(parents=True, exist_ok=True)
    source_path = output / "source-quadrants.png"
    _source_image(source_path)
    document, import_report = import_figma_payload(
        _payload(),
        source="figma-image-fill-qa",
        image_paths={"qa-image": str(source_path)},
    )
    artboard_id = str(document["active_artboard_id"])
    render = render_ui_artboard(document, artboard_id, density=1.5)
    render_path = output / "figma-image-fill-render.png"
    if not render.save(str(render_path), "PNG"):
        raise RuntimeError(f"Unable to write render: {render_path}")
    umg = painter_ui_to_umg_document(document, artboard_id=artboard_id)
    layers = {str(row["Id"]): row for row in umg["Layers"]}
    rows = []
    for row in document["objects"]:
        content = dict(row.get("content") or {})
        layer = layers[str(row["id"])]
        rows.append(
            {
                "id": row["id"],
                "figma_node_id": content.get("figma_node_id"),
                "name": row["name"],
                "image_fit": content.get("image_fit"),
                "image_rotation": content.get("image_rotation"),
                "tile_scale": content.get("tile_scale"),
                "figma_image_transform": content.get("figma_image_transform"),
                "umg_disposition": layer["Disposition"],
                "umg_mode": layer["ImageFill"].get("Mode"),
                "umg_crop": layer["ImageFill"].get("Crop"),
                "umg_block_reasons": list(layer.get("BlockReasons") or []),
            }
        )
    by_name = {row["name"]: row for row in rows}
    if by_name["REST stretch crop"]["umg_disposition"] != "Native":
        raise RuntimeError("Axis-aligned Figma transform did not map to native UMG crop")
    if by_name["REST stretch crop"]["umg_mode"] != "Crop":
        raise RuntimeError("Axis-aligned Figma transform did not emit Crop mode")
    if "image_fill_transform_requires_ui_material_or_bake" not in by_name[
        "Affine skew"
    ]["umg_block_reasons"]:
        raise RuntimeError("Skewed Figma transform was not explicitly blocked")
    plugin = export_figma_plugin_package(document, output / "figma-plugin")
    code_path = Path(plugin["output_dir"]) / "code.js"
    code = code_path.read_text("utf-8")
    if "function imagePaint(row,imageHash)" not in code:
        raise RuntimeError("Figma round-trip plugin omitted image paint semantics")
    pixels = bytes(render.constBits())
    report = {
        "schema": "tigerstudio.painter.ui.figma_image_fill_qa.v1",
        "ok": True,
        "source_path": str(source_path.resolve()),
        "render_path": str(render_path.resolve()),
        "render_size": [render.width(), render.height()],
        "render_sha256": hashlib.sha256(pixels).hexdigest(),
        "case_count": len(rows),
        "import_warning_count": len(import_report["warnings"]),
        "figma_compatibility": inspect_figma_compatibility(document)["counts"],
        "rows": rows,
        "plugin_output": str(Path(plugin["output_dir"]).resolve()),
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render and classify Figma image-fill placement modes."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "debugCapture" / "painter_ui_figma_image_fill_qa",
    )
    args = parser.parse_args()
    report = run(args.output.resolve())
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "case_count": report["case_count"],
                "render_path": report["render_path"],
                "report_path": report["report_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
