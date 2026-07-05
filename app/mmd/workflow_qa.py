"""Action-level workflow QA for MMD actor editing."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.mmd.editor_composite_qa import (
    DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
    _entry_paths,
    select_mmd_editor_composite_entry,
)
from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST, resolve_mmd_qa_path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MMD_WORKFLOW_QA_OUT_DIR = ROOT / "debugCapture" / "mmd_player" / "workflow_qa"
DEFAULT_MMD_WORKFLOW_QA_REPORT = ROOT / "debugCapture" / "mmd_player" / "mmd_workflow_qa.json"
DEFAULT_MMD_WORKFLOW_ENTRY_ID = DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID


class _WorkflowPlayer:
    def __init__(self) -> None:
        self.tracks: list[dict[str, Any]] = []
        self.refresh_count = 0

    def position(self) -> int:
        return 0

    def duration(self) -> int:
        return 6000

    def set_mmd_tracks(self, tracks: list[dict[str, Any]] | None) -> None:
        self.tracks = list(tracks or [])

    def refresh_current_frame(self) -> None:
        self.refresh_count += 1


class _WorkflowOwner:
    def __init__(self) -> None:
        self._mmd_tracks: list[dict[str, Any]] = []
        self._player = _WorkflowPlayer()
        self.change_labels: list[str] = []
        self.refresh_tracks_count = 0

    def _refresh_player_tracks(self) -> None:
        self.refresh_tracks_count += 1

    def _sync_mmd_tracks_to_player(self) -> None:
        self._player.set_mmd_tracks(self._mmd_tracks)

    def _register_change(self, label: str) -> None:
        self.change_labels.append(str(label))


def _execute(registry: Any, action: str, params: dict[str, Any] | None = None, *, confirm: bool = False) -> dict[str, Any]:
    return registry.execute(action, params or {}, confirm_destructive=confirm).to_dict()


def _result_ok(row: dict[str, Any]) -> bool:
    return bool(row.get("ok")) and not bool(row.get("error"))


def run_mmd_workflow_qa(
    *,
    manifest: str | Path = DEFAULT_MMD_QA_MANIFEST,
    entry_id: str = DEFAULT_MMD_WORKFLOW_ENTRY_ID,
    out_dir: str | Path = DEFAULT_MMD_WORKFLOW_QA_OUT_DIR,
    report_path: str | Path = DEFAULT_MMD_WORKFLOW_QA_REPORT,
) -> dict[str, Any]:
    """Run the user-facing MMD actor action workflow without a live editor UI."""
    from app.actions import build_default_action_registry

    resolved_manifest = resolve_mmd_qa_path(manifest)
    out = Path(out_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    entry = select_mmd_editor_composite_entry(resolved_manifest, entry_id=entry_id)
    model_path, motion_path = _entry_paths(entry)
    if motion_path is None:
        raise ValueError(f"MMD workflow QA entry has no motion_path: {entry_id}")

    owner = _WorkflowOwner()
    registry = build_default_action_registry(owner)
    action_rows: list[dict[str, Any]] = []

    def run(action: str, params: dict[str, Any] | None = None, *, confirm: bool = False) -> dict[str, Any]:
        row = _execute(registry, action, params, confirm=confirm)
        action_rows.append(row)
        return row

    add = run(
        "mmd.actor.add",
        {
            "path": str(model_path),
            "track_id": "mmd_workflow_001",
            "start_ms": 400,
            "duration_ms": 1800,
        },
    )
    track_id = str(add.get("result", {}).get("track_id") or "mmd_workflow_001")
    before_library = run("mmd.motion.list", {"track_id": track_id})
    library_add = run("mmd.motion.add", {"track_id": track_id, "motion_path": str(motion_path)})
    after_library = run("mmd.motion.list", {"track_id": track_id})
    apply_motion = run("mmd.motion.apply", {"track_id": track_id, "motion_path": str(motion_path)})
    settings = run(
        "mmd.settings.apply",
        {
            "track_id": track_id,
            "playback": {
                "physics_rotation_hint_scale": 0.18,
                "physics_spring_response": 0.72,
                "gpu_skinning": True,
            },
            "render": {
                "lighting_preset": "night_stage",
                "bloom_strength": 0.42,
            },
            "material": {
                "skin_warmth": 1.20,
                "hair_highlight": 0.85,
            },
        },
    )
    move = run("mmd.track.move", {"track_id": track_id, "start_ms": 600})
    trim = run("mmd.track.trim", {"track_id": track_id, "duration_ms": 1400})
    duplicate = run(
        "mmd.actor.duplicate",
        {"track_id": track_id, "new_track_id": "mmd_workflow_002", "start_ms": 2200},
    )
    duplicate_id = str(duplicate.get("result", {}).get("track_id") or "mmd_workflow_002")
    destructive_guard = run("mmd.actor.delete", {"track_id": duplicate_id})
    delete_duplicate = run("mmd.actor.delete", {"track_id": duplicate_id}, confirm=True)
    summary = run("mmd.summary", {"limit": 10})
    diagnostics = run("mmd.diagnostics", {"track_id": track_id, "pos_ms": 700, "include_materials": False})

    track = owner._mmd_tracks[0] if owner._mmd_tracks else {}
    after_motion_paths = {
        str(row.get("path") or "")
        for row in list(after_library.get("result", {}).get("motions") or [])
        if isinstance(row, dict)
    }
    checks = {
        "actor_added": _result_ok(add) and track_id == "mmd_workflow_001" and len(owner._mmd_tracks) >= 1,
        "motion_library_add_visible": _result_ok(library_add) and str(motion_path.resolve()) in after_motion_paths,
        "motion_apply_persisted": _result_ok(apply_motion) and str(track.get("motion_path") or "") == str(motion_path.resolve()),
        "settings_persisted": _result_ok(settings)
        and abs(float((track.get("playback") or {}).get("physics_rotation_hint_scale", 0.0)) - 0.18) < 1e-6
        and abs(float((track.get("playback") or {}).get("physics_spring_response", 0.0)) - 0.72) < 1e-6
        and str((track.get("render") or {}).get("lighting_preset") or "") == "night_stage"
        and abs(float((track.get("render") or {}).get("bloom_strength", 0.0)) - 0.42) < 1e-6,
        "move_and_trim_persisted": _result_ok(move)
        and _result_ok(trim)
        and int(track.get("start_ms", 0) or 0) == 600
        and int(track.get("duration_ms", 0) or 0) == 1400,
        "duplicate_and_delete_worked": _result_ok(duplicate)
        and not bool(destructive_guard.get("ok"))
        and _result_ok(delete_duplicate)
        and [str(row.get("id") or "") for row in owner._mmd_tracks] == [track_id],
        "summary_and_diagnostics_worked": _result_ok(summary)
        and _result_ok(diagnostics)
        and int(summary.get("result", {}).get("track_count", 0) or 0) == 1
        and int(diagnostics.get("result", {}).get("track_count", 0) or 0) == 1,
        "player_sync_happened": owner._player.tracks == owner._mmd_tracks and owner._player.refresh_count >= 1,
    }
    failures = [{"check": key, "message": "check failed"} for key, value in checks.items() if not value]
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "mmd_workflow_qa",
        "manifest": str(resolved_manifest),
        "entry_id": str(entry.get("id") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path),
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for value in checks.values() if value),
            "failing": len(failures),
            "action_count": len(action_rows),
            "final_track_count": len(owner._mmd_tracks),
            "player_refresh_count": owner._player.refresh_count,
        },
        "checks": checks,
        "actions": action_rows,
        "before_motion_count": len(list(before_library.get("result", {}).get("motions") or [])),
        "after_motion_count": len(list(after_library.get("result", {}).get("motions") or [])),
        "final_tracks": [dict(row) for row in owner._mmd_tracks],
        "change_labels": list(owner.change_labels),
        "failures": failures,
        "outputs": {
            "out_dir": str(out),
        },
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report)
    return payload
