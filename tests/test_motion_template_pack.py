from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.plugin_manifest import MOTION_PLUGIN_SCHEMA
from app.motion_designer.schema import MotionComposition
from app.motion_designer.template_pack import (
    MOTION_TEMPLATE_PACK_SCHEMA,
    install_motion_template_pack,
    validate_motion_template_pack,
)


def _write_pack(root: Path, *, pack_id: str = "qa.titles", include_executable: bool = False) -> Path:
    root.mkdir(parents=True)
    compositions = root / "compositions"
    compositions.mkdir()
    composition = MotionComposition(id="qa_template_comp", name="QA Template")
    (compositions / "title.json").write_text(
        json.dumps(composition.to_dict()), encoding="utf-8"
    )
    if include_executable:
        (root / "run.py").write_text("raise RuntimeError('must never run')", encoding="utf-8")
    (root / "template-pack.json").write_text(json.dumps({
        "schema": MOTION_TEMPLATE_PACK_SCHEMA,
        "id": pack_id,
        "name": "QA Titles",
        "version": "1.0.0",
        "vendor": "Tiger QA",
        "license": "CC0-1.0",
        "templates": [{
            "id": "qa.title",
            "name": "QA Title",
            "category": "Titles",
            "variants": ["16:9", "9:16"],
            "composition": "compositions/title.json",
            "published_controls": [{
                "id": "headline", "label": "Headline", "value_type": "string", "default": "QA",
            }],
        }],
    }), encoding="utf-8")
    return root


def _write_plugin(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "source.json").write_text(json.dumps({"schema": "qa.source.v1"}), encoding="utf-8")
    manifest = root / "plugin.json"
    manifest.write_text(json.dumps({
        "schema": MOTION_PLUGIN_SCHEMA,
        "id": "qa.action",
        "name": "QA Action Plugin",
        "version": "1.0.0",
        "vendor": "Tiger QA",
        "api_version": "1.0",
        "capabilities": ["motion.source.v1"],
        "contributions": {
            "sources": [{"id": "qa.action.source", "label": "QA", "descriptor": "source.json"}],
        },
    }), encoding="utf-8")
    return manifest


def test_motion_template_pack_validates_and_installs_atomically(tmp_path: Path) -> None:
    source = _write_pack(tmp_path / "source")

    report = validate_motion_template_pack(source)
    installed = install_motion_template_pack(source, destination_root=tmp_path / "installed")

    assert report["ok"] is True
    assert report["pack"]["templates"][0]["composition_validation"]["ok"] is True
    assert report["runtime_loaded"] is False
    assert Path(installed["installed_path"], "template-pack.json").is_file()
    assert installed["restart_required"] is True
    with pytest.raises(FileExistsError):
        install_motion_template_pack(source, destination_root=tmp_path / "installed")
    replaced = install_motion_template_pack(
        source, destination_root=tmp_path / "installed", replace=True
    )
    assert replaced["replaced"] is True


def test_motion_template_pack_rejects_executable_content_and_zip_escape(tmp_path: Path) -> None:
    unsafe_directory = _write_pack(tmp_path / "unsafe", include_executable=True)
    assert validate_motion_template_pack(unsafe_directory)["ok"] is False

    archive_path = tmp_path / "escape.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", "escape")
        archive.writestr("template-pack.json", "{}")
    report = validate_motion_template_pack(archive_path)
    assert report["ok"] is False
    assert any("Unsafe template-pack archive path" in error for error in report["errors"])
    assert not (tmp_path / "outside.txt").exists()


def test_motion_plugin_actions_are_ownerless_and_template_install_requires_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    source = _write_pack(tmp_path / "source")
    registry = ActionRegistry()
    required_ids = {
        "motion.plugin.list", "motion.plugin.inspect", "motion.plugin.enable",
        "motion.plugin.disable", "motion.plugin.validate",
        "motion.template_pack.install", "motion.template_pack.validate",
    }
    schemas = {row["id"]: row for row in registry.list_actions() if row["id"] in required_ids}

    assert set(schemas) == required_ids
    assert all(not row["requires_owner"] for row in schemas.values())
    assert schemas["motion.template_pack.install"]["requires_review"] is True
    assert "destination_root" not in schemas["motion.template_pack.install"]["params_schema"]["properties"]
    for action_id in ("motion.plugin.list", "motion.plugin.inspect", "motion.plugin.enable", "motion.plugin.disable"):
        assert "state_path" not in schemas[action_id]["params_schema"]["properties"]
    assert registry.execute("motion.template_pack.validate", {"path": str(source)}).result["ok"] is True

    params = {"path": str(source)}
    blocked = registry.execute("motion.template_pack.install", params)
    assert blocked.ok is False
    assert "confirm_destructive" in blocked.error
    installed = registry.execute(
        "motion.template_pack.install", params, confirm_destructive=True
    )
    assert installed.ok is True
    assert Path(installed.result["installed_path"]).is_dir()


def test_motion_plugin_actions_execute_discovery_validation_and_enable_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_app_data = tmp_path / "local-app-data"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    plugin_root = tmp_path / "plugins"
    manifest = _write_plugin(plugin_root / "qa-action")
    state_path = local_app_data / "TigerCapture" / "MotionDesigner" / "plugin_state.json"
    context = {"plugin_roots": [str(plugin_root)]}
    registry = ActionRegistry()

    validated = registry.execute("motion.plugin.validate", {"path": str(manifest)})
    listed = registry.execute("motion.plugin.list", context)
    inspected = registry.execute("motion.plugin.inspect", {"plugin_id": "qa.action", **context})
    enabled = registry.execute("motion.plugin.enable", {"plugin_id": "qa.action", **context})
    disabled = registry.execute("motion.plugin.disable", {"plugin_id": "qa.action", **context})

    assert validated.ok and validated.result["ok"] is True
    assert listed.ok and listed.result["plugins"][0]["id"] == "qa.action"
    assert inspected.ok and inspected.result["runtime_loaded"] is False
    assert enabled.ok and enabled.result["enabled"] is True
    assert disabled.ok and disabled.result["enabled"] is False
    assert state_path.is_file()
