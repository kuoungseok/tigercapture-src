"""Launch the AR/PBR Texture Lab window for manual inspection."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _log_path() -> Path:
    root = ROOT / "debugCapture"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        root = Path(tempfile.gettempdir())
    return root / "texture_lab_window_launch.log"


def main(argv: list[str]) -> int:
    log = _log_path()
    try:
        image_path = Path(argv[1]).expanduser() if len(argv) > 1 else (
            ROOT
            / "sample_assets"
            / "pbr_blender_scenes"
            / "polyhaven"
            / "materials"
            / "concrete_floor"
            / "textures"
            / "concrete_floor_diff_1k.jpg"
        )
        image_path = image_path.resolve()
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"launch image={image_path} exists={image_path.exists()}\n")
        from PySide6.QtWidgets import QApplication

        from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow
        from app.window_placement import fit_window_to_current_screen, install_global_window_placement

        app = QApplication.instance() or QApplication(sys.argv)
        install_global_window_placement(app)
        window = ArPbrTextureMapLabWindow(image_path)
        fit_window_to_current_screen(window, mark_done=True)
        native_handle = int(window.winId())
        window.show()
        window.raise_()
        window.activateWindow()
        with log.open("a", encoding="utf-8") as fh:
            fh.write(
                "shown "
                f"visible={window.isVisible()} "
                f"winId={native_handle} "
                f"geometry={window.geometry().x()},{window.geometry().y()},"
                f"{window.geometry().width()}x{window.geometry().height()}\n"
            )
        return int(app.exec())
    except Exception:
        with log.open("a", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
            fh.write("\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
