from __future__ import annotations

import json
import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _web_document():
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
    )

    document = create_ui_document(390, 844, name="Home")
    home_id = document["active_artboard_id"]
    document, details = add_ui_artboard(
        document,
        name="Details",
        width=390,
        height=844,
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Open details",
        artboard_id=home_id,
        x=24,
        y=680,
        width=342,
        height=52,
        style={"fill": "#4F7CEC", "corner_radius": 8},
        content={"text": "Open details"},
    )
    document, _path = add_ui_object(
        document,
        kind="path",
        name="Accent",
        artboard_id=home_id,
        x=32,
        y=48,
        width=120,
        height=40,
        content={"points": [[0, 20], [60, 0], [120, 20]]},
    )
    document, _interaction = add_ui_interaction(
        document,
        source_object_id=button["id"],
        trigger="click",
        action="navigate",
        target_artboard_id=details["id"],
    )
    return document


def test_web_preflight_maps_renderers_and_prototype() -> None:
    from app.painter_ui_web_delivery import (
        WEB_PREFLIGHT_SCHEMA,
        preflight_ui_web,
    )

    report = preflight_ui_web(_web_document())

    assert report["schema"] == WEB_PREFLIGHT_SCHEMA
    assert report["ok"] is True
    assert report["renderer_counts"]["dom_css"] == 1
    assert report["renderer_counts"]["svg"] == 1
    assert report["prototype"]["interaction_count"] == 1
    assert report["responsive_policy"] == {
        "viewport_meta": True,
        "fit_active_artboard": True,
        "max_upscale": 1.0,
        "mobile_breakpoint_px": 600,
    }


def test_web_package_is_executable_responsive_and_hashed(
    tmp_path: Path,
) -> None:
    from app.painter_ui_web_delivery import (
        WEB_PACKAGE_SCHEMA,
        package_ui_web,
    )

    report = package_ui_web(_web_document(), tmp_path / "web")

    assert report["ok"] is True
    root = Path(report["output_dir"])
    expected = {
        "index.html",
        "design_document.json",
        "web.css",
        "web-runtime.js",
        "web_preflight.json",
        "manifest.json",
    }
    assert expected.issubset({path.name for path in root.iterdir()})
    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "web.css").read_text(encoding="utf-8")
    runtime = (root / "web-runtime.js").read_text(encoding="utf-8")
    assert 'href="web.css"' in html
    assert 'src="web-runtime.js"' in html
    assert "function fire(" in html
    assert "addEventListener" in html
    assert "--tiger-web-scale" in runtime
    assert '"resize"' in runtime
    assert "chooseResponsiveArtboard" in runtime
    assert '"mobile"' in runtime and '"desktop"' in runtime
    assert "font-size:" in css
    assert '[id="artboard-' in css
    manifest = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == WEB_PACKAGE_SCHEMA
    assert manifest["entrypoint"] == "index.html"
    assert manifest["hosting"] == "not_included"
    assert all(
        len(row["sha256"]) == 64 and row["bytes"] > 0
        for row in manifest["artifacts"]
    )


def test_web_preflight_blocks_broken_interaction_reference() -> None:
    from app.painter_ui_web_delivery import preflight_ui_web

    document = _web_document()
    document["interactions"][0]["target_artboard_id"] = "missing-artboard"

    report = preflight_ui_web(document)

    assert report["ok"] is False
    assert any("missing_interaction_artboard" in row for row in report["blockers"])


def test_web_delivery_panel_exposes_compact_requests(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _app()
    from PySide6.QtWidgets import QFileDialog

    from app.painter_ui_production_panel import PainterUIProductionPanel

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(tmp_path),
    )
    panel = PainterUIProductionPanel()
    preflight_requests: list[bool] = []
    package_requests: list[str] = []
    panel.web_preflight_requested.connect(
        lambda: preflight_requests.append(True)
    )
    panel.web_package_requested.connect(package_requests.append)

    panel.web_preflight_button.click()
    panel.web_package_button.click()

    assert preflight_requests == [True]
    assert package_requests == [str(tmp_path)]
    assert panel.web_preflight_button.text()
    assert panel.web_package_button.text()
    panel.close()


def test_web_actions_are_non_mutating_and_write_package(
    tmp_path: Path,
) -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _web_document()
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.ui.web.preflight",
        "paint.ui.web.package",
    }.issubset(action_ids)
    before_revision = dialog._painter_ui_document["revision"]

    preflight = registry.execute("paint.ui.web.preflight", {}).to_dict()
    packaged = registry.execute(
        "paint.ui.web.package",
        {"output_dir": str(tmp_path / "action-web")},
    ).to_dict()

    assert preflight["ok"] is True
    assert preflight["changed"] is False
    assert packaged["ok"] is True
    assert packaged["changed"] is False
    assert Path(packaged["result"]["entrypoint"]).is_file()
    assert dialog._painter_ui_document["revision"] == before_revision
    dialog.close()
