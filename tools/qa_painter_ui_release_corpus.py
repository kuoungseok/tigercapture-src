"""Capture the Painter UI release corpus report at desktop and compact sizes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.painter_ui_release_corpus import run_painter_ui_release_corpus
    from app.painter_ui_release_corpus_dialog import (
        PainterUIReleaseCorpusDialog,
    )

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "release_corpus"
    )
    artifacts = output / "artifacts"
    report = run_painter_ui_release_corpus(artifacts)
    results = {}
    for label, size in (("desktop", (650, 500)), ("compact", (420, 520))):
        dialog = PainterUIReleaseCorpusDialog()
        dialog.set_report(report)
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        path = output / f"release_corpus_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        compact = label == "compact"
        results[label] = {
            "ok": bool(
                saved
                and dialog.tree.topLevelItemCount() == 7
                and dialog.tree.isColumnHidden(2) is compact
                and dialog.tree.isColumnHidden(3) is compact
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    qa = {
        "schema": "tigerstudio.painter.ui.release_corpus.qa.v1",
        "ok": bool(report["ok"]) and all(
            row["ok"] for row in results.values()
        ),
        "corpus_report": report,
        "results": results,
    }
    report_path = output / "report_qa.json"
    report_path.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": qa["ok"], "report": str(report_path)}))
    return 0 if qa["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
