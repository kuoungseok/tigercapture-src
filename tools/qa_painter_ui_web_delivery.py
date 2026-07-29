"""Build and capture an executable Painter UI Web package."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sample_color_count(image) -> int:
    colors = set()
    x_step = max(1, image.width() // 32)
    y_step = max(1, image.height() // 24)
    for y in range(0, image.height(), y_step):
        for x in range(0, image.width(), x_step):
            colors.add(image.pixelColor(x, y).rgba())
    return len(colors)


def _capture_page(app, entrypoint: Path, output: Path, size: tuple[int, int]):
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebEngineWidgets import QWebEngineView

    view = QWebEngineView()
    view.resize(*size)
    view.show()
    loaded = {"ok": False}
    loop = QEventLoop()

    def finish(ok: bool) -> None:
        loaded["ok"] = bool(ok)
        QTimer.singleShot(500, loop.quit)

    view.loadFinished.connect(finish)
    view.load(QUrl.fromLocalFile(str(entrypoint)))
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    app.processEvents()
    image = view.grab().toImage()
    saved = image.save(str(output), "PNG")
    result = {
        "ok": bool(
            loaded["ok"]
            and saved
            and not image.isNull()
            and _sample_color_count(image) >= 8
        ),
        "screenshot": str(output),
        "viewport": list(size),
        "sample_color_count": _sample_color_count(image),
    }
    view.close()
    view.deleteLater()
    app.processEvents()
    return result


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-software-rasterizer",
    )
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_web_delivery import package_ui_web

    app = QApplication.instance() or QApplication([])
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "web_delivery"
    )
    package_root = output / "package"
    output.mkdir(parents=True, exist_ok=True)
    document, _template_report = instantiate_ui_template("saas_dashboard")
    package = package_ui_web(document, package_root)
    if not package["ok"]:
        raise RuntimeError(
            "Web package preflight failed: "
            + ", ".join(package["preflight"]["blockers"])
        )
    entrypoint = Path(package["entrypoint"])
    captures = {
        "desktop": _capture_page(
            app,
            entrypoint,
            output / "web_desktop.png",
            (1280, 800),
        ),
        "compact": _capture_page(
            app,
            entrypoint,
            output / "web_compact.png",
            (390, 844),
        ),
    }
    report = {
        "schema": "tigerstudio.painter.ui.web_delivery.qa.v1",
        "ok": all(row["ok"] for row in captures.values()),
        "package": {
            "schema": package["schema"],
            "entrypoint": package["entrypoint"],
            "manifest_path": package["manifest_path"],
            "renderer_counts": package["preflight"]["renderer_counts"],
            "interaction_count": package["preflight"]["prototype"][
                "interaction_count"
            ],
        },
        "captures": captures,
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
