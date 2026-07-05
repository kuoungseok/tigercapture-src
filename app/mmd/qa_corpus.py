"""Reusable MMD QA corpus runner used by CLI tools and automation actions."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from app.mmd.diagnostics import analyze_mmd_model, format_mmd_report
from app.mmd.regression_profiles import evaluate_mmd_regression_profile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MMD_QA_MANIFEST = ROOT / "local_resources" / "mmd" / "qa_corpus_manifest.json"
MMD_QA_PASS_STATUSES = {"ready", "verified", "candidate"}


def resolve_mmd_qa_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return (ROOT / value).resolve()


def _resolve_resource_path(raw: Any) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _entry_paths_exist(entry: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in ("model_path", "motion_path", "camera_motion_path", "alternate_motion_path"):
        path = _resolve_resource_path(entry.get(key))
        if path is not None and not path.exists():
            missing.append(str(path))
    return missing


def _profile_result(report: dict[str, Any], profile_id: str) -> dict[str, Any] | None:
    if not profile_id:
        return None
    try:
        return evaluate_mmd_regression_profile(report, profile_id)
    except Exception as exc:
        return {
            "ok": False,
            "profile_id": profile_id,
            "label": profile_id,
            "check_count": 0,
            "failure_count": 1,
            "failures": [{"reason": type(exc).__name__, "message": str(exc)}],
        }


def run_mmd_qa_manifest(manifest_path: str | Path = DEFAULT_MMD_QA_MANIFEST) -> dict[str, Any]:
    """Run text diagnostics for every passing-status entry in an MMD QA manifest."""
    resolved_manifest = resolve_mmd_qa_path(manifest_path)
    manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    blocked = [dict(row) for row in list(manifest.get("blocked_entries") or []) if isinstance(row, dict)]
    for raw_entry in list(manifest.get("entries") or []):
        if not isinstance(raw_entry, dict):
            continue
        entry = dict(raw_entry)
        entry_id = str(entry.get("id") or "")
        status = str(entry.get("status") or "")
        result: dict[str, Any] = {
            "id": entry_id,
            "status": status,
            "ok": False,
            "skipped": status not in MMD_QA_PASS_STATUSES,
        }
        missing_paths = _entry_paths_exist(entry)
        if missing_paths:
            result["missing_paths"] = missing_paths
            result["error"] = "missing_manifest_resource"
            entries.append(result)
            continue
        if result["skipped"]:
            result["ok"] = True
            entries.append(result)
            continue

        model_path = _resolve_resource_path(entry.get("model_path"))
        motion_path = _resolve_resource_path(entry.get("motion_path"))
        if model_path is None:
            result["error"] = "missing_model_path"
            entries.append(result)
            continue
        try:
            report = analyze_mmd_model(model_path, motion_path)
        except Exception as exc:
            result["error"] = type(exc).__name__
            result["message"] = str(exc)
            entries.append(result)
            continue

        profile = _profile_result(report, str(entry.get("qa_profile") or ""))
        profile_ok = True if profile is None else bool(profile.get("ok"))
        result["ok"] = bool(report.get("ok")) and profile_ok
        result["report"] = report
        if profile is not None:
            result["regression_profile"] = profile
        entries.append(result)

    ok = all(bool(entry.get("ok")) for entry in entries if not bool(entry.get("skipped")))
    return {
        "ok": bool(ok),
        "manifest": str(resolved_manifest),
        "run_count": int(sum(1 for entry in entries if not bool(entry.get("skipped")))),
        "entry_count": int(len(entries)),
        "blocked_count": int(len(blocked)),
        "entries": entries,
        "blocked_entries": blocked,
    }


def format_mmd_qa_manifest_text(payload: dict[str, Any]) -> str:
    """Format a manifest QA run as the project's text-first QA output."""
    lines = [
        f"ok            : {bool(payload.get('ok'))}",
        f"run_count     : {int(payload.get('run_count', 0) or 0)}",
        f"entry_count   : {int(payload.get('entry_count', 0) or 0)}",
        f"blocked_count : {int(payload.get('blocked_count', 0) or 0)}",
        f"manifest      : {payload.get('manifest')}",
        "",
    ]
    for entry in list(payload.get("entries") or []):
        if not isinstance(entry, dict) or bool(entry.get("skipped")):
            continue
        lines.append(f"==== {entry.get('id')} [{entry.get('status')}] ok={bool(entry.get('ok'))} ====")
        report = entry.get("report")
        if isinstance(report, dict):
            lines.append(format_mmd_report([report]))
        else:
            lines.append(str(entry.get("error") or "no_report"))
        profile = entry.get("regression_profile")
        if isinstance(profile, dict):
            lines.append(
                f"profile      : {profile.get('profile_id')} ok={bool(profile.get('ok'))} "
                f"checks={int(profile.get('check_count', 0) or 0)} "
                f"failures={int(profile.get('failure_count', 0) or 0)}"
            )
            for failure in list(profile.get("failures") or [])[:8]:
                if isinstance(failure, dict):
                    lines.append(f"  - {failure}")
        lines.append("")
    return "\n".join(lines).rstrip()
