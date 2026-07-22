from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.motion_designer.plugin_manifest import MOTION_PLUGIN_SCHEMA
from app.motion_designer.plugin_registry import MotionPluginRegistry


def _write_plugin(root: Path, plugin_id: str, *, dependencies: list[dict] | None = None,
                  default_enabled: bool = False) -> None:
    root.mkdir(parents=True)
    (root / "source.json").write_text(json.dumps({"schema": "qa.source.v1"}), encoding="utf-8")
    (root / "plugin.json").write_text(json.dumps({
        "schema": MOTION_PLUGIN_SCHEMA,
        "id": plugin_id,
        "name": plugin_id.title(),
        "version": "1.0.0",
        "vendor": "Tiger QA",
        "api_version": "1.0",
        "capabilities": ["motion.source.v1"],
        "dependencies": {"plugins": dependencies or [], "capabilities": []},
        "default_enabled": default_enabled,
        "contributions": {
            "sources": [{"id": f"{plugin_id}.source", "label": "QA Source", "descriptor": "source.json"}],
        },
    }), encoding="utf-8")


def test_motion_plugin_registry_discovers_inspects_and_persists_enable_state(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _write_plugin(root / "base", "qa.base")
    _write_plugin(root / "child", "qa.child", dependencies=[{"id": "qa.base", "version": "^1.0"}])
    state_path = tmp_path / "state.json"
    registry = MotionPluginRegistry([root], state_path=state_path)

    listing = registry.list()
    assert listing["ok"] is True
    assert [row["id"] for row in listing["plugins"]] == ["qa.base", "qa.child"]
    assert registry.inspect("qa.child")["dependencies"]["plugins"][0]["id"] == "qa.base"

    with pytest.raises(ValueError, match="disabled"):
        registry.set_enabled("qa.child", True)
    assert registry.set_enabled("qa.base", True)["changed"] is True
    assert registry.set_enabled("qa.child", True)["changed"] is True
    assert MotionPluginRegistry([root], state_path=state_path).list()["enabled_count"] == 2

    with pytest.raises(ValueError, match="dependent"):
        registry.set_enabled("qa.base", False)
    registry.set_enabled("qa.child", False)
    registry.set_enabled("qa.base", False)
    assert registry.list()["enabled_count"] == 0


def test_motion_plugin_registry_marks_duplicate_ids_invalid(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _write_plugin(root / "one", "qa.duplicate")
    _write_plugin(root / "two", "qa.duplicate")

    listing = MotionPluginRegistry([root], state_path=tmp_path / "state.json").list()

    assert listing["ok"] is False
    assert listing["duplicate_ids"] == ["qa.duplicate"]
    assert all(not row["valid"] and not row["enabled"] for row in listing["plugins"])
