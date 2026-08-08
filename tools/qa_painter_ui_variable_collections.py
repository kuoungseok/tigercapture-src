"""Capture the compact Painter UI Variable Collections and Modes panel."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.painter_ui_document import add_ui_token, create_ui_document
from app.painter_ui_token_library import PainterUITokenLibrary
from app.painter_ui_variables import (
    add_ui_variable_collection,
    add_ui_variable_mode,
)


def _sample() -> tuple[dict, str, str]:
    document = create_ui_document(390, 844, name="Mobile")
    document, collection = add_ui_variable_collection(
        document,
        name="Interface Density",
        kind="density",
    )
    document, compact = add_ui_variable_mode(
        document,
        collection_id=collection["id"],
        name="Compact",
    )
    document, _ = add_ui_variable_mode(
        document,
        collection_id=collection["id"],
        name="Comfortable",
    )
    for name, kind, value, compact_value in (
        ("Control Gap", "spacing", 12, 8),
        ("Panel Radius", "radius", 10, 6),
        ("Quiet Opacity", "opacity", 0.72, 0.62),
    ):
        document, _ = add_ui_token(
            document,
            name=name,
            kind=kind,
            token_value=value,
            collection_id=collection["id"],
            variable_type="number",
            mode_values={compact["id"]: compact_value},
        )
    return document, collection["id"], compact["id"]


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    document, collection_id, mode_id = _sample()
    panel = PainterUITokenLibrary()
    panel.resize(360, 760)
    panel.set_document(document)
    panel.collection_combo.setCurrentIndex(
        panel.collection_combo.findData(collection_id)
    )
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(mode_id))
    if panel.tree.topLevelItemCount():
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0).child(0))
    panel.show()
    app.processEvents()
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "painter_ui_designer_m3_variable_collections.png"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not panel.grab().save(str(output)):
        raise RuntimeError(f"Failed to save Variable Collections QA: {output}")
    print(output)
    panel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
