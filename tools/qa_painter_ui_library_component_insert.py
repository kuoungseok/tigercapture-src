from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _source_document(resource: Path):
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Checkout Button",
        x=24,
        y=24,
        width=240,
        height=72,
    )
    document, _icon = add_ui_object(
        document,
        kind="image",
        name="Arrow Icon",
        parent_id=root["id"],
        x=192,
        y=20,
        width=32,
        height=32,
        content={"source_path": str(resource)},
    )
    document, _component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Checkout Button",
    )
    return document


def main() -> int:
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_library_panel import PainterUILibraryPanel
    from app.painter_ui_library_store import (
        export_ui_library_package,
        install_ui_library_package,
    )

    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\segoeui.ttf")
    app.setFont(QFont("Segoe UI", 9))
    output = (
        Path("debugCapture")
        / "painter_ui_designer"
        / "library_component_insert"
    )
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        resource = root / "arrow.png"
        resource.write_bytes(b"regenerable-qa-resource")
        package = export_ui_library_package(
            _source_document(resource),
            root / "studio-components.tsuilib",
            library_id="studio-components",
            name="Studio Components",
            description="Reusable checkout controls",
        )
        store = root / "store"
        install_ui_library_package(package["path"], store_root=store)
        panel = PainterUILibraryPanel(store_root=store)
        panel.show()
        app.processEvents()
        library = panel.tree.topLevelItem(0)
        version = library.child(0)
        library.setExpanded(True)
        version.setExpanded(True)
        panel.tree.setCurrentItem(version.child(0))
        app.processEvents()
        for name, size in (
            ("desktop", (420, 520)),
            ("compact", (280, 460)),
        ):
            panel.resize(*size)
            app.processEvents()
            panel.grab().save(str(output / f"library_{name}.png"))
        panel.close()
        panel.deleteLater()
        app.processEvents()
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
