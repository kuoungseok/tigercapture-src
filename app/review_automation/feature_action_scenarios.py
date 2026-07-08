from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.actions import build_default_action_registry

from .artifacts import feature_editor_surface_artifact_id, feature_editor_surface_specs, relpath


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class FeatureActionScenario:
    id: str
    topic_id: str
    feature_id: str
    title: str
    summary: str
    sample_resource_ids: tuple[str, ...]
    steps: tuple[Mapping[str, Any], ...]
    capture_target: str = "editor"
    capture_method: str = "registered_actions_then_feature_surface"

    @property
    def artifact_id(self) -> str:
        return feature_editor_surface_artifact_id(self.topic_id)

    def to_dict(self) -> dict[str, Any]:
        action_ids = [str(row.get("action") or "") for row in self.steps if isinstance(row, Mapping)]
        return {
            "id": self.id,
            "topic_id": self.topic_id,
            "feature_id": self.feature_id,
            "title": self.title,
            "summary": self.summary,
            "sample_resource_ids": list(self.sample_resource_ids),
            "action_ids": action_ids,
            "capture_target": self.capture_target,
            "capture_method": self.capture_method,
            "artifact_id": self.artifact_id,
            "artifact_ids": [self.artifact_id, "feature_action_scenarios"],
        }


def _step(action: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"action": action, "params": dict(params or {})}


def _spec_title(topic_id: str) -> str:
    for spec in feature_editor_surface_specs():
        if str(spec.get("id") or "") == topic_id:
            return str(spec.get("title") or topic_id)
    return topic_id.replace("_", " ").title()


def _scenario(
    topic_id: str,
    feature_id: str,
    summary: str,
    steps: Iterable[Mapping[str, Any]],
    *,
    sample_resource_ids: tuple[str, ...] = ("overview_screen_demo",),
    capture_target: str = "editor",
) -> FeatureActionScenario:
    return FeatureActionScenario(
        id=f"feature_{topic_id}_action_review",
        topic_id=topic_id,
        feature_id=feature_id,
        title=_spec_title(topic_id),
        summary=summary,
        sample_resource_ids=sample_resource_ids,
        steps=tuple(steps),
        capture_target=capture_target,
    )


