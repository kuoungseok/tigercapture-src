from __future__ import annotations

import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _library_document(resource_path: Path):
    from app.painter_ui_document import (
        add_ui_component,
        add_ui_object,
        add_ui_token,
        create_ui_document,
    )
    from app.painter_ui_styles import add_ui_style

    document = create_ui_document()
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Button Family",
    )
    document, _child = add_ui_object(
        document,
        kind="image",
        name="Button Icon",
        parent_id=root["id"],
        content={"source_path": str(resource_path)},
    )
    document, _component = add_ui_component(
        document,
        name="Primary Button",
        root_object_id=root["id"],
    )
    document, token = add_ui_token(
        document,
        name="Brand",
        kind="color",
        token_value="#3377CC",
        scope=["style.fill"],
    )
    document, _style = add_ui_style(
        document,
        name="Brand Fill",
        kind="color",
        properties={"fill": "#3377CC"},
        token_bindings={"style.fill": token["id"]},
    )
    return document


def test_ui_library_package_round_trip_and_resource_hash(tmp_path: Path) -> None:
    from app.painter_ui_library_store import (
        export_ui_library_package,
        read_ui_library_package,
    )

    resource = tmp_path / "icon.png"
    resource.write_bytes(b"durable-image-resource")
    document = _library_document(resource)
    exported = export_ui_library_package(
        document,
        tmp_path / "studio-library",
        library_id="Studio Core",
        name="Studio Core",
    )
    assert exported["path"].endswith(".tsuilib")
    package = read_ui_library_package(exported["path"])
    assert package["manifest"]["id"] == "studio-core"
    assert package["manifest"]["counts"] == {
        "components": 1,
        "styles": 1,
        "variable_collections": 1,
        "tokens": 1,
        "resources": 1,
    }
    assert len(package["payload"]["component_objects"]) == 2
    assert package["payload"]["resources"][0]["name"] == "icon.png"


def test_ui_library_update_defer_apply_and_rollback(tmp_path: Path) -> None:
    from app.painter_ui_library_store import (
        compare_ui_library_update,
        defer_ui_library_update,
        export_ui_library_package,
        inspect_ui_library_store,
        install_ui_library_package,
        rollback_ui_library,
    )
    from app.painter_ui_styles import add_ui_style

    resource = tmp_path / "icon.png"
    resource.write_bytes(b"resource")
    document = _library_document(resource)
    v1 = export_ui_library_package(
        document,
        tmp_path / "v1.tsuilib",
        library_id="studio-core",
        name="Studio Core",
        version=1,
    )
    store = tmp_path / "store"
    install_ui_library_package(v1["path"], store_root=store)

    document, _style = add_ui_style(
        document,
        name="Soft Shadow",
        kind="effect",
        properties={"shadow": {"blur": 12}},
    )
    v2 = export_ui_library_package(
        document,
        tmp_path / "v2.tsuilib",
        library_id="studio-core",
        name="Studio Core",
        version=2,
    )
    review = compare_ui_library_update(v2["path"], store_root=store)
    assert review["update_available"] is True
    assert review["counts"]["current"]["styles"] == 1
    assert review["counts"]["candidate"]["styles"] == 2

    state = defer_ui_library_update("studio-core", 2, store_root=store)
    assert state["deferred_versions"]["studio-core"] == 2
    install_ui_library_package(v2["path"], store_root=store)
    report = inspect_ui_library_store(store_root=store)
    assert report["active_versions"]["studio-core"] == 2
    assert report["previous_versions"]["studio-core"] == 1
    assert report["deferred_versions"] == {}

    rolled_back = rollback_ui_library("studio-core", store_root=store)
    assert rolled_back["active_version"] == 1
    assert (
        inspect_ui_library_store(store_root=store)["active_versions"][
            "studio-core"
        ]
        == 1
    )


def test_ui_library_actions_export_install_and_inspect(tmp_path: Path) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    package_path = tmp_path / "action-library.tsuilib"
    exported = registry.execute(
        "paint.ui.library.package.export",
        {
            "path": str(package_path),
            "library_id": "action-library",
            "name": "Action Library",
        },
    ).to_dict()
    assert exported["ok"] is True
    installed = registry.execute(
        "paint.ui.library.package.install",
        {
            "path": exported["result"]["path"],
            "store_root": str(tmp_path / "store"),
        },
    ).to_dict()
    assert installed["ok"] is True
    inspected = registry.execute(
        "paint.ui.library.store.inspect",
        {"store_root": str(tmp_path / "store")},
    ).to_dict()
    assert inspected["ok"] is True
    assert inspected["result"]["library_count"] == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_library_panel_shows_versions_and_emits_review_choices(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_library_panel import PainterUILibraryPanel
    from app.painter_ui_library_store import (
        export_ui_library_package,
        install_ui_library_package,
    )

    store = tmp_path / "store"
    document = create_ui_document()
    v1 = export_ui_library_package(
        document,
        tmp_path / "panel-v1.tsuilib",
        library_id="panel-kit",
        name="Panel Kit",
        version=1,
    )
    v2 = export_ui_library_package(
        document,
        tmp_path / "panel-v2.tsuilib",
        library_id="panel-kit",
        name="Panel Kit",
        version=2,
    )
    install_ui_library_package(v1["path"], store_root=store)
    panel = PainterUILibraryPanel(store_root=store)
    panel.set_document(document)
    assert panel.tree.topLevelItemCount() == 1
    assert panel.tree.topLevelItem(0).childCount() == 1

    report = panel.set_update_candidate(v2["path"])
    assert report["update_available"] is True
    accepted: list[str] = []
    deferred: list[tuple[str, int]] = []
    panel.update_apply_requested.connect(accepted.append)
    panel.update_defer_requested.connect(
        lambda library_id, version: deferred.append((library_id, version))
    )
    panel.accept_button.click()
    panel.defer_button.click()
    app.processEvents()
    assert accepted == [v2["path"]]
    assert deferred == [("panel-kit", 2)]
    panel.close()
    panel.deleteLater()
    app.processEvents()
