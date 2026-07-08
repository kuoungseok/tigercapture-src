from __future__ import annotations

import os


def test_ppt_video_export_worker_runs_in_background(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, SlideSpec
    from app.pptgen.ui.video_export_worker import PptVideoExportWorker

    app = QApplication.instance() or QApplication([])
    assert app is not None

    deck = DeckSpec(id="deck", slides=[SlideSpec(id="slide-001", title="Worker", duration_ms=500)])
    out = tmp_path / "worker.mp4"
    worker = PptVideoExportWorker(deck, out, fps=2, size=(160, 90))
    result: dict[str, object] = {}
    errors: list[str] = []
    loop = QEventLoop()

    worker.resultReady.connect(lambda payload: result.update(dict(payload)))
    worker.failed.connect(lambda message: errors.append(str(message)))
    worker.finished.connect(loop.quit)
    worker.start()
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    worker.wait(5000)

    assert errors == []
    assert result["ok"] is True
    assert out.is_file()
    assert int(result["frames_written"]) >= 1
