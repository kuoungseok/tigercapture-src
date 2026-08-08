"""Regenerate desktop and compact Painter UI Inspect/Dev evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.drawing import _PAINT_DIALOG_QSS
from app.painter_ui_dev_handoff import (
    add_ui_dev_annotation,
    inspect_ui_dev_handoff,
    set_ui_dev_ready,
)
from app.painter_ui_inspector import PainterUIInspector
from app.painter_ui_document import (
    add_ui_object,
    add_ui_token,
    create_ui_document,
    update_ui_object,
)
from app.painter_ui_components import (
    convert_ui_object_to_component,
    create_ui_component_variant,
)


def _document_and_report() -> tuple[dict, dict]:
    document = create_ui_document(390, 844)
    document, token = add_ui_token(
        document,
        name="Brand Accent",
        kind="color",
        token_value="#69A7FF",
        scope=["style.fill"],
    )
    document, row = add_ui_object(
        document,
        kind="button",
        name="Continue Button",
        x=24,
        y=712,
        width=342,
        height=52,
        style={"fill": "#69A7FF", "radius": 10},
    )
    document, row = update_ui_object(
        document,
        row["id"],
        {
            "token_bindings": {"style.fill": token["id"]},
            "accessibility": {
                "role": "button",
                "label": "Continue",
                "focus_order": 1,
            },
        },
    )
    document, _status = set_ui_dev_ready(
        document,
        target_type="object",
        target_id=row["id"],
        ready=True,
        note="Keyboard and touch states verified",
    )
    document, _annotation = add_ui_dev_annotation(
        document,
        target_type="object",
        target_id=row["id"],
        text="Export icon assets at @2x and @3x.",
        kind="measurement",
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=row["id"],
        name="Continue Button",
    )
    document, _variant = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Continue Button Emphasis",
    )
    document["selection"] = {
        "object_id": row["id"],
        "object_ids": [row["id"]],
    }
    return document, inspect_ui_dev_handoff(document, object_ids=[row["id"]])


def main() -> int:
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/malgun.ttf")
    app.setFont(QFont("Malgun Gothic", 9))
    app.setStyleSheet(_PAINT_DIALOG_QSS)
    root = (
        Path("debugCapture") / "painter_ui_designer" / "dev_handoff"
    ).resolve()
    root.mkdir(parents=True, exist_ok=True)
    document, report = _document_and_report()
    panel = PainterUIInspector()
    panel.take_layers_page()
    panel.take_asset_pages()
    panel.set_document(document)
    panel.dev_panel.set_report(report)
    panel._tabs.setCurrentWidget(panel.production_panel)
    panel.production_panel.tabs.setCurrentWidget(panel.dev_panel)
    panel.show()
    panel.resize(340, 660)
    app.processEvents()
    panel.grab().save(str(root / "dev_handoff_desktop.png"))
    panel.resize(244, 600)
    app.processEvents()
    panel.grab().save(str(root / "dev_handoff_compact.png"))
    panel.dev_panel.snippet_combo.setCurrentIndex(3)
    panel.dev_panel.scroll_area.verticalScrollBar().setValue(
        panel.dev_panel.scroll_area.verticalScrollBar().maximum()
    )
    app.processEvents()
    panel.grab().save(str(root / "dev_handoff_compact_swiftui.png"))
    panel.dev_panel.snippet_combo.setCurrentIndex(4)
    app.processEvents()
    panel.grab().save(str(root / "dev_handoff_compact_compose.png"))
    report["native_adapter_qa"] = {
        "swiftui": {
            "generated": True,
            "compiler": "not_installed",
            "compiled": "not_run",
        },
        "compose": {
            "generated": True,
            "compiler": "not_installed",
            "compiled": "not_run",
        },
    }
    (root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    panel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
