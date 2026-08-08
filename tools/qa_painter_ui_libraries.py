"""Capture the compact Painter UI local Libraries Assets panel."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.painter_ui_document import add_ui_token, create_ui_document
from app.painter_ui_library_panel import PainterUILibraryPanel
from app.painter_ui_library_store import (
    export_ui_library_package,
    install_ui_library_package,
)
from app.painter_ui_styles import add_ui_style


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    with tempfile.TemporaryDirectory(prefix="tiger_ui_library_qa_") as temp:
        root = Path(temp)
        document = create_ui_document(1440, 900, name="Desktop")
        document, _ = add_ui_token(
            document,
            name="Brand Blue",
            kind="color",
            token_value="#4B8FCA",
        )
        document, _ = add_ui_style(
            document,
            name="Brand Fill",
            kind="color",
            properties={"fill": "#4B8FCA"},
        )
        v1 = export_ui_library_package(
            document,
            root / "studio-core-v1.tsuilib",
            library_id="studio-core",
            name="Studio Core",
            version=1,
        )
        install_ui_library_package(v1["path"], store_root=root / "store")
        document, _ = add_ui_style(
            document,
            name="Panel Elevation",
            kind="effect",
            properties={"shadow": {"blur": 16}},
        )
        v2 = export_ui_library_package(
            document,
            root / "studio-core-v2.tsuilib",
            library_id="studio-core",
            name="Studio Core",
            version=2,
        )
        panel = PainterUILibraryPanel(store_root=root / "store")
        panel.resize(360, 560)
        panel.set_document(document)
        panel.set_update_candidate(v2["path"])
        panel.show()
        app.processEvents()
        output = (
            ROOT
            / "debugCapture"
            / "painter_ui_designer"
            / "painter_ui_designer_m3_local_libraries.png"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if not panel.grab().save(str(output)):
            raise RuntimeError(f"Failed to save Libraries QA: {output}")
        print(output)
        panel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
