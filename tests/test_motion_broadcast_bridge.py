from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.broadcast_bridge import (
    BROADCAST_CACHE_SCHEMA,
    apply_live_controls,
    broadcast_preflight,
    estimate_broadcast_cost,
    render_stinger_alpha_cache,
    stinger_alpha_plan,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.templates import instantiate_template
from app.motion_designer.templates import apply_template_to_composition


def test_realtime_template_is_ready_without_cache() -> None:
    composition = instantiate_template("clean_lower_third")
    report = broadcast_preflight(composition)
    assert report["ok"] is True
    assert report["grade"] == "realtime"
    assert report["program_output"]["direct_playback"] is True
    assert report["program_output"]["performance_source_allowed"] is False


def test_cached_template_is_blocked_until_revision_bound_alpha_cache_exists(tmp_path: Path) -> None:
    composition = instantiate_template("stream_stinger")
    blocked = broadcast_preflight(composition)
    assert blocked["ok"] is False
    assert blocked["grade"] == "cached"
    assert any("alpha-cache" in item for item in blocked["blockers"])

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    manifest = {
        "schema": BROADCAST_CACHE_SCHEMA,
        "ready": True,
        "composition_revision": composition.revision,
        "alpha": True,
        "premultiplied_alpha": True,
        "frame_count": 2,
        "path": str(cache_dir),
    }
    ready = broadcast_preflight(composition, cache_manifest=manifest)
    assert ready["ok"] is True
    assert ready["program_output"]["cached_playback"] is True


def test_live_controls_use_stable_ids_and_invalidate_old_cache() -> None:
    composition = instantiate_template("clean_lower_third")
    composition.metadata["broadcast_cache"] = {"ready": True}
    updated = apply_live_controls(composition, {
        "headline": "ON AIR", "accent_color": "#ff3355", "duration_ms": 2500,
    })
    roles = {layer.metadata.get("template_role"): layer for layer in updated.layers}
    assert roles["headline"].source.params["text"] == "ON AIR"
    assert roles["accent"].source.params["fill"] == "#ff3355"
    assert updated.duration_ms == 2500
    assert all(layer.out_ms == 2500 for layer in updated.layers)
    assert "broadcast_cache" not in updated.metadata
    with pytest.raises(ValueError, match="unknown published template control"):
        apply_live_controls(composition, {"internal_layer_name": "bad"})


def test_live_controls_only_change_the_latest_template_instance() -> None:
    composition = instantiate_template("clean_lower_third", controls={"headline": "FIRST"})
    previous_instance = composition.metadata["last_applied_template"]["template_instance_id"]
    composition = apply_template_to_composition(
        composition, "clean_lower_third", controls={"headline": "SECOND"},
    )
    current_instance = composition.metadata["last_applied_template"]["template_instance_id"]
    assert current_instance != previous_instance
    updated = apply_live_controls(composition, {"headline": "LIVE"})
    headlines = {
        layer.metadata["template_instance_id"]: layer.source.params["text"]
        for layer in updated.layers if layer.metadata.get("template_role") == "headline"
    }
    assert headlines[previous_instance] == "FIRST"
    assert headlines[current_instance] == "LIVE"


def test_hard_budget_composition_is_offline_only() -> None:
    composition = MotionComposition(duration_ms=1000)
    composition.layers = [MotionLayer(name=f"Layer {index}", out_ms=1000) for index in range(97)]
    cost = estimate_broadcast_cost(composition)
    report = broadcast_preflight(composition)
    assert cost.grade == "offline_only"
    assert report["ok"] is False
    assert any("offline_only" in item for item in report["blockers"])


def test_stinger_render_writes_real_alpha_frames_and_current_manifest(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    composition = MotionComposition(width=80, height=48, fps=10, duration_ms=200)
    composition.layers = [MotionLayer(
        name="Wipe", layer_type="shape", out_ms=200,
        source=SourceRef(kind="shape", params={
            "shape": "rectangle", "width": 50, "height": 30,
            "fill": "#43d7b5cc", "stroke": "#00000000", "stroke_width": 0,
        }),
    )]
    composition.layers[0].transform.position.default = [40, 24]
    composition.metadata["broadcast_grade"] = "cached"
    plan = stinger_alpha_plan(composition, tmp_path)
    assert plan["frame_count"] == 2
    assert plan["storage_alpha"] == "straight"
    assert plan["composite_alpha"] == "premultiplied"

    cached, manifest = render_stinger_alpha_cache(composition, tmp_path)
    assert manifest["ready"] is True
    assert manifest["composition_revision"] == cached.revision
    assert Path(manifest["manifest_path"]).is_file()
    assert json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))["alpha"] is True
    frames = sorted(Path(manifest["path"]).glob("frame_*.png"))
    assert len(frames) == 2
    assert all(QImage(str(path)).hasAlphaChannel() for path in frames)
    assert broadcast_preflight(cached)["ok"] is True
    app.processEvents()


def test_broadcast_actions_share_core_contract(tmp_path: Path) -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {"comp": instantiate_template("clean_lower_third")}
            self._motion_compositions["comp"].id = "comp"

    owner = Owner()
    registry = ActionRegistry(owner)
    action_ids = {item["id"] for item in registry.list_actions()}
    assert {
        "motion.broadcast.preflight", "motion.broadcast.live_control.set",
        "motion.broadcast.stinger.plan", "motion.broadcast.stinger.render",
    } <= action_ids
    changed = registry.execute("motion.broadcast.live_control.set", {
        "composition_id": "comp", "changes": {"headline": "LIVE"},
    })
    assert changed.ok
    assert changed.result["published_controls"]["headline"] == "LIVE"
    assert registry.execute("motion.broadcast.preflight", {"composition_id": "comp"}).result["ok"] is True
