from __future__ import annotations

import json
from pathlib import Path

from app.motion_designer.plugin_manifest import (
    MOTION_PLUGIN_API_VERSION,
    MOTION_PLUGIN_SCHEMA,
    validate_motion_plugin_manifest,
)


def _write_plugin(root: Path, *, descriptor: str = "descriptors/source.json",
                  api_version: str = MOTION_PLUGIN_API_VERSION) -> Path:
    root.mkdir(parents=True)
    descriptor_path = root / descriptor
    if ".." not in Path(descriptor).parts:
        descriptor_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor_path.write_text(json.dumps({"schema": "example.source.v1"}), encoding="utf-8")
    manifest = {
        "schema": MOTION_PLUGIN_SCHEMA,
        "id": "example.source",
        "name": "Example Source",
        "version": "1.2.0",
        "vendor": "Tiger QA",
        "api_version": api_version,
        "capabilities": ["motion.source.v1"],
        "contributions": {
            "sources": [{"id": "example.source.reader", "label": "Reader", "descriptor": descriptor}],
        },
    }
    path = root / "plugin.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_valid_motion_plugin_manifest_is_declarative_and_compatible(tmp_path: Path) -> None:
    path = _write_plugin(tmp_path / "plugin")

    report = validate_motion_plugin_manifest(path)

    assert report["ok"] is True
    assert report["plugin"]["id"] == "example.source"
    assert report["plugin"]["contributions"]["sources"][0]["kind"] == "sources"
    assert report["runtime_loaded"] is False
    assert report["resource_paths"] == [str((path.parent / "descriptors/source.json").resolve())]


def test_motion_plugin_manifest_rejects_api_mismatch_and_path_escape(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path / "plugin",
        descriptor="../outside.json",
        api_version="2.0",
    )

    report = validate_motion_plugin_manifest(path)

    assert report["ok"] is False
    assert any("incompatible" in error for error in report["errors"])
    assert any("unsafe descriptor path" in error for error in report["errors"])


def test_motion_plugin_manifest_rejects_executable_descriptor(tmp_path: Path) -> None:
    path = _write_plugin(tmp_path / "plugin", descriptor="source.py")

    report = validate_motion_plugin_manifest(path)

    assert report["ok"] is False
    assert any("declarative JSON descriptor" in error for error in report["errors"])
