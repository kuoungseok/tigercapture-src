from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.actions import build_default_action_registry

from .feature_action_scenarios import (
    FeatureActionScenario,
    default_feature_action_scenarios,
    feature_action_scenario_for,
    materialize_feature_action_scenario,
)
from .paths import DEFAULT_REVIEW_OUTPUT_DIR, DEFAULT_REVIEW_REPORT, DEFAULT_REVIEW_SAMPLE_MANIFEST
from .sample_resources import review_sample_resource_report
from .artifacts import relpath


ROOT = Path(__file__).resolve().parents[2]


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


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


def _process_events() -> None:
    try:
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


def _widget_rect(editor: Any, widget: Any) -> list[int]:
    try:
        from PySide6.QtCore import QPoint

        if widget is None:
            return [0, 0, 0, 0]
        top_left = widget.mapTo(editor, QPoint(0, 0))
        return [int(top_left.x()), int(top_left.y()), int(widget.width()), int(widget.height())]
    except Exception:
        return [0, 0, 0, 0]


def _prepare_preview_for_capture(owner: Any, state: Mapping[str, Any]) -> None:
    track_id = state.get("video_track_id")
    clip_id = state.get("video_clip_id")
    target_ms = 750
    for track in list(getattr(owner, "_tracks", []) or []):
        if track_id is not None and int(getattr(track, "id", -1) or -1) != int(track_id):
            continue
        for clip in list(getattr(track, "clips", []) or []):
            if clip_id is not None and int(getattr(clip, "id", -1) or -1) != int(clip_id):
                continue
            start = int(getattr(clip, "timeline_in_ms", 0) or 0)
            end = int(getattr(clip, "timeline_out_ms", start + 1500) or start + 1500)
            target_ms = max(start, min(end - 120, start + 900))
            break
        break
    player = getattr(owner, "_player", None)
    setter = getattr(player, "set_position", None)
    if callable(setter):
        try:
            setter(int(target_ms))
        except Exception:
            pass
    refresher = getattr(player, "refresh_current_frame", None)
    if callable(refresher):
        try:
            refresher()
        except Exception:
            pass
    _process_events()


def _patch_capture_preview_frame(owner: Any, image_path: Path) -> bool:
    latest = getattr(owner, "_latest_preview_rgb", None)
    if latest is None or not image_path.exists():
        return False
    try:
        import numpy as np
        from PIL import Image, ImageDraw

        arr = np.asarray(latest)
        if arr.ndim != 3 or arr.shape[2] < 3 or arr.size == 0:
            return False
        if arr.dtype.kind == "f":
            scale = 255.0 if float(arr.max(initial=0.0)) <= 1.01 else 1.0
            arr = np.clip(arr[:, :, :3] * scale, 0, 255).astype(np.uint8)
        else:
            arr = np.clip(arr[:, :, :3], 0, 255).astype(np.uint8)

        label = getattr(owner, "_preview_label", None)
        label_x, label_y, label_w, label_h = _widget_rect(owner, label)
        if label_w <= 0 or label_h <= 0:
            return False
        frame_rect = None
        frame_rect_for = getattr(owner, "_preview_frame_rect_in_label", None)
        if callable(frame_rect_for):
            try:
                frame_rect = frame_rect_for(int(arr.shape[1]), int(arr.shape[0]))
            except Exception:
                frame_rect = None
        if frame_rect is not None:
            x = label_x + int(frame_rect.x())
            y = label_y + int(frame_rect.y())
            w = int(frame_rect.width())
            h = int(frame_rect.height())
        else:
            scale = min(label_w / max(1, int(arr.shape[1])), label_h / max(1, int(arr.shape[0])))
            w = max(1, int(arr.shape[1] * scale))
            h = max(1, int(arr.shape[0] * scale))
            x = label_x + (label_w - w) // 2
            y = label_y + (label_h - h) // 2
        canvas = Image.open(image_path).convert("RGB")
        x = max(0, min(int(x), canvas.width - 1))
        y = max(0, min(int(y), canvas.height - 1))
        w = max(1, min(int(w), canvas.width - x))
        h = max(1, min(int(h), canvas.height - y))
        frame = Image.fromarray(arr, "RGB").resize((w, h), Image.Resampling.LANCZOS)
        canvas.paste(frame, (x, y))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=10, outline=(255, 255, 255), width=1)
        canvas.save(image_path)
        return True
    except Exception:
        return False


