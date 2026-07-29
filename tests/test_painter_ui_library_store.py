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
    assert package["payload"]["resources"][0]["bindings"] == [
        {
            "object_id": "ui-object-2",
            "content_key": "source_path",
        }
    ]


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


def test_installed_library_component_imports_dependencies_and_reuses_definition(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import create_ui_document, validate_ui_document
    from app.painter_ui_library_import import insert_ui_library_component
    from app.painter_ui_library_store import (
        export_ui_library_package,
        install_ui_library_package,
        read_ui_library_package,
    )

    resource = tmp_path / "icon.png"
    resource.write_bytes(b"durable-library-icon")
    source = _library_document(resource)
    exported = export_ui_library_package(
        source,
        tmp_path / "insertable.tsuilib",
        library_id="insertable",
        name="Insertable",
    )
    store = tmp_path / "store"
    install_ui_library_package(exported["path"], store_root=store)
    source_component_id = read_ui_library_package(exported["path"])[
        "payload"
    ]["components"][0]["id"]

    document, first = insert_ui_library_component(
        create_ui_document(800, 600),
        library_id="insertable",
        component_id=source_component_id,
        store_root=store,
        x=120,
        y=80,
    )
    instance_root = next(
        row
        for row in document["objects"]
        if row["id"] == document["selection"]["object_id"]
    )
    instance_image = next(
        row
        for row in document["objects"]
        if row["parent_id"] == instance_root["id"]
    )
    assert validate_ui_document(document)["ok"] is True
    assert instance_root["component_role"] == "instance"
    assert (instance_root["x"], instance_root["y"]) == (120.0, 80.0)
    assert Path(instance_image["content"]["source_path"]).is_file()
    assert first["imported"]["components"] == 1
    assert first["imported"]["tokens"] == 1

    document, second = insert_ui_library_component(
        document,
        library_id="insertable",
        component_id=source_component_id,
        store_root=store,
        x=240,
        y=160,
    )
    assert second["imported"]["components"] == 0
    assert len(document["components"]) == 1
    assert validate_ui_document(document)["ok"] is True


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

    resource = tmp_path / "action-icon.png"
    resource.write_bytes(b"action-library-icon")
    source_package = tmp_path / "source-components.tsuilib"
    from app.painter_ui_library_store import export_ui_library_package

    source_export = export_ui_library_package(
        _library_document(resource),
        source_package,
        library_id="source-components",
        name="Source Components",
    )
    installed_source = registry.execute(
        "paint.ui.library.package.install",
        {
            "path": source_export["path"],
            "store_root": str(tmp_path / "store"),
        },
    ).to_dict()
    assert installed_source["ok"] is True
    inserted = registry.execute(
        "paint.ui.library.component.insert",
        {
            "library_id": "source-components",
            "component_id": "ui-component-1",
            "store_root": str(tmp_path / "store"),
            "x": 96,
            "y": 72,
        },
    ).to_dict()
    assert inserted["ok"] is True
    assert inserted["result"]["library_component"]["instance"][
        "component_id"
    ]
    assert dialog._painter_ui_document["selection"]["object_id"]
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
    resource = tmp_path / "panel-icon.png"
    resource.write_bytes(b"panel-library-icon")
    document = _library_document(resource)
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
    version_item = panel.tree.topLevelItem(0).child(0)
    assert version_item.childCount() == 1
    component_item = version_item.child(0)
    inserted: list[tuple[str, str, int]] = []
    panel.component_insert_requested.connect(
        lambda library_id, component_id, version: inserted.append(
            (library_id, component_id, version)
        )
    )
    panel.tree.setCurrentItem(component_item)
    panel.insert_component_button.click()
    assert inserted == [("panel-kit", "ui-component-1", 1)]
    panel.resize(280, 460)
    panel.show()
    app.processEvents()
    assert panel.tree.horizontalScrollBar().maximum() == 0

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
