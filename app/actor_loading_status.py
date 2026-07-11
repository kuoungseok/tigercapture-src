"""Transient loading state helpers for Live2D/Spine actor clips."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Any


STATUS_LOADING = "loading"
STATUS_READY = "ready"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"
STATUS_TIMEOUT = "timeout"
ACTOR_DIAGNOSTIC_CARD_SCHEMA = "tigercapture.actor.loading_diagnostic_card.v1"


def set_actor_clip_status(
    clip: Any,
    status: str,
    message: str = "",
    *,
    path: str = "",
) -> None:
    if clip is None:
        return
    try:
        setattr(clip, "_editor_load_status", str(status or ""))
        setattr(clip, "_editor_load_message", str(message or ""))
        setattr(clip, "_editor_load_path", str(path or ""))
        setattr(clip, "_editor_load_updated_at", time.time())
    except Exception:
        pass


def actor_clip_status(clip: Any) -> dict[str, Any]:
    if clip is None:
        return {}
    status = str(getattr(clip, "_editor_load_status", "") or "")
    if not status:
        return {}
    return {
        "status": status,
        "message": str(getattr(clip, "_editor_load_message", "") or ""),
        "path": str(getattr(clip, "_editor_load_path", "") or ""),
        "updated_at": float(getattr(clip, "_editor_load_updated_at", 0.0) or 0.0),
    }


def actor_clip_badge(clip: Any) -> tuple[str, str] | None:
    status = actor_clip_status(clip).get("status", "")
    if status == STATUS_LOADING:
        return "LOAD", "#5B45FF"
    if status == STATUS_READY:
        return "OK", "#38C7A0"
    if status == STATUS_ERROR:
        return "ERR", "#FF5A7A"
    if status == STATUS_TIMEOUT:
        return "TIME", "#FFBD59"
    if status == STATUS_CANCELLED:
        return "STOP", "#8A8FA8"
    return None


def _path_name(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        return Path(text).name
    except Exception:
        return text[-48:]


def _exists(path: str) -> bool:
    try:
        return Path(path).exists()
    except Exception:
        return False


def _mmd_actions(path: str, message: str) -> list[str]:
    actions: list[str] = []
    if not path:
        actions.append("Choose a PMX/PMD model before opening the MMD actor preview.")
    elif not _exists(path):
        actions.append("Relink the missing PMX/PMD file or restore it under the MMD model pool.")
    elif Path(path).suffix.casefold() not in {".pmx", ".pmd"} and not str(path).casefold().endswith(".pbx.json"):
        actions.append("Import MMD actors as PMX/PMD/PBX packages; VMD files belong in the motion library.")
    text = str(message or "").casefold()
    if "texture" in text:
        actions.append("Check missing texture paths in MMD diagnostics and restore the referenced image files.")
    if "decode" in text or "parse" in text or "index" in text:
        actions.append("Run MMD corpus diagnostics and quarantine the model if the PMX/PMD parser rejects it.")
    if not actions:
        actions.append("Open Actor Loading Manager, run Probe Selected, then inspect MMD diagnostics before retrying.")
    return actions


def actor_loading_diagnostic_card(
    kind: str,
    path: str = "",
    *,
    status: str = "",
    stage: str = "",
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a UI-ready actor loading diagnostic card.

    This card is the product contract for avoiding silent black actor previews:
    failures must surface the actor family, failed path, reason, and next steps.
    """
    raw_kind = str(kind or "actor").strip().lower()
    raw_status = str(status or "").strip().lower()
    raw_stage = str(stage or raw_status or "").strip().lower()
    text = str(message or "").strip()
    meta = dict(metadata or {})
    name = _path_name(path) or f"{raw_kind or 'actor'} asset"
    failure = raw_status in {STATUS_ERROR, STATUS_TIMEOUT, STATUS_CANCELLED, "blank", "failed", "fail", "crash"}
    loading = raw_status == STATUS_LOADING
    ready = raw_status == STATUS_READY
    tone = "error" if raw_status in {STATUS_ERROR, "failed", "fail", "crash"} else (
        "warning" if raw_status in {STATUS_TIMEOUT, STATUS_CANCELLED, "blank"} else ("ok" if ready else "info")
    )
    if ready:
        title = f"{raw_kind.upper()} actor ready"
        summary = text or f"{name} loaded and produced a preview-ready actor state."
    elif loading:
        title = f"{raw_kind.upper()} actor loading"
        summary = text or f"{name} is loading at stage {raw_stage or 'loading'}."
    elif raw_status == STATUS_TIMEOUT:
        title = f"{raw_kind.upper()} actor load timed out"
        summary = text or "The actor did not produce a first frame before the timeout."
    elif raw_status == STATUS_CANCELLED:
        title = f"{raw_kind.upper()} actor load cancelled"
        summary = text or "The actor load was cancelled before a usable preview frame was produced."
    elif raw_status in {"blank"}:
        title = f"{raw_kind.upper()} actor rendered blank"
        summary = text or "The actor renderer ran but produced no visible alpha pixels."
    elif failure:
        title = f"{raw_kind.upper()} actor load failed"
        summary = text or "The actor could not be loaded into the preview renderer."
    else:
        title = f"{raw_kind.upper()} actor diagnostic"
        summary = text or "Actor load status is available for inspection."

    actions: list[str] = []
    blockers: list[str] = []
    if failure:
        blockers.append(f"{raw_kind}_load_not_ready")
    if raw_status == STATUS_TIMEOUT:
        blockers.append("first_frame_timeout")
    if raw_status == "blank":
        blockers.append("blank_actor_frame")

    if raw_kind in {"live2d", "spine"}:
        try:
            from app.actor_compat_repair import actor_repair_guidance_report

            report = actor_repair_guidance_report(raw_kind, path, status_row={"severity": "high" if failure else "ok"})
            actions.extend(str(row) for row in report.get("actions", []) or [])
            blockers.extend(str(row) for row in report.get("blockers", []) or [])
            meta.setdefault("repair", report)
        except Exception as exc:
            actions.append(f"Open Actor Loading Manager and inspect {raw_kind} repair diagnostics.")
            meta.setdefault("repair_error", f"{type(exc).__name__}: {exc}")
    elif raw_kind == "mmd":
        actions.extend(_mmd_actions(path, text))
    else:
        actions.append("Open Actor Loading Manager and run isolated probe/render QA for this actor.")

    if raw_status == STATUS_TIMEOUT:
        actions.insert(0, "Retry once after the first load cache warms, then run isolated probe if it times out again.")
    if raw_status == "blank":
        actions.insert(0, "Treat this as a render failure, not a successful preview; run actor render QA before using the sample.")
    if not path:
        actions.insert(0, "Select or relink the actor asset path.")

    return {
        "schema": ACTOR_DIAGNOSTIC_CARD_SCHEMA,
        "kind": raw_kind,
        "status": raw_status or "unknown",
        "stage": raw_stage or raw_status or "unknown",
        "tone": tone,
        "title": title,
        "summary": summary,
        "path": str(path or ""),
        "asset_name": name,
        "blockers": _dedupe_text(blockers),
        "actions": _dedupe_text(actions),
        "metadata": meta,
    }


def _dedupe_text(rows: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = str(row or "").strip()
        key = text.casefold()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def format_actor_loading_diagnostic_card(card: dict[str, Any]) -> str:
    """Format a diagnostic card for QTextEdit/QMessageBox surfaces."""
    if not isinstance(card, dict):
        return "Actor diagnostic unavailable."
    lines = [
        str(card.get("title") or "Actor diagnostic"),
        str(card.get("summary") or "").strip(),
    ]
    path = str(card.get("path") or "").strip()
    if path:
        lines.append(f"Asset: {path}")
    stage = str(card.get("stage") or "").strip()
    status = str(card.get("status") or "").strip()
    if status or stage:
        lines.append(f"Status: {status or '-'} / Stage: {stage or '-'}")
    actions = [str(row).strip() for row in list(card.get("actions") or []) if str(row).strip()]
    if actions:
        lines.append("Next steps:")
        lines.extend(f"- {row}" for row in actions[:5])
    blockers = [str(row).strip() for row in list(card.get("blockers") or []) if str(row).strip()]
    if blockers:
        lines.append(f"Blockers: {', '.join(blockers[:5])}")
    return "\n".join(line for line in lines if line)
