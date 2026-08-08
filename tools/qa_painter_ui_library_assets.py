"""Regenerate Painter UI library asset-browser evidence."""
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
from app.painter_ui_document import (
    add_ui_component,
    add_ui_object,
    add_ui_token,
    create_ui_document,
)
from app.painter_ui_library_assets import search_ui_library_assets
from app.painter_ui_library_panel import PainterUILibraryPanel
from app.painter_ui_library_store import (
    export_ui_library_package,
    install_ui_library_package,
)
from app.painter_ui_styles import add_ui_style


def _document(resource: Path) -> dict:
    document = create_ui_document(800, 600)
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Checkout Button",
    )
    document, _image = add_ui_object(
        document,
        kind="image",
        name="Checkout Icon",
        parent_id=root["id"],
        content={"source_path": str(resource)},
    )
    document, _component = add_ui_component(
        document,
        name="Checkout Button",
        root_object_id=root["id"],
    )
    document, token = add_ui_token(
        document,
        name="Brand Accent",
        kind="color",
        token_value="#3D8BFF",
        scope=["style.fill"],
    )
    document, _style = add_ui_style(
        document,
        name="Brand Accent Fill",
        kind="color",
        properties={"fill": "#3D8BFF"},
        token_bindings={"style.fill": token["id"]},
    )
    return document


def main() -> int:
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    app.setFont(QFont("Segoe UI", 9))
    app.setStyleSheet(_PAINT_DIALOG_QSS)
    root = (
        Path("debugCapture")
        / "painter_ui_designer"
        / "library_assets"
    ).resolve()
    root.mkdir(parents=True, exist_ok=True)
    resource = root / "checkout-icon.png"
    resource.write_bytes(b"regenerable-library-asset")
    store = root / "store"
    exported = export_ui_library_package(
        _document(resource),
        root / "studio-controls.tsuilib",
        library_id="studio-controls",
        name="Studio Controls",
    )
    install_ui_library_package(exported["path"], store_root=store)
    panel = PainterUILibraryPanel(store_root=store)
    version_item = panel.tree.topLevelItem(0).child(0)
    style_item = next(
        version_item.child(index)
        for index in range(version_item.childCount())
        if version_item.child(index).data(3, 256) == "style"
    )
    panel.tree.setCurrentItem(style_item)
    panel.show()
    app.processEvents()
    panel.resize(340, 620)
    app.processEvents()
    panel.grab().save(str(root / "library_assets_desktop.png"))
    panel.resize(240, 520)
    app.processEvents()
    panel.grab().save(str(root / "library_assets_compact.png"))
    report = search_ui_library_assets(store_root=store)
    (root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    panel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
