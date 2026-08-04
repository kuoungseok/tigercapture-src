from __future__ import annotations

import os
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.runtime_package import (
    export_motion_package, inspect_motion_package, load_motion_package,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.toolbar import MotionToolbar


def test_runtime_package_embeds_deduplicates_verifies_and_relinks_assets(tmp_path) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"portable-image-content")
    first = MotionLayer(id="first", layer_type="image", source=SourceRef(kind="image", uri=str(image)))
    second = MotionLayer(id="second", layer_type="image", source=SourceRef(kind="image", uri=str(image)))
    composition = MotionComposition(id="portable", duration_ms=1000, layers=[first, second])
    result = export_motion_package(composition, tmp_path / "portable")
    assert result["asset_count"] == 1
    package = result["path"]
    inspection = inspect_motion_package(package)
    assert inspection["ok"] is True
    restored = load_motion_package(package, tmp_path / "unpacked")
    assert restored.layers[0].source.uri == restored.layers[1].source.uri
    assert restored.layers[0].source.uri != str(image)
    assert open(restored.layers[0].source.uri, "rb").read() == image.read_bytes()


def test_runtime_package_detects_modified_embedded_asset(tmp_path) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"original")
    composition = MotionComposition(
        id="tamper", duration_ms=1000,
        layers=[MotionLayer(layer_type="image", source=SourceRef(kind="image", uri=str(image)))],
    )
    package = export_motion_package(composition, tmp_path / "tamper.tgmotionpkg")["path"]
    replacement = tmp_path / "tampered.tgmotionpkg"
    with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(replacement, "w") as target:
        asset = next(name for name in source.namelist() if name.startswith("assets/"))
        for name in source.namelist():
            target.writestr(name, b"modified" if name == asset else source.read(name))
    package = str(replacement)
    assert inspect_motion_package(package)["ok"] is False


class _Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_runtime_package_actions_export_inspect_and_load(tmp_path) -> None:
    asset = tmp_path / "card.png"
    asset.write_bytes(b"package-action-asset")
    owner = _Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Portable"})
    composition_id = created.result["payload"]["composition"]["id"]
    registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {
            "layer_type": "image",
            "source": {"kind": "image", "uri": str(asset)},
        },
    })

    exported = registry.execute("motion.package.export", {
        "composition_id": composition_id,
        "path": str(tmp_path / "portable"),
    })
    assert exported.ok
    package = exported.result["path"]
    inspected = registry.execute("motion.package.inspect", {"path": package})
    assert inspected.ok and inspected.result["ok"] is True
    loaded = registry.execute("motion.package.load", {
        "path": package,
        "extract_dir": str(tmp_path / "action-unpacked"),
    })
    assert loaded.ok
    loaded_id = loaded.result["composition"]["id"]
    assert loaded_id in owner._motion_compositions


def test_desktop_file_menu_exposes_portable_package_commands() -> None:
    QApplication.instance() or QApplication([])
    toolbar = MotionToolbar()
    assert toolbar.open_package_action.text() == "Open Portable Package"
    assert toolbar.export_package_action.text() == "Export Portable Package"
    toolbar.close()
