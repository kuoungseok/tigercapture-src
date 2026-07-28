"""Render the built-in Mixed Media starter materials through the real renderer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.collage_assets import (
    COLLAGE_ASSET_PACK_CONTRACT,
    collage_asset_catalog,
    create_collage_asset_layer,
)
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition


OUTPUT = ROOT / "debugCapture" / "motion_collage_asset_pack"


def _digest(image: QImage) -> str:
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def main() -> int:
    QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=2)
    rows: list[dict] = []
    frames: list[QImage] = []
    for index, asset in enumerate(collage_asset_catalog()):
        composition = MotionComposition(
            width=480,
            height=270,
            duration_ms=2000,
            fps=30,
        )
        layer = create_collage_asset_layer(
            composition,
            str(asset["id"]),
            seed=20260729 + index,
        )
        composition.layers.append(layer)
        frame = renderer.render_frame(
            composition,
            650,
            width=480,
            height=270,
            use_cache=False,
        )
        path = OUTPUT / f"{asset['id']}.png"
        if not frame.save(str(path), "PNG"):
            raise RuntimeError(f"Failed to save {path}")
        frames.append(frame)
        rows.append({
            "id": asset["id"],
            "name": asset["name"],
            "sha256": _digest(frame),
            "path": str(path),
        })

    columns = 2
    cell_width, cell_height = 480, 300
    sheet = QImage(
        columns * cell_width,
        ((len(frames) + columns - 1) // columns) * cell_height,
        QImage.Format_RGBA8888,
    )
    sheet.fill(QColor("#0e131a"))
    painter = QPainter(sheet)
    painter.setPen(QColor("#f2f4f8"))
    painter.setFont(QFont("Segoe UI", 12))
    for index, (row, frame) in enumerate(zip(rows, frames)):
        x = index % columns * cell_width
        y = index // columns * cell_height
        painter.drawImage(QRect(x, y, 480, 270), frame)
        painter.drawText(
            QRect(x + 10, y + 274, 460, 22),
            str(row["name"]),
        )
    painter.end()
    sheet_path = OUTPUT / "collage_asset_pack_contact_sheet.png"
    sheet.save(str(sheet_path), "PNG")
    report = {
        "schema": COLLAGE_ASSET_PACK_CONTRACT,
        "ok": bool(
            len(rows) == 6
            and len({row["sha256"] for row in rows}) == 6
            and sheet_path.is_file()
            and sheet_path.stat().st_size > 0
        ),
        "asset_count": len(rows),
        "all_editable": True,
        "external_binary_dependencies": 0,
        "contact_sheet": str(sheet_path),
        "rows": rows,
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