def _actor_render_probe(owner: Any, state: Mapping[str, Any]) -> dict[str, Any]:
    """Verify that an actor scenario can render visible actor pixels.

    The review deck must not imply a Live2D/Spine actor is visible just because
    an actor lane exists. This probe uses the same actor clip renderer that the
    preview path uses and treats missing alpha pixels as blocked evidence.
    """
    track_id = state.get("actor_track_id")
    if track_id is None:
        return {"ok": False, "status": "missing_actor_track", "reason": "actor.add did not create an actor track"}
    for track in list(getattr(owner, "_live2d_actor_tracks", []) or []):
        if int(getattr(track, "id", -1) or -1) != int(track_id):
            continue
        clips = list(getattr(track, "clips", []) or [])
        if not clips:
            return {"ok": False, "status": "missing_actor_clip", "reason": "Live2D track has no clips"}
        clip = clips[min(max(0, int(state.get("actor_clip_index", 0) or 0)), len(clips) - 1)]
        pos_ms = int(getattr(clip, "start_ms", 0) or 0) + min(900, max(120, int(getattr(clip, "duration_ms", 1200) or 1200) // 2))
        try:
            image = clip.render_frame(320, 180, pos_ms)
        except Exception as exc:
            return {"ok": False, "status": "render_exception", "reason": repr(exc), "pos_ms": pos_ms}
        if image is None:
            return {"ok": False, "status": "render_none", "reason": "Live2D renderer returned no image", "pos_ms": pos_ms}
        try:
            bbox = image.getchannel("A").getbbox()
        except Exception as exc:
            return {"ok": False, "status": "alpha_probe_error", "reason": repr(exc), "pos_ms": pos_ms}
        if bbox is None:
            return {"ok": False, "status": "blank_alpha", "reason": "Live2D renderer produced no visible alpha pixels", "pos_ms": pos_ms}
        return {"ok": True, "status": "visible_actor_pixels", "bbox": [int(v) for v in bbox], "pos_ms": pos_ms}
    for track in list(getattr(owner, "_spine_actor_tracks", []) or []):
        if int(getattr(track, "id", -1) or -1) == int(track_id):
            clips = list(getattr(track, "clips", []) or [])
            return {"ok": bool(clips), "status": "spine_actor_track_present" if clips else "missing_spine_actor_clip"}
    return {"ok": False, "status": "actor_track_not_found", "reason": f"actor track not found: {track_id}"}


def _validate_live_capture(target: FeatureActionScenario, owner: Any, state: Mapping[str, Any], capture_path: Path) -> dict[str, Any]:
    if not capture_path.exists():
        return {"ok": False, "status": "missing_capture", "reason": str(capture_path)}
    if str(target.topic_id or "").strip().lower() == "actors":
        probe = _actor_render_probe(owner, state)
        if not probe.get("ok"):
            probe = dict(probe)
            probe.setdefault("reason", "actor renderer did not produce visible evidence")
        return probe
    return {"ok": True, "status": "capture_exists"}


def _reset_review_scenario_editor_state(owner: Any) -> None:
    for track in list(getattr(owner, "_tracks", []) or []):
        delete = getattr(owner, "_delete_track", None)
        if callable(delete):
            try:
                delete(int(getattr(track, "id", 0) or 0))
                continue
            except Exception:
                pass
    if list(getattr(owner, "_tracks", []) or []):
        setattr(owner, "_tracks", [])
        getattr(owner, "_track_rows", {}).clear()

    for track in list(getattr(owner, "_audio_tracks", []) or []):
        delete = getattr(owner, "_delete_audio_track", None)
        if callable(delete):
            try:
                delete(int(getattr(track, "id", 0) or 0))
                continue
            except Exception:
                pass
    if list(getattr(owner, "_audio_tracks", []) or []):
        setattr(owner, "_audio_tracks", [])
        getattr(owner, "_audio_rows", {}).clear()

    for attr, rebuild_name in (
        ("_spine_actor_tracks", "_rebuild_spine_actor_lanes"),
        ("_live2d_actor_tracks", "_rebuild_live2d_actor_lanes"),
    ):
        if getattr(owner, attr, None):
            setattr(owner, attr, [])
            rebuild = getattr(owner, rebuild_name, None)
            if callable(rebuild):
                try:
                    rebuild()
                except Exception:
                    pass
    if hasattr(owner, "_ar_pbr_tracks"):
        try:
            owner._ar_pbr_tracks = []
            sync = getattr(owner, "_sync_ar_pbr_tracks_to_player", None)
            if callable(sync):
                sync()
        except Exception:
            pass
    if hasattr(owner, "_timeline_markers"):
        owner._timeline_markers = []
        sync_markers = getattr(owner, "_sync_markers_to_ruler", None)
        if callable(sync_markers):
            try:
                sync_markers()
            except Exception:
                pass
    if hasattr(owner, "_selected_clips"):
        owner._selected_clips = []
    if hasattr(owner, "_active_track_id"):
        owner._active_track_id = None
    refresh = getattr(owner, "_refresh_player_tracks", None)
    if callable(refresh):
        try:
            refresh()
        except Exception:
            pass
    update_width = getattr(owner, "_update_tracks_host_width", None)
    if callable(update_width):
        try:
            update_width()
        except Exception:
            pass
    _process_events()


def _write_placeholder_live2d(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Version": 3,
        "FileReferences": {},
        "Groups": [],
        "Meta": {"source": "review_automation_placeholder"},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _review_live2d_fixture_path(*, root: Path, fallback_path: Path) -> Path:
    preferred = [
        root / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Haru/Haru.model3.json",
        root / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Hiyori/Hiyori.model3.json",
        root / "resources/live2d_samples/hiyori_free/hiyori_free_t08.model3.json",
        root / "resources/live2d_samples/HoshinoAi/Hoshino_Ai.model3.json",
    ]
    for path in preferred:
        if path.exists():
            return path
    _write_placeholder_live2d(fallback_path)
    return fallback_path


def _is_video_scoped_action(action: str) -> bool:
    return action.startswith(("timeline.", "clip.", "node.", "text.", "selection."))


def _is_audio_scoped_action(action: str) -> bool:
    return action.startswith("audio.")


def _adapt_params(action: str, params: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(params or {})
    if action == "media.import_to_timeline":
        kind = str(out.get("kind") or "").strip().lower()
        # Let the adapter create an isolated review track, then reuse the actual ids.
        if kind in {"video", "audio"}:
            out.pop("track_id", None)
        return out
    if _is_video_scoped_action(action):
        if out.get("track_id") == 1 and state.get("video_track_id") is not None:
            out["track_id"] = state.get("video_track_id")
        if out.get("clip_id") == 1 and state.get("video_clip_id") is not None:
            out["clip_id"] = state.get("video_clip_id")
    if _is_audio_scoped_action(action):
        if out.get("track_id") == 2 and state.get("audio_track_id") is not None:
            out["track_id"] = state.get("audio_track_id")
        if out.get("clip_id") == 1 and state.get("audio_clip_id") is not None:
            out["clip_id"] = state.get("audio_clip_id")
    if action.startswith("actor."):
        if out.get("track_id") == 10 and state.get("actor_track_id") is not None:
            out["track_id"] = state.get("actor_track_id")
    if action == "ui.focus_surface":
        target_kind = str(out.get("kind") or "").strip().lower()
        if target_kind == "audio":
            if out.get("track_id") in {2, "$audio_track_id", "audio_track_id"} and state.get("audio_track_id") is not None:
                out["track_id"] = state.get("audio_track_id")
            if out.get("clip_id") in {1, "$audio_clip_id", "audio_clip_id"} and state.get("audio_clip_id") is not None:
                out["clip_id"] = state.get("audio_clip_id")
        elif target_kind in {"live2d", "spine", "actor"}:
            if out.get("track_id") in {10, "$actor_track_id", "actor_track_id"} and state.get("actor_track_id") is not None:
                out["track_id"] = state.get("actor_track_id")
        else:
            if out.get("track_id") in {1, "$video_track_id", "video_track_id"} and state.get("video_track_id") is not None:
                out["track_id"] = state.get("video_track_id")
            if out.get("clip_id") in {1, "$video_clip_id", "video_clip_id"} and state.get("video_clip_id") is not None:
                out["clip_id"] = state.get("video_clip_id")
    if action == "text.set_keyframes" and out.get("text_id") == 1 and state.get("text_id") is not None:
        out["text_id"] = state.get("text_id")
    if action == "node.set_param" and state.get("node_id") is not None:
        current_node = str(out.get("node_id") or "").strip()
        if current_node and current_node not in {"1", "$node_id", "node_id", "last", "new"}:
            return out
        out["node_id"] = state.get("node_id")
    if action == "review.scenario.run":
        nested = out.get("params") if isinstance(out.get("params"), Mapping) else {}
        nested = dict(nested)
        nested["_live_nested"] = True
        nested.setdefault("write_html", False)
        nested.setdefault("write_ppt", False)
        out["params"] = nested
    return out


def _update_state_from_result(state: dict[str, Any], action: str, result: Mapping[str, Any]) -> None:
    payload = result.get("result") if isinstance(result.get("result"), Mapping) else {}
    if action == "media.import_to_timeline":
        kind = str(payload.get("kind") or "")
        if kind == "video":
            state["video_track_id"] = payload.get("track_id")
            state["video_clip_id"] = payload.get("clip_id")
        elif kind == "audio":
            state["audio_track_id"] = payload.get("track_id")
            state["audio_clip_id"] = payload.get("clip_id")
    elif action == "text.add" and payload.get("text_id") is not None:
        state["text_id"] = payload.get("text_id")
    elif action == "actor.add" and payload.get("track_id") is not None:
        state["actor_track_id"] = payload.get("track_id")
        state["actor_clip_index"] = payload.get("clip_index")
    elif action == "node.add" and payload.get("node_id") is not None:
        state["node_id"] = payload.get("node_id")


def _scenario_targets(raw: str, *, params: Mapping[str, Any]) -> list[FeatureActionScenario]:
    explicit_topic = str(params.get("topic_id") or params.get("feature_topic_id") or "").strip()
    if explicit_topic:
        match = feature_action_scenario_for(explicit_topic)
        return [match] if match else []
    text = str(raw or "").strip()
    if text in {"", "live-feature-captures", "feature-captures", "all", "features"}:
        return list(default_feature_action_scenarios())
    match = feature_action_scenario_for(text)
    return [match] if match else []


def run_live_feature_action_captures(
    owner: Any,
    *,
    scenario: str = "live-feature-captures",
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    options = dict(params or {})
    root = Path(options.get("project_root") or ROOT)
    out = Path(options.get("out_dir") or DEFAULT_REVIEW_OUTPUT_DIR)
    sample_manifest = Path(options.get("sample_manifest") or DEFAULT_REVIEW_SAMPLE_MANIFEST)
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    scenario_dir = out / "action_scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)

    sample_report = review_sample_resource_report(sample_manifest, root=root, create_default_if_missing=False)
    registry = build_default_action_registry(owner)
    targets = _scenario_targets(str(scenario or ""), params=options)
    live2d_fixture = _review_live2d_fixture_path(
        root=root,
        fallback_path=scenario_dir / "review_live2d_placeholder.model3.json",
    )
    rows: list[dict[str, Any]] = []

    for target in targets:
        _reset_review_scenario_editor_state(owner)
        materialized = materialize_feature_action_scenario(
            target,
            project_root=root,
            out_dir=out,
            sample_report=sample_report,
            live2d_fixture_path=live2d_fixture,
        )
        steps = list(materialized.get("steps") or [])
        state: dict[str, Any] = {}
        results: list[dict[str, Any]] = []
        failed_index = -1
        _process_events()
        for index, step in enumerate(steps):
            action = str(step.get("action") or "") if isinstance(step, Mapping) else ""
            raw_params = step.get("params") if isinstance(step, Mapping) and isinstance(step.get("params"), Mapping) else {}
            action_params = _adapt_params(action, raw_params, state)
            if action in {"capture.screenshot", "capture.gif"}:
                _prepare_preview_for_capture(owner, state)
                _process_events()
            result = registry.execute_action(
                action,
                action_params,
                dry_run=False,
                confirm_destructive=bool(options.get("confirm_destructive", False)),
            ).to_dict()
            if action == "capture.screenshot" and result.get("ok"):
                capture_file = Path(str(action_params.get("path") or ""))
                if str(capture_file):
                    payload = result.get("result") if isinstance(result.get("result"), Mapping) else {}
                    patched = _patch_capture_preview_frame(owner, capture_file)
                    if isinstance(payload, dict):
                        payload["preview_frame_patched"] = bool(patched)
                        result["result"] = payload
            results.append({"index": index, "action": action, "params": _json_safe(action_params), **_json_safe(result)})
            if result.get("ok"):
                _update_state_from_result(state, action, result)
                _process_events()
                continue
            failed_index = index
            break

        capture_path = Path(materialized.get("capture_path"))
        gif_path = Path(materialized.get("gif_path"))
        live_validation = _validate_live_capture(target, owner, state, capture_path)
        ok = failed_index < 0 and bool(live_validation.get("ok")) and capture_path.exists()
        row = target.to_dict()
        row.update(
            {
                "status": "live_captured" if ok else "live_failed",
                "automation_level": "registered_action_live",
                "live_capture": bool(ok),
                "dry_run_ok": True,
                "step_count": len(steps),
                "executed_step_count": len(results),
                "failed_index": failed_index,
                "artifact_path": relpath(capture_path, root=root),
                "artifact_exists": capture_path.exists(),
                "gif_path": relpath(gif_path, root=root),
                "gif_exists": gif_path.exists(),
                "state": _json_safe(state),
                "live_validation": _json_safe(live_validation),
                "live_result": {"ok": bool(ok), "failed_index": failed_index, "results": results},
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        scenario_path = scenario_dir / f"{target.id}_live.json"
        scenario_path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        row["evidence_path"] = relpath(scenario_path, root=root)
        rows.append(row)

    report = {
        "kind": "live_feature_action_scenario_report",
        "ok": bool(targets) and all(row.get("live_capture") for row in rows),
        "scenario": str(scenario or "live-feature-captures"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_count": len(rows),
        "live_capture_count": sum(1 for row in rows if row.get("live_capture")),
        "failed_count": sum(1 for row in rows if not row.get("live_capture")),
        "sample_report": sample_report,
        "scenarios": rows,
    }
    live_report_path = scenario_dir / "feature_action_scenarios_live.json"
    live_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = relpath(live_report_path, root=root)
    return report


def run_live_review_scenario(owner: Any, scenario: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    options = dict(params or {})
    scenario_text = str(scenario or "").strip().lower().replace("_", "-")
    if scenario_text in {"multi-monitor-capture", "multi-monitor", "multi-environment-capture", "multi-environment"}:
        from .window_actions import run_review_multi_monitor_capture

        return run_review_multi_monitor_capture(owner, options)

    if _as_bool(options.pop("_live_nested", False), False):
        from .deck_modes import normalize_deck_mode
        from .runner import build_review_automation_report

        deck_mode = normalize_deck_mode(str(options.pop("deck_mode", "") or scenario or "summary"))
        root = Path(options.pop("project_root", ROOT))
        out = Path(options.pop("out_dir", DEFAULT_REVIEW_OUTPUT_DIR))
        report_path = Path(options.pop("report_path", DEFAULT_REVIEW_REPORT))
        sample_manifest = Path(options.pop("sample_manifest", DEFAULT_REVIEW_SAMPLE_MANIFEST))
        report = build_review_automation_report(
            project_root=root,
            out_dir=out,
            report_path=report_path,
            sample_manifest=sample_manifest,
            write_html=_as_bool(options.pop("write_html", False), False),
            write_ppt=_as_bool(options.pop("write_ppt", False), False),
            deck_mode=deck_mode,
            force=_as_bool(options.pop("force", False), False),
        )
        return {
            "scenario": str(scenario or ""),
            "deck_mode": deck_mode,
            "executed": True,
            "live_capture": False,
            "nested": True,
            "ok": bool(report.get("ok")),
            "summary": dict(report.get("summary") or {}),
            "report_path": str(report.get("report_path") or ""),
        }

    targets = _scenario_targets(str(scenario or ""), params=options)
    run_live = bool(targets) or _as_bool(options.get("live_feature_captures"), False)
    live_report: dict[str, Any] | None = None
    if run_live:
        live_report = run_live_feature_action_captures(
            owner,
            scenario=str(scenario or "live-feature-captures"),
            params=options,
        )

    if targets and not _as_bool(options.get("build_report", False), False):
        return dict(live_report or {})

    from .deck_modes import normalize_deck_mode
    from .runner import build_review_automation_report

    deck_mode = normalize_deck_mode(str(options.get("deck_mode") or scenario or "summary"))
    root = Path(options.get("project_root") or ROOT)
    out = Path(options.get("out_dir") or DEFAULT_REVIEW_OUTPUT_DIR)
    report_path = Path(options.get("report_path") or DEFAULT_REVIEW_REPORT)
    sample_manifest = Path(options.get("sample_manifest") or DEFAULT_REVIEW_SAMPLE_MANIFEST)
    report = build_review_automation_report(
        project_root=root,
        out_dir=out,
        report_path=report_path,
        sample_manifest=sample_manifest,
        write_html=_as_bool(options.get("write_html"), True),
        write_ppt=_as_bool(options.get("write_ppt"), False),
        deck_mode=deck_mode,
        force=_as_bool(options.get("force"), False),
    )
    return {
        "scenario": str(scenario or ""),
        "deck_mode": deck_mode,
        "executed": True,
        "live_capture": bool(live_report),
        "ok": bool(report.get("ok")) and (True if live_report is None else bool(live_report.get("ok"))),
        "live_report": live_report or {},
        "summary": dict(report.get("summary") or {}),
        "report_path": str(report.get("report_path") or ""),
        "output_dir": str(report.get("output_dir") or ""),
        "warnings": list(report.get("warnings") or []),
    }
