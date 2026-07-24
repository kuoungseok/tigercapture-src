"""Launch the standalone TigerCapture MMD player."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.mmd.player_window import DEFAULT_MODEL, DEFAULT_MOTION, MMDPlayerWindow
from app.style import APP_QSS
from app.window_placement import install_global_window_placement


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TigerCapture MMD player")
    parser.add_argument("--model", default="", help=f"PMX or PMD model path, default: {DEFAULT_MODEL}")
    parser.add_argument("--vmd", default="", help=f"VMD motion path, default with built-in model: {DEFAULT_MOTION}")
    args = parser.parse_args(argv)

    QCoreApplication.setApplicationName("TigerCapture MMD Player")
    QCoreApplication.setOrganizationName("TigerCapture")
    app = QApplication(sys.argv[:1])
    install_global_window_placement(app)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    apply_ui_font(app)
    icon_path = ROOT / "resources" / "tigercapture.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MMDPlayerWindow(args.model or None, args.vmd or None)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
