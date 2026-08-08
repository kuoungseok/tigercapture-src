from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.actions.registry import ActionRegistry
from app.painter_ui_figma_plugin_registry import PainterFigmaPluginRegistry


def _app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _write_plugin(root: Path, plugin_id: str) -> Path:
    root.mkdir(parents=True)
    marker = root / "executed.txt"
    (root / "code.js").write_text(
        f"require('fs').writeFileSync({str(marker)!r}, 'bad');\n",
        encoding="utf-8",
    )
    manifest = {
        "name": plugin_id,
        "id": plugin_id,
        "api": "1.0.0",
        "editorType": ["figma"],
        "main": "code.js",
        "documentAccess": "dynamic-page",
        "networkAccess": {"allowedDomains": ["none"]},
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_registry_installs_lists_inspects_and_removes_without_execution(tmp_path: Path) -> None:
    source = tmp_path / "source"
    manifest = _write_plugin(source, "qa.plugin")
    install_root = tmp_path / "installed"
    registry = PainterFigmaPluginRegistry([install_root], install_root=install_root)

    installed = registry.install(manifest)
    assert installed["ok"] is True
    assert installed["runtime_ready"] is False
    assert not (source / "executed.txt").exists()

    listing = registry.list()
    assert listing["count"] == 1
    assert listing["runtime_ready_count"] == 0
    assert listing["plugins"][0]["id"] == "qa.plugin"
    assert registry.inspect("qa.plugin")["runtime_policy"] == "metadata_only_no_code_execution"
    assert not (Path(installed["install_path"]) / "executed.txt").exists()

    removed = registry.remove("qa.plugin")
    assert removed["ok"] is True
    assert not Path(removed["removed_path"]).exists()
    assert registry.list()["count"] == 0


def test_registry_rejects_duplicate_ids_and_second_install(tmp_path: Path) -> None:
    roots = tmp_path / "roots"
    one = _write_plugin(roots / "one", "qa.duplicate")
    _write_plugin(roots / "two", "qa.duplicate")
    registry = PainterFigmaPluginRegistry([roots], install_root=tmp_path / "installed")

    listing = registry.list()
    assert listing["ok"] is False
    assert listing["duplicate_ids"] == ["qa.duplicate"]
    assert all(not item["valid"] for item in listing["plugins"])

    install_registry = PainterFigmaPluginRegistry(
        [tmp_path / "installed"], install_root=tmp_path / "installed"
    )
    install_registry.install(one)
    with pytest.raises(ValueError, match="already installed"):
        install_registry.install(one)


def test_registry_does_not_remove_read_only_discovery_package(tmp_path: Path) -> None:
    bundled = tmp_path / "bundled"
    _write_plugin(bundled / "plugin", "qa.bundled")
    registry = PainterFigmaPluginRegistry([bundled], install_root=tmp_path / "installed")

    with pytest.raises(ValueError, match="writable user root"):
        registry.remove("qa.bundled")
    assert (bundled / "plugin" / "manifest.json").is_file()


def test_figma_plugin_actions_are_ownerless_reviewed_and_metadata_only(tmp_path: Path) -> None:
    source = _write_plugin(tmp_path / "source", "qa.action")
    installed_root = tmp_path / "installed"
    context = {
        "plugin_roots": [str(installed_root)],
        "install_root": str(installed_root),
    }
    registry = ActionRegistry()
    action_ids = {
        "paint.ui.figma_plugin.validate",
        "paint.ui.figma_plugin.list",
        "paint.ui.figma_plugin.inspect",
        "paint.ui.figma_plugin.install",
        "paint.ui.figma_plugin.remove",
        "paint.ui.figma_plugin.run",
    }
    schemas = {row["id"]: row for row in registry.list_actions() if row["id"] in action_ids}

    assert set(schemas) == action_ids
    assert all(
        not schemas[action_id]["requires_owner"]
        for action_id in action_ids - {"paint.ui.figma_plugin.run"}
    )
    assert schemas["paint.ui.figma_plugin.run"]["requires_owner"] is True
    assert schemas["paint.ui.figma_plugin.install"]["requires_review"] is True
    assert schemas["paint.ui.figma_plugin.remove"]["destructive"] is True
    validated = registry.execute(
        "paint.ui.figma_plugin.validate", {"path": str(source)}
    )
    assert validated.ok and validated.result["runtime_ready"] is False

    blocked = registry.execute(
        "paint.ui.figma_plugin.install", {"path": str(source), **context}
    )
    assert blocked.ok is False
    installed = registry.execute(
        "paint.ui.figma_plugin.install",
        {"path": str(source), **context},
        confirm_destructive=True,
    )
    assert installed.ok and installed.result["runtime_ready"] is False
    listed = registry.execute("paint.ui.figma_plugin.list", context)
    assert listed.ok and listed.result["plugins"][0]["id"] == "qa.action"
    removed = registry.execute(
        "paint.ui.figma_plugin.remove",
        {"plugin_id": "qa.action", **context},
        confirm_destructive=True,
    )
    assert removed.ok and not Path(removed.result["removed_path"]).exists()


def test_plugin_manager_dialog_exposes_fp2_limited_run_control(tmp_path: Path) -> None:
    app = _app()
    from PySide6.QtWidgets import QLabel, QPushButton

    source = _write_plugin(tmp_path / "source", "qa.dialog")
    (source.parent / "code.js").write_text(
        "const n=figma.createRectangle();n.name='Dialog';", encoding="utf-8"
    )
    installed_root = tmp_path / "installed"
    registry = PainterFigmaPluginRegistry([installed_root], install_root=installed_root)
    registry.install(source)
    from app.painter_ui_figma_plugin_manager_dialog import (
        PainterFigmaPluginManagerDialog,
    )

    dialog = PainterFigmaPluginManagerDialog(registry=registry)
    app.processEvents()

    assert dialog.plugin_list.count() == 1
    assert dialog.current_plugin_id() == "qa.dialog"
    policy = dialog.findChild(QLabel, "PainterFigmaPluginRuntimePolicy")
    assert policy is not None
    assert "별도 프로세스에서 실행" in policy.text()
    assert "실행: FP2 기본 API 샌드박스" in dialog.details.toPlainText()
    run_button = dialog.findChild(QPushButton, "PainterFigmaPluginRunButton")
    assert run_button is not None and run_button.isEnabled()
    status = dialog.findChild(QLabel, "PainterFigmaPluginRuntimeStatus")
    assert status is not None
    assert status.property("runtimeState") == "ready"
    assert status.text() == "실행 준비됨"
    dialog.close()
    dialog.deleteLater()


def test_registry_and_manager_route_message_only_ui_plugin_to_fp3(tmp_path: Path) -> None:
    app = _app()
    from PySide6.QtWidgets import QPushButton

    source = _write_plugin(tmp_path / "source", "qa.ui.dialog")
    (source.parent / "code.js").write_text(
        "figma.showUI(__html__,{width:320,height:180,themeColors:true});"
        "figma.ui.onmessage=msg=>figma.ui.postMessage({type:'echo',value:msg.value});",
        encoding="utf-8",
    )
    (source.parent / "ui.html").write_text("<button>Send</button>", encoding="utf-8")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["ui"] = "ui.html"
    source.write_text(json.dumps(manifest), encoding="utf-8")
    installed_root = tmp_path / "installed"
    registry = PainterFigmaPluginRegistry([installed_root], install_root=installed_root)
    registry.install(source)

    listing = registry.list()
    row = listing["plugins"][0]
    assert row["runtime_ready"] is False
    assert row["ui_runtime_ready"] is True
    assert row["compatibility"] == "fp3_limited_ui"
    assert listing["ui_runtime_ready_count"] == 1

    from app.painter_ui_figma_plugin_manager_dialog import PainterFigmaPluginManagerDialog

    dialog = PainterFigmaPluginManagerDialog(registry=registry)
    app.processEvents()
    headless = dialog.findChild(QPushButton, "PainterFigmaPluginRunButton")
    ui_run = dialog.findChild(QPushButton, "PainterFigmaPluginUIRunButton")
    assert headless is not None and not headless.isEnabled()
    assert ui_run is not None and ui_run.isEnabled()
    assert "실행: FP3 제한 UI 브리지" in dialog.details.toPlainText()
    assert dialog.runtime_status.text() == "UI 실행 준비됨"
    dialog.close()
    dialog.deleteLater()


def test_plugin_manager_network_approval_is_explicit_and_per_run(
    tmp_path: Path, monkeypatch
) -> None:
    app = _app()
    from PySide6.QtWidgets import QMessageBox
    from app.painter_ui_figma_plugin_manager_dialog import PainterFigmaPluginManagerDialog

    registry = PainterFigmaPluginRegistry([tmp_path / "empty"], install_root=tmp_path / "installed")
    dialog = PainterFigmaPluginManagerDialog(registry=registry)
    plugin = {
        "allowed_domains": ["https://api.example.com"],
        "network_reasoning": "동기화 API",
    }
    calls = []

    def reject(*args, **kwargs):
        calls.append((args, kwargs))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", reject)
    assert dialog._approve_network_domains(plugin) is None
    assert len(calls) == 1

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    assert dialog._approve_network_domains(plugin) == ("https://api.example.com",)
    assert dialog._approve_network_domains({"allowed_domains": ["none"]}) == ()
    app.processEvents()
    dialog.close()
    dialog.deleteLater()
