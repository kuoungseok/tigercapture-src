"""Render a linked TSX bundle to a deterministic PNG frame cache."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-web-security --allow-file-access-from-files")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView


def _wait_javascript(page, script: str, timeout_ms: int = 10000):
    loop = QEventLoop()
    state = {"done": False, "value": None}

    def complete(value):
        state.update(done=True, value=value)
        loop.quit()

    page.runJavaScript(script, complete)
    QTimer.singleShot(max(1, int(timeout_ms)), loop.quit)
    loop.exec()
    if not state["done"]:
        raise TimeoutError(f"Timed out running browser script: {script[:80]}")
    return state["value"]


def render(manifest_path: str | Path) -> dict[str, object]:
    manifest_file = Path(manifest_path).expanduser().resolve(strict=True)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    html = Path(manifest["html"]).resolve(strict=True)
    output = Path(manifest["frame_dir"]).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True)
    width = max(1, int(manifest["width"]))
    height = max(1, int(manifest["height"]))
    frame_count = max(1, int(manifest["duration_frames"]))

    app = QApplication.instance() or QApplication(["tiger-remotion-tsx-renderer"])
    view = QWebEngineView()
    view.setAttribute(Qt.WA_DontShowOnScreen, True)
    view.setAttribute(Qt.WA_TranslucentBackground, True)
    view.page().setBackgroundColor(QColor(0, 0, 0, 0))
    view.setFixedSize(width, height)
    loaded = QEventLoop()
    load_state = {"ok": False}

    def on_loaded(ok: bool) -> None:
        load_state["ok"] = bool(ok)
        loaded.quit()

    view.loadFinished.connect(on_loaded)
    view.load(QUrl.fromLocalFile(str(html)))
    view.show()
    QTimer.singleShot(20000, loaded.quit)
    loaded.exec()
    if not load_state["ok"]:
        raise RuntimeError(f"Could not load TSX preview page: {html}")
    if not _wait_javascript(view.page(), "Boolean(globalThis.__tigerReady)"):
        raise RuntimeError("TSX preview did not initialize")

    for frame in range(frame_count):
        _wait_javascript(
            view.page(),
            f"globalThis.__tigerSetFrame({frame}).then(() => true)",
        )
        app.processEvents()
        image = view.grab().toImage()
        target = output / f"frame_{frame:06d}.png"
        if image.isNull() or not image.save(str(target), "PNG"):
            raise RuntimeError(f"Could not save TSX frame {frame}: {target}")
    view.close()
    app.processEvents()
    return {
        "ok": True,
        "frame_dir": str(output),
        "frame_count": frame_count,
        "first_frame": str(output / "frame_000000.png"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.manifest), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
