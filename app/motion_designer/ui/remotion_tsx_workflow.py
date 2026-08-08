"""UI workflow for explicitly trusted, linked Remotion-style TSX sources."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QProgressDialog, QWidget

from app.motion_designer.remotion_tsx import (
    DEFAULT_REMOTION_TSX_DURATION_MS,
    create_remotion_tsx_layer,
    inspect_remotion_tsx,
    install_remotion_tsx_runtime,
    prepare_remotion_tsx_frames,
    remotion_tsx_runtime_status,
)


def choose_and_prepare_remotion_tsx(
    parent: QWidget,
    *,
    width: int,
    height: int,
    fps: float,
    duration_ms: int,
):
    path, _selected = QFileDialog.getOpenFileName(
        parent,
        "Open linked Remotion TSX",
        "",
        "Remotion React Source (*.tsx *.jsx)",
    )
    if not path:
        return None
    linked_duration_ms = min(
        max(1, int(duration_ms)),
        DEFAULT_REMOTION_TSX_DURATION_MS,
    )
    inspection = inspect_remotion_tsx(path)
    if not inspection.ok:
        detail = "\n".join(inspection.warnings) or "Unsupported TSX source contract."
        QMessageBox.warning(parent, "TSX compatibility", detail)
        return None
    trust = QMessageBox.question(
        parent,
        "Trust TSX source",
        "TSX is executable React source. Tiger will keep the original file unchanged "
        "and execute a reviewed compatibility subset to build the preview cache.\n\n"
        f"Source: {inspection.path}\n"
        f"Imports: {', '.join(inspection.imports) or 'none'}\n\n"
        "Trust and load this source?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if trust != QMessageBox.Yes:
        return None
    status = remotion_tsx_runtime_status()
    if not status["ready"]:
        install = QMessageBox.question(
            parent,
            "Install TSX preview support",
            "Tiger needs its React/esbuild compatibility runtime. Remotion itself is not "
            "installed. Install the local runtime now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if install != QMessageBox.Yes:
            return create_remotion_tsx_layer(
                path, width=width, height=height, fps=fps,
                duration_ms=linked_duration_ms,
            )
        progress = QProgressDialog(
            "Installing TSX preview runtime...", "", 0, 0, parent,
        )
        progress.setCancelButton(None)
        progress.setWindowTitle("Remotion TSX")
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
        try:
            install_remotion_tsx_runtime()
        except Exception as error:
            progress.close()
            QMessageBox.critical(parent, "TSX runtime installation failed", str(error))
            return None
        progress.close()
    progress = QProgressDialog(
        "Reading TSX and preparing linked preview frames...", "", 0, 0, parent,
    )
    progress.setCancelButton(None)
    progress.setWindowTitle("Remotion TSX")
    progress.setMinimumDuration(0)
    progress.show()
    QApplication.processEvents()
    try:
        prepared = prepare_remotion_tsx_frames(
            path, width=width, height=height, fps=fps,
            duration_ms=linked_duration_ms, trusted=True,
        )
    except Exception as error:
        progress.close()
        QMessageBox.critical(parent, "TSX preview preparation failed", str(error))
        return None
    progress.close()
    return create_remotion_tsx_layer(
        path, width=width, height=height, fps=fps,
        duration_ms=linked_duration_ms, name=Path(path).stem, prepared=prepared,
    )


__all__ = ["choose_and_prepare_remotion_tsx"]