def default_feature_action_scenarios() -> tuple[FeatureActionScenario, ...]:
    """Feature-page review scenarios aligned with detailed/evidence deck topics."""

    return (
        _scenario(
            "screen_recording",
            "screenstudio_auto_polish",
            "Import a screen recording sample, zoom the timeline, mark cursor/click moments, and capture screenshot/GIF evidence.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 6000}),
                _step("timeline.set_zoom", {"px_per_sec": 340}),
                _step("timeline.marker.add", {"ms": 1200, "label": "cursor emphasis", "color": "#69E7D6"}),
                _step("clip.set_filter", {"track_id": 1, "clip_id": 1, "params": {"cursor_ring": True, "click_pulse": 0.75}}),
                _step("ui.focus_surface", {"surface": "timeline", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "clip"}),
                _step("capture.gif", {"path": "$feature_capture_gif_path", "target": "preview", "duration_ms": 1600, "fps": 10}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "creator_assist",
            "action_automation",
            "Create a prompt-assisted shorts edit with caption/keyframe lanes and a review screenshot.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 8000}),
                _step("timeline.set_in", {"ms": 500}),
                _step("timeline.set_out", {"ms": 6500}),
                _step("timeline.marker.add", {"ms": 2400, "label": "shorts beat", "color": "#FF5F45"}),
                _step("text.add", {"track_id": 1, "clip_id": 1, "text": "Creator Assist", "start_ms": 500, "end_ms": 3600, "style": {"position_y": 0.18}}),
                _step("text.set_keyframes", {"track_id": 1, "clip_id": 1, "text_id": 1, "keyframes": {"opacity": [{"time_ms": 500, "value": 0.0}, {"time_ms": 900, "value": 1.0}]}}),
                _step("ui.focus_surface", {"surface": "timeline", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "clip"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "multilingual_localization",
            "multilingual_ui",
            "Build a typography-heavy canvas with large title layers, multilingual text, and visible keyframes.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 8000}),
                _step("timeline.set_zoom", {"px_per_sec": 360}),
                _step("timeline.marker.add", {"ms": 900, "label": "title entrance", "color": "#B9FF66"}),
                _step("timeline.marker.add", {"ms": 4200, "label": "locale sweep", "color": "#7BA8FF"}),
                _step(
                    "text.add",
                    {
                        "track_id": 1,
                        "clip_id": 1,
                        "text": "TYPE THAT MOVES",
                        "start_ms": 250,
                        "end_ms": 6200,
                        "style": {
                            "font_size": 112,
                            "font_weight": 600,
                            "letter_spacing": 0,
                            "position_x": 0.50,
                            "position_y": 0.24,
                            "align": "center",
                            "color": "#F7F8F2",
                        },
                    },
                ),
                _step(
                    "text.set_keyframes",
                    {
                        "track_id": 1,
                        "clip_id": 1,
                        "text_id": 1,
                        "keyframes": {
                            "opacity": [{"time_ms": 250, "value": 0.0}, {"time_ms": 900, "value": 1.0}, {"time_ms": 5900, "value": 1.0}],
                            "scale": [{"time_ms": 250, "value": 0.92}, {"time_ms": 900, "value": 1.0}, {"time_ms": 5900, "value": 1.04}],
                            "position_y": [{"time_ms": 250, "value": 0.30}, {"time_ms": 900, "value": 0.24}],
                        },
                    },
                ),
                _step(
                    "text.add",
                    {
                        "track_id": 1,
                        "clip_id": 1,
                        "text": "Kinetic titles / captions / multilingual layouts",
                        "start_ms": 800,
                        "end_ms": 7000,
                        "style": {"font_size": 42, "position_x": 0.50, "position_y": 0.40, "align": "center", "color": "#D7DEE8"},
                    },
                ),
                _step(
                    "text.add",
                    {
                        "track_id": 1,
                        "clip_id": 1,
                        "text": "한국어 타이틀 · 日本語タイトル · English Headline",
                        "start_ms": 1400,
                        "end_ms": 7600,
                        "style": {"font_size": 34, "position_x": 0.50, "position_y": 0.70, "align": "center", "color": "#B9FF66"},
                    },
                ),
                _step(
                    "text.add",
                    {
                        "track_id": 1,
                        "clip_id": 1,
                        "text": "Preset cards, safe fonts, opacity keys, position keys, export-ready titles",
                        "start_ms": 1800,
                        "end_ms": 7600,
                        "style": {"font_size": 28, "position_x": 0.50, "position_y": 0.80, "align": "center", "color": "#B8C2D4"},
                    },
                ),
                _step("text.set_keyframes", {"track_id": 1, "clip_id": 1, "text_id": 2, "keyframes": {"opacity": [{"time_ms": 800, "value": 0.0}, {"time_ms": 1300, "value": 1.0}]}}),
                _step("ui.focus_surface", {"surface": "timeline", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "text"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "ai_script_edit",
            "ai_script_edit",
            "Represent transcript-driven editing with guarded apply markers and a review scenario handoff.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 9000}),
                _step("timeline.marker.add", {"ms": 1800, "label": "script beat", "color": "#C6ABFF"}),
                _step("timeline.split", {"track_id": 1, "at_ms": 3000}),
                _step("clip.trim", {"track_id": 1, "clip_id": 1, "source_in_ms": 0, "source_out_ms": 2760}),
                _step("review.scenario.run", {"scenario": "ai-script-edit", "params": {"mode": "dry_review"}}),
                _step("ui.focus_surface", {"surface": "timeline", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "clip"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "timeline_editing",
            "overview_editor",
            "Show timeline editing with split, speed, markers, node graph, selection, and inspector lanes.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 7000}),
                _step("timeline.set_zoom", {"px_per_sec": 420}),
                _step("timeline.marker.add", {"ms": 2200, "label": "cut point", "color": "#69E7D6"}),
                _step("timeline.split", {"track_id": 1, "at_ms": 2200}),
                _step("clip.set_speed", {"track_id": 1, "clip_id": 1, "speed": 1.25}),
                _step("node.add", {"track_id": 1, "kind": "blur", "label": "Focus blur", "x": -60, "y": -20, "params": {"radius": 5}}),
                _step("selection.set", {"kind": "video", "track_id": 1, "clip_id": 1}),
                _step("ui.focus_surface", {"surface": "node_graph", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "fx"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "actors",
            "live2d_overlay",
            "Place an actor lane beside normal video and animate transform/opacity keyframes for review capture.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 6000}),
                _step("actor.add", {"kind": "live2d", "path": "$live2d_fixture", "track_id": 10, "start_ms": 500, "duration_ms": 4200, "pos_x": 0.68, "pos_y": 0.64, "scale": 0.82, "opacity": 1.0}),
                _step("actor.set_transform", {"kind": "live2d", "track_id": 10, "clip_index": 0, "pos_x": 0.62, "pos_y": 0.62, "scale": 0.92, "opacity": 0.95}),
                _step("actor.set_keyframes", {"kind": "live2d", "track_id": 10, "clip_index": 0, "keyframes": {"opacity": [{"time_ms": 0, "value": 0.0}, {"time_ms": 350, "value": 1.0}, {"time_ms": 3900, "value": 1.0}, {"time_ms": 4300, "value": 0.0}]}}),
                _step("ui.focus_surface", {"surface": "actors", "kind": "live2d", "track_id": 10, "open_aux_window": False}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "color_audio_vfx",
            "audio_cleanup",
            "Apply color grade, filter, mask node, audio mix, and clip gain before capturing the finishing view.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 7000}),
                _step("media.import_to_timeline", {"path": "$dialogue_audio", "kind": "audio", "track_id": 2, "at_ms": 0, "duration_ms": 7000}),
                _step("clip.set_color_grade", {"track_id": 1, "clip_id": 1, "grade": {"exposure": 0.08, "contrast": 1.12, "saturation": 1.08}}),
                _step("clip.set_filter", {"track_id": 1, "clip_id": 1, "params": {"vignette": 0.18, "sharpen": 0.22}}),
                _step("node.add", {"track_id": 1, "kind": "mask", "label": "Tracked mask", "x": 120, "y": -40, "params": {"feather": 0.35}}),
                _step("audio.track.set_volume", {"track_id": 2, "volume": 0.82}),
                _step("audio.track.set_pan", {"track_id": 2, "pan": -0.05}),
                _step("audio.track.mute", {"track_id": 2, "muted": False}),
                _step("audio.track.solo", {"track_id": 2, "solo": False}),
                _step("audio.track.set_type", {"track_id": 2, "track_type": "dialogue"}),
                _step("audio.track.insert.set", {"track_id": 2, "slot": "eq", "enabled": True}),
                _step("audio.track.insert.set", {"track_id": 2, "slot": "dyn", "enabled": True}),
                _step("audio.track.send.set_level", {"track_id": 2, "send_id": "reverb", "level": 0.24}),
                _step("audio.track.route_to_bus", {"track_id": 2, "bus_id": "dialogue"}),
                _step("audio.automation.write", {"track_id": 2, "parameter": "volume", "time_ms": 1200, "value": 0.78, "read": True, "write": True}),
                _step("audio.clip.set_gain", {"track_id": 2, "clip_id": 1, "gain": 1.12}),
                _step("audio.track.meter.state", {"track_id": 2}),
                _step("audio.mixer.snapshot.save", {"snapshot_id": "review_mix_a", "name": "Review Mix A"}),
                _step("audio.mixer.state", {}),
                _step("ui.focus_surface", {"surface": "color_grading", "kind": "video", "track_id": 1, "clip_id": 1, "show_audio_mixer": True, "show_audio_scopes": True}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
            sample_resource_ids=("overview_screen_demo", "dialogue_cleanup_demo"),
        ),
        _scenario(
            "export_parity",
            "review_site_deck",
            "Frame an export/parity review range and trigger the review scenario output contract.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 6000}),
                _step("timeline.set_in", {"ms": 0}),
                _step("timeline.set_out", {"ms": 6000}),
                _step("timeline.play_range", {"start_ms": 0, "end_ms": 1800, "restore_playhead": True}),
                _step("review.scenario.run", {"scenario": "export-parity", "params": {"report_path": "$review_report_path"}}),
                _step("ui.focus_surface", {"surface": "export", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "meta"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "ar_pbr_3d",
            "action_automation",
            "Build a tracked plate review surface with PBR/composite node evidence.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 6000}),
                _step("node.add", {"track_id": 1, "node_id": "pbr_composite", "kind": "pbr_composite", "label": "PBR object", "x": 40, "y": 20, "params": {"lighting": "hdri", "asset": "camera_scene"}}),
                _step("node.set_param", {"track_id": 1, "node_id": "pbr_composite", "params": {"camera_solve": True, "composite_mode": "pbr"}}),
                _step("timeline.marker.add", {"ms": 3000, "label": "PBR composite", "color": "#FF97CD"}),
                _step("ui.focus_surface", {"surface": "node_graph", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "fx"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "performance_health",
            "action_automation",
            "Exercise timeline zoom and health markers so performance evidence has a visible editor context.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 6000}),
                _step("timeline.set_zoom", {"px_per_sec": 300}),
                _step("timeline.marker.add", {"ms": 1600, "label": "cache warm", "color": "#69E7D6"}),
                _step("timeline.marker.add", {"ms": 4200, "label": "worker boundary", "color": "#FFD166"}),
                _step("ui.focus_surface", {"surface": "timeline", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "meta"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
        _scenario(
            "productization_release",
            "review_site_deck",
            "Run the review scenario/deck contract and capture the release-evidence editor surface.",
            (
                _step("media.import_to_timeline", {"path": "$overview_video", "kind": "video", "track_id": 1, "at_ms": 0, "duration_ms": 6000}),
                _step("review.scenario.run", {"scenario": "evidence-full", "params": {"deck_mode": "evidence-full", "report_path": "$review_report_path"}}),
                _step("ui.focus_surface", {"surface": "metadata", "kind": "video", "track_id": 1, "clip_id": 1, "inspector_tab": "meta"}),
                _step("capture.screenshot", {"path": "$feature_capture_path", "target": "editor"}),
            ),
        ),
    )


def _resources_by_id(sample_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("id")): row
        for row in list(sample_report.get("resources", []) or [])
        if isinstance(row, Mapping) and row.get("id")
    }


def _resolve_resource_path(resources: Mapping[str, Mapping[str, Any]], resource_id: str, *, root: Path) -> Path | None:
    row = resources.get(resource_id)
    if not row:
        return None
    raw = Path(str(row.get("path") or ""))
    path = raw if raw.is_absolute() else root / raw
    return path if path.exists() else None


def _resolve_artifact_path(artifact: Mapping[str, Any] | None, *, root: Path) -> Path | None:
    if not artifact:
        return None
    raw = Path(str(artifact.get("output_path") or ""))
    path = raw if raw.is_absolute() else root / raw
    return path if str(raw) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _replace_tokens(value: Any, tokens: Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _replace_tokens(item, tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_tokens(item, tokens) for item in value]
    if isinstance(value, tuple):
        return [_replace_tokens(item, tokens) for item in value]
    if isinstance(value, str) and value in tokens:
        return tokens[value]
    return value


def feature_action_scenario_for(value: str) -> FeatureActionScenario | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.lower().replace("-", "_")
    for scenario in default_feature_action_scenarios():
        if text == scenario.id or text == scenario.topic_id:
            return scenario
        if normalized == scenario.id.lower().replace("-", "_"):
            return scenario
        if normalized == scenario.topic_id.lower().replace("-", "_"):
            return scenario
        if normalized == f"feature_{scenario.topic_id}_action_review":
            return scenario
    return None


def materialize_feature_action_scenario(
    scenario: FeatureActionScenario,
    *,
    project_root: str | Path = ROOT,
    out_dir: str | Path,
    sample_report: Mapping[str, Any],
    artifacts: Iterable[Mapping[str, Any]] = (),
    live2d_fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    out = Path(out_dir)
    scenario_dir = out / "action_scenarios"
    assets_dir = out / "assets"
    resources = _resources_by_id(sample_report)
    artifact_map = {
        str(row.get("id")): row
        for row in list(artifacts or [])
        if isinstance(row, Mapping) and row.get("id")
    }
    overview_video = (
        _resolve_resource_path(resources, "overview_screen_demo", root=root)
        or _resolve_resource_path(resources, "screenstudio_cursor_demo", root=root)
    )
    dialogue_audio = _resolve_resource_path(resources, "dialogue_cleanup_demo", root=root)
    artifact = artifact_map.get(scenario.artifact_id)
    artifact_path = _resolve_artifact_path(artifact, root=root)
    capture_path = artifact_path or (assets_dir / f"{scenario.artifact_id}.png")
    live2d_path = Path(live2d_fixture_path) if live2d_fixture_path else scenario_dir / "review_live2d_placeholder.model3.json"
    tokens = {
        "$overview_video": str(overview_video or ""),
        "$dialogue_audio": str(dialogue_audio or ""),
        "$feature_capture_path": str(capture_path),
        "$feature_capture_gif_path": str(scenario_dir / f"{scenario.topic_id}_feature_capture.gif"),
        "$live2d_fixture": str(live2d_path),
        "$review_report_path": str(out / "review_report.json"),
    }
    steps = [_json_safe(_replace_tokens(step, tokens)) for step in scenario.steps]
    missing_resources = [
        resource_id
        for resource_id in scenario.sample_resource_ids
        if _resolve_resource_path(resources, resource_id, root=root) is None
    ]
    return {
        "scenario": scenario,
        "steps": steps,
        "tokens": _json_safe(tokens),
        "overview_video": overview_video,
        "dialogue_audio": dialogue_audio,
        "capture_path": capture_path,
        "gif_path": scenario_dir / f"{scenario.topic_id}_feature_capture.gif",
        "live2d_fixture_path": live2d_path,
        "missing_resources": missing_resources,
        "artifact_path": capture_path,
    }


def build_feature_action_scenario_report(
    *,
    project_root: str | Path = ROOT,
    out_dir: str | Path,
    sample_report: Mapping[str, Any],
    artifacts: Iterable[Mapping[str, Any]],
    force: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(project_root)
    out = Path(out_dir)
    scenario_dir = out / "action_scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    path = scenario_dir / "feature_action_scenarios.json"

    artifact_map = {
        str(row.get("id")): row
        for row in list(artifacts or [])
        if isinstance(row, Mapping) and row.get("id")
    }
    registry = build_default_action_registry(None)
    registered_actions = {str(row.get("id") or "") for row in registry.specs()}
    live_report_path = scenario_dir / "feature_action_scenarios_live.json"
    live_by_id: dict[str, Mapping[str, Any]] = {}
    if live_report_path.exists():
        try:
            live_payload = json.loads(live_report_path.read_text(encoding="utf-8"))
        except Exception:
            live_payload = {}
        if isinstance(live_payload, Mapping):
            live_by_id = {
                str(row.get("id") or ""): row
                for row in list(live_payload.get("scenarios", []) or [])
                if isinstance(row, Mapping) and row.get("id")
            }

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for scenario in default_feature_action_scenarios():
        materialized = materialize_feature_action_scenario(
            scenario,
            project_root=root,
            out_dir=out,
            sample_report=sample_report,
            artifacts=artifacts,
        )
        steps = list(materialized.get("steps") or [])
        action_ids = [str(step.get("action") or "") for step in steps if isinstance(step, Mapping)]
        missing_actions = [action_id for action_id in action_ids if action_id not in registered_actions]
        missing_resources = list(materialized.get("missing_resources") or [])
        artifact = artifact_map.get(scenario.artifact_id)
        missing_artifacts = [] if artifact and artifact.get("exists") else [scenario.artifact_id]
        dry_run_result: dict[str, Any]
        if missing_actions:
            dry_run_result = {"ok": False, "failed_index": -1, "results": [], "missing_actions": missing_actions}
        else:
            dry_run_result = registry.execute_sequence(steps, dry_run=True)

        dry_run_ok = bool(dry_run_result.get("ok"))
        if missing_actions:
            status = "blocked"
        elif missing_resources or missing_artifacts:
            status = "pending_evidence"
        elif dry_run_ok:
            status = "action_plan_ready"
        else:
            status = "blocked"

        row = scenario.to_dict()
        row.update(
            {
                "status": status,
                "automation_level": "registered_action_dry_run",
                "live_capture": False,
                "dry_run_ok": dry_run_ok,
                "steps": steps,
                "step_count": len(steps),
                "missing_actions": missing_actions,
                "missing_resources": missing_resources,
                "missing_artifacts": missing_artifacts,
                "artifact_path": relpath(Path(materialized.get("artifact_path")), root=root),
                "dry_run_result": _json_safe(dry_run_result),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        live_row = live_by_id.get(scenario.id)
        if live_row:
            live_artifact = artifact_map.get(scenario.artifact_id)
            live_exists = bool(live_row.get("artifact_exists") or (live_artifact and live_artifact.get("exists")))
            live_validation = live_row.get("live_validation") if isinstance(live_row.get("live_validation"), Mapping) else {}
            live_ok = bool(live_row.get("live_capture") is True and live_exists)
            row.update(
                {
                    "automation_level": "registered_action_live" if live_ok else "registered_action_live_failed",
                    "live_capture": live_ok,
                    "live_result": _json_safe(live_row.get("live_result") or {}),
                    "live_validation": _json_safe(live_validation),
                    "live_evidence_path": str(live_row.get("evidence_path") or ""),
                    "live_generated_at": str(live_row.get("generated_at") or ""),
                }
            )
            if live_ok:
                row["status"] = "live_captured"
            elif not bool(live_validation.get("ok", True)):
                row["status"] = "blocked"
                row["blocking_reason"] = str(live_validation.get("reason") or live_validation.get("status") or "live validation failed")
        scenario_path = scenario_dir / f"{scenario.id}.json"
        if force or not scenario_path.exists():
            scenario_path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        row["evidence_path"] = relpath(scenario_path, root=root)
        rows.append(row)
        if str(row.get("status") or "") not in {"action_plan_ready", "live_captured"}:
            warnings.append(f"feature action scenario not ready: {scenario.id} ({row.get('status')})")

    ready_statuses = {"action_plan_ready", "captured", "live_captured", "evidence_ready"}
    report = {
        "kind": "feature_action_scenario_report",
        "ok": all(row.get("status") in ready_statuses for row in rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_count": len(rows),
        "ready_count": sum(1 for row in rows if row.get("status") in ready_statuses),
        "dry_run_ready_count": sum(1 for row in rows if row.get("dry_run_ok")),
        "live_capture_count": sum(1 for row in rows if row.get("live_capture")),
        "scenarios": rows,
        "warnings": warnings,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact = {
        "id": "feature_action_scenarios",
        "title": "Feature action scenario report",
        "kind": "json",
        "source_path": "",
        "output_path": relpath(path, root=root),
        "exists": path.exists(),
        "size": int(path.stat().st_size) if path.exists() else 0,
    }
    return report, artifact
