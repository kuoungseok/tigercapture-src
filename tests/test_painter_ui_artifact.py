from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_artifact_resolver_allows_handoff_outputs_and_rejects_executables(
    tmp_path,
) -> None:
    import pytest

    from app.painter_ui_artifact import (
        ARTIFACT_SCHEMA,
        resolve_painter_ui_artifact,
    )

    html = tmp_path / "index.html"
    html.write_text("<title>Review</title>", encoding="utf-8")
    report = resolve_painter_ui_artifact(html)
    assert report["schema"] == ARTIFACT_SCHEMA
    assert report["kind"] == "html"
    assert report["url"].startswith("file:")

    executable = tmp_path / "unsafe.exe"
    executable.write_bytes(b"MZ")
    with pytest.raises(ValueError, match="Unsupported"):
        resolve_painter_ui_artifact(executable)


def test_production_panel_requires_explicit_open_click(tmp_path) -> None:
    _app()
    from app.painter_ui_production_panel import PainterUIProductionPanel

    artifact = tmp_path / "index.html"
    artifact.write_text("<title>Review</title>", encoding="utf-8")
    panel = PainterUIProductionPanel()
    requests: list[str] = []
    panel.artifact_open_requested.connect(requests.append)
    assert not panel.open_artifact_button.isEnabled()
    panel.set_artifact(str(artifact))
    assert panel.open_artifact_button.isEnabled()
    panel.open_artifact_button.click()
    assert requests == [str(artifact)]


def test_artifact_action_validates_but_does_not_launch(tmp_path) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    artifact = tmp_path / "index.html"
    artifact.write_text("<title>Review</title>", encoding="utf-8")
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    result = ActionRegistry(owner=dialog).execute(
        "paint.ui.delivery.artifact.open",
        {"path": str(artifact)},
    ).to_dict()
    assert result["ok"] is True
    assert result["result"]["launched"] is False
    assert result["result"]["launch_policy"] == "explicit_desktop_ui_only"
    dialog.close()
    app.processEvents()


def test_explicit_desktop_open_uses_qdesktopservices(tmp_path, monkeypatch) -> None:
    from app.painter_ui_artifact import open_painter_ui_artifact

    artifact = tmp_path / "index.html"
    artifact.write_text("<title>Review</title>", encoding="utf-8")
    opened: list[str] = []

    def fake_open(url):
        opened.append(url.toLocalFile())
        return True

    monkeypatch.setattr(
        "app.painter_ui_artifact.QDesktopServices.openUrl",
        fake_open,
    )
    report = open_painter_ui_artifact(artifact)
    assert report["launched"] is True
    from pathlib import Path

    assert [Path(value) for value in opened] == [artifact.resolve()]
