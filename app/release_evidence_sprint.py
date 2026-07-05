"""Evidence collection sprint for the remaining release blockers.

The sprint turns the two evidence-heavy gaps into concrete local files:
Screen Studio cursor sidecar capture commands and AI real-corpus registration
templates.  It never writes counted QA evidence by itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OUT_DIR = Path("debugCapture/release_evidence_sprint")


SCREENSTUDIO_REQUIREMENT_LABELS = {
    "cursor_sidecar": "Cursor sidecar",
    "click": "Click animation",
    "drag": "Drag tracking",
    "hotkey": "Hotkey overlay",
    "auto_zoom": "Auto zoom window",
}


SCREENSTUDIO_REQUIREMENT_ACTIONS = {
    "cursor_sidecar": "Record a real .cursor.json sidecar for this video.",
    "click": "Replay real clicks so click rings and cursor pop animation can be validated.",
    "drag": "Replay at least one drag span so smoothing and drag trail QA has evidence.",
    "hotkey": "Press a real shortcut during capture so shortcut overlay QA has evidence.",
    "auto_zoom": "Capture enough cursor action points for auto-zoom window planning.",
}


BROADCAST_PLATFORM_CHECK_LABELS = {
    "private_rtmp_ingest": "Private/unlisted RTMP ingest",
    "discord_window_share": "Discord/video-call Program Output share",
}


BROADCAST_PLATFORM_CHECK_ACTIONS = {
    "private_rtmp_ingest": "Run YouTube, Twitch, or Custom RTMP and attach redacted ingest evidence.",
    "discord_window_share": "Join a test call and verify only Program Output is shared.",
}


def _ps_quote(value: str | Path) -> str:
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _python_command(root: Path) -> Path | str:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    return venv_python if venv_python.exists() else "python"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return default


def _screenstudio_rows(intake: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = [dict(row) for row in list(intake.get("rows") or []) if isinstance(row, Mapping)]
    missing = [row for row in rows if row.get("missing_requirements")]

    def _slot_order(row: Mapping[str, Any]) -> int:
        slot = str(row.get("slot_id") or "")
        try:
            value = int(slot.rsplit("-", 1)[-1])
        except Exception:
            return 9999
        if 1 <= value <= 20:
            return value
        return 1000 + value

    missing.sort(
        key=lambda row: (
            0 if "cursor_sidecar" in list(row.get("missing_requirements") or []) else 1,
            _slot_order(row),
            _safe_int(row.get("index"), 9999),
        )
    )
    if limit > 0:
        return missing[:limit]
    return missing


def _ai_template_rows(intake: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = [dict(row) for row in list(intake.get("rows") or []) if isinstance(row, Mapping)]
    pending = [row for row in rows if row.get("template_path") and not row.get("ready")]
    pending.sort(key=lambda row: _safe_int(row.get("index"), 9999))
    if limit > 0:
        return pending[:limit]
    return pending


def _broadcast_platform_report(root: Path) -> dict[str, Any]:
    cached = _load_json(root / "debugCapture" / "broadcast_platform_e2e_qa.json")
    if cached:
        return cached
    try:
        from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

        return build_broadcast_platform_e2e_report(root, run_record_smoke=False)
    except Exception as exc:
        return {
            "ok": False,
            "real_platform_evidence": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checks": [],
            "summary": {"passed": 0, "required": 2, "pending": 2},
        }


def _broadcast_platform_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in list(report.get("checks") or []):
        if not isinstance(row, Mapping):
            continue
        check_id = str(row.get("id") or "")
        if check_id not in BROADCAST_PLATFORM_CHECK_LABELS:
            continue
        ok = bool(row.get("ok"))
        rows.append(
            {
                "check_id": check_id,
                "label": str(row.get("label") or BROADCAST_PLATFORM_CHECK_LABELS[check_id]),
                "kind": str(row.get("kind") or "manual_platform"),
                "ready": ok and str(row.get("kind") or "") == "real_platform",
                "state": "ready" if ok else "needs_real_platform_evidence",
                "action": str(row.get("action") or BROADCAST_PLATFORM_CHECK_ACTIONS[check_id]),
                "evidence": dict(row.get("evidence") or {}) if isinstance(row.get("evidence"), Mapping) else {},
            }
        )
    rows.sort(key=lambda item: list(BROADCAST_PLATFORM_CHECK_LABELS).index(str(item.get("check_id"))))
    return rows


def _broadcast_platform_summary(report: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = max(len(BROADCAST_PLATFORM_CHECK_LABELS), len(rows))
    ready = sum(1 for row in rows if row.get("ready"))
    pending = max(0, target - ready)
    return {
        "target": target,
        "ready": ready,
        "pending": pending,
        "real_platform_evidence": bool(report.get("real_platform_evidence")),
        "report_ok": bool(report.get("ok")),
    }


def _write_screenstudio_script(
    *,
    root: Path,
    out_dir: Path,
    rows: list[dict[str, Any]],
    capture_duration_ms: int,
) -> Path:
    script = out_dir / "record_screenstudio_sidecars.ps1"
    python = _python_command(root)
    manifest = root / "qa_corpus" / "screenstudio_real_recordings" / "manifest.json"
    lines = [
        "# Generated by tools/prepare_release_evidence_sprint.py",
        "# Replay each target recording and perform real cursor, click, drag, and hotkey actions.",
        "# This captures real .cursor.json files; templates/example events are not counted evidence.",
        "$ErrorActionPreference = 'Stop'",
        f"$Python = {_ps_quote(python)}",
        f"$Manifest = {_ps_quote(manifest)}",
        f"Set-Location {_ps_quote(root)}",
        "",
    ]
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        video = str(row.get("path") or "")
        slot = str(row.get("slot_id") or "")
        duration = _safe_int(row.get("duration_ms"), capture_duration_ms)
        if duration <= 0:
            duration = capture_duration_ms
        frame_w = max(1, _safe_int(row.get("frame_w"), 1920))
        frame_h = max(1, _safe_int(row.get("frame_h"), 1080))
        lines.extend(
            [
                f"Write-Host '[{idx}/{total}] Capture sidecar for {slot or Path(video).name}'",
                f"if (Test-Path {_ps_quote(video)}) {{",
                f"  Start-Process -FilePath {_ps_quote(video)}",
                "  Read-Host 'Press Enter when the recording is visible and you are ready to replay real cursor actions'",
                "  & $Python 'tools/record_screenstudio_cursor_sidecar.py' "
                f"--video {_ps_quote(video)} "
                f"--duration-ms {duration} "
                f"--frame-w {frame_w} --frame-h {frame_h} "
                "--capture-hotkeys --register --manifest $Manifest "
                f"--slot-id {_ps_quote(slot)}",
                "} else {",
                f"  Write-Warning 'Missing video: {video.replace(chr(39), chr(39) + chr(39))}'",
                "}",
                "",
            ]
        )
    script.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return script


def _write_ai_script(*, root: Path, out_dir: Path, rows: list[dict[str, Any]]) -> Path:
    script = out_dir / "register_ai_real_cases.ps1"
    python = _python_command(root)
    lines = [
        "# Generated by tools/prepare_release_evidence_sprint.py",
        "# Fill each AI template with a real transcript and natural-language prompt before running.",
        "# Registration rejects placeholder prompts and missing transcripts.",
        "$ErrorActionPreference = 'Stop'",
        f"$Python = {_ps_quote(python)}",
        f"Set-Location {_ps_quote(root)}",
        "",
    ]
    total = len(rows)
    if total <= 0:
        lines.extend(
            [
                "# No pending AI real-case templates were selected.",
                "# Standard registration tool: tools/register_ai_edit_corpus_case.py",
                "Write-Host 'All selected AI edit corpus cases are already registered.'",
                "",
            ]
        )
    for idx, row in enumerate(rows, start=1):
        template = str(row.get("template_path") or "")
        lines.extend(
            [
                f"Write-Host '[{idx}/{total}] Register AI real case {row.get('case_id') or ''}'",
                "  & $Python 'tools/register_ai_edit_corpus_case.py' "
                f"--from-template {_ps_quote(template)} --overwrite",
                "",
            ]
        )
    script.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return script


def _write_broadcast_script(*, root: Path, out_dir: Path, rows: list[dict[str, Any]]) -> Path:
    script = out_dir / "register_broadcast_platform_evidence.ps1"
    python = _python_command(root)
    lines = [
        "# Generated by tools/prepare_release_evidence_sprint.py",
        "# Register only redacted real platform evidence. Do not paste stream keys or tokens.",
        "$ErrorActionPreference = 'Stop'",
        f"$Python = {_ps_quote(python)}",
        f"Set-Location {_ps_quote(root)}",
        "",
    ]
    pending = [row for row in rows if not row.get("ready")]
    total = len(pending)
    for idx, row in enumerate(pending, start=1):
        check_id = str(row.get("check_id") or "")
        label = str(row.get("label") or BROADCAST_PLATFORM_CHECK_LABELS.get(check_id, check_id))
        default_platform = "Discord" if check_id == "discord_window_share" else "YouTube/Twitch/Custom RTMP"
        lines.extend(
            [
                f"Write-Host '[{idx}/{total}] Register broadcast evidence: {label}'",
                f"Write-Host {_ps_quote(str(row.get('action') or BROADCAST_PLATFORM_CHECK_ACTIONS.get(check_id, 'Attach redacted real platform evidence.')))}",
                f"$Platform = Read-Host 'Platform tested ({default_platform})'",
                "$EvidencePath = Read-Host 'Path to redacted screenshot/log/video evidence (optional if notes are detailed)'",
                "$Notes = Read-Host 'Redacted notes, no stream keys/tokens'",
                "if ([string]::IsNullOrWhiteSpace($Platform)) { throw 'Platform is required.' }",
                "if ([string]::IsNullOrWhiteSpace($EvidencePath) -and [string]::IsNullOrWhiteSpace($Notes)) { throw 'Evidence path or notes are required.' }",
                "& $Python 'tools/register_broadcast_platform_evidence.py' "
                f"--check-id {_ps_quote(check_id)} "
                "--platform $Platform --evidence-path $EvidencePath --notes $Notes --confirm-redacted",
                "",
            ]
        )
    if not pending:
        lines.append("Write-Host 'All broadcast platform evidence rows are already registered.'")
    lines.extend(
        [
            "Write-Host ''",
            "Write-Host 'Broadcast evidence registration finished. Run Refresh Evidence Status in TigerCapture.'",
            "",
        ]
    )
    script.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return script


def _write_playbook(
    *,
    out_dir: Path,
    screenstudio_script: Path,
    ai_script: Path,
    broadcast_script: Path,
    screenstudio_rows: list[dict[str, Any]],
    ai_rows: list[dict[str, Any]],
    broadcast_rows: list[dict[str, Any]],
) -> Path:
    path = out_dir / "README.md"
    broadcast_pending = [row for row in broadcast_rows if not row.get("ready")]
    lines = [
        "# Release Evidence Sprint",
        "",
        "This folder is a collection plan, not proof by itself.",
        "",
        "## Screen Studio corpus",
        "",
        f"- Selected recordings: {len(screenstudio_rows)}",
        f"- Capture script: `{screenstudio_script.name}`",
        "- Run the script while replaying each target recording and reproducing real cursor actions.",
        "- The recorder captures cursor movement, clicks, drags, releases, and modifier hotkeys.",
        "- Re-run `tools/qa_screenstudio_real_recording_corpus.py` after capture.",
        "",
        "## AI edit corpus",
        "",
        f"- Selected AI templates: {len(ai_rows)}",
        f"- Registration script: `{ai_script.name}`",
        "- Fill templates with real transcripts, prompts, expected intent, and expected operations.",
        "- Re-run `tools/qa_ai_edit_corpus_quality.py --use-provider` after registration.",
        "",
        "## Broadcast platform evidence",
        "",
        f"- Pending platform checks: {len(broadcast_pending)}",
        f"- Registration script: `{broadcast_script.name}`",
        "- Run a private/unlisted RTMP ingest and a Discord/video-call Program Output share.",
        "- Register only redacted evidence; never paste stream keys, passwords, or tokens.",
        "- Re-run `tools/qa_broadcast_platform_e2e.py` and `tools/qa_broadcast_release_readiness.py` after registration.",
        "",
        "## Guardrail",
        "",
        "Do not copy example events or placeholder prompts into counted QA data.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _screenstudio_requirement_breakdown(screen: Mapping[str, Any], *, target: int) -> dict[str, dict[str, Any]]:
    """Return per-interaction evidence counts for Screen Studio replacement claims."""

    target = max(1, int(target or 20))
    sidecar_ready = _safe_int(screen.get("cursor_sidecar_ready"), 0)
    ready_counts = {
        "cursor_sidecar": sidecar_ready,
        "click": _safe_int(screen.get("click_ready"), 0),
        "drag": _safe_int(screen.get("drag_ready"), 0),
        "hotkey": _safe_int(screen.get("hotkey_ready"), 0),
        "auto_zoom": _safe_int(screen.get("auto_zoom_ready"), 0),
    }
    explicit_needs = {
        "cursor_sidecar": screen.get("needs_sidecar"),
        "click": screen.get("needs_click"),
        "drag": screen.get("needs_drag"),
        "hotkey": screen.get("needs_hotkey"),
        "auto_zoom": screen.get("needs_auto_zoom"),
    }
    breakdown: dict[str, dict[str, Any]] = {}
    for key, label in SCREENSTUDIO_REQUIREMENT_LABELS.items():
        ready = max(0, min(target, _safe_int(ready_counts.get(key), 0)))
        explicit = explicit_needs.get(key)
        if explicit is None:
            needed = max(0, target - ready)
        else:
            needed = max(0, min(target, _safe_int(explicit, 0)))
        breakdown[key] = {
            "label": label,
            "ready": ready,
            "target": target,
            "needed": needed,
            "percent": _progress_percent(ready, target),
            "action": SCREENSTUDIO_REQUIREMENT_ACTIONS[key],
        }
    return breakdown


def release_evidence_next_items(report: Mapping[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    """Return the next concrete user tasks required to turn generated plans into proof.

    Generated scripts/templates are useful scaffolding, but not evidence.  This queue
    points at the real recordings and AI templates that still need human data.
    """

    data = dict(report or {})
    items: list[dict[str, Any]] = []
    screen_rows = [
        dict(row)
        for row in list(((data.get("screenstudio") or {}).get("selected_rows", []) or []))
        if isinstance(row, Mapping)
    ]
    for row in screen_rows:
        missing = [str(item) for item in list(row.get("missing_requirements") or []) if str(item).strip()]
        if not missing:
            continue
        actions = [
            SCREENSTUDIO_REQUIREMENT_ACTIONS.get(req, f"Collect real {req} evidence.")
            for req in missing
        ]
        priority = 10
        if "cursor_sidecar" in missing:
            priority = 0
        elif "click" in missing:
            priority = 1
        elif "drag" in missing or "hotkey" in missing:
            priority = 2
        elif "auto_zoom" in missing:
            priority = 3
        items.append(
            {
                "kind": "screenstudio_interaction_evidence",
                "priority": priority,
                "slot_id": str(row.get("slot_id") or ""),
                "path": str(row.get("path") or ""),
                "state": str(row.get("state") or "needs_work"),
                "missing_requirements": missing,
                "summary": (
                    f"{row.get('slot_id') or Path(str(row.get('path') or '')).name}: "
                    + ", ".join(SCREENSTUDIO_REQUIREMENT_LABELS.get(req, req) for req in missing)
                ),
                "next_actions": actions,
                "duration_ms": _safe_int(row.get("duration_ms"), 0),
                "frame_w": max(1, _safe_int(row.get("frame_w"), 1920)),
                "frame_h": max(1, _safe_int(row.get("frame_h"), 1080)),
                "command": str(row.get("sidecar_capture_command") or ""),
                "target_sidecar_path": str(row.get("target_sidecar_path") or ""),
                "template_path": str(row.get("template_path") or ""),
            }
        )

    ai_rows = [
        dict(row)
        for row in list(((data.get("ai") or {}).get("selected_rows", []) or []))
        if isinstance(row, Mapping)
    ]
    for row in ai_rows:
        if row.get("ready"):
            continue
        items.append(
            {
                "kind": "ai_real_edit_case",
                "priority": 20 + _safe_int(row.get("index"), 999),
                "case_id": str(row.get("case_id") or ""),
                "state": str(row.get("state") or "needs_real_case"),
                "summary": f"{row.get('case_id') or 'AI case'}: fill real transcript/prompt/expected operations",
                "next_actions": [
                    "Fill this template with a real transcript and natural-language edit request.",
                    "Register it with tools/register_ai_edit_corpus_case.py before rerunning AI corpus QA.",
                ],
                "template_path": str(row.get("template_path") or ""),
                "command": str(row.get("registration_command") or ""),
            }
        )

    broadcast_rows = [
        dict(row)
        for row in list(((data.get("broadcast") or {}).get("selected_rows", []) or []))
        if isinstance(row, Mapping)
    ]
    for row in broadcast_rows:
        if row.get("ready"):
            continue
        check_id = str(row.get("check_id") or "")
        items.append(
            {
                "kind": "broadcast_platform_evidence",
                "priority": 50 + list(BROADCAST_PLATFORM_CHECK_LABELS).index(check_id)
                if check_id in BROADCAST_PLATFORM_CHECK_LABELS
                else 59,
                "check_id": check_id,
                "state": str(row.get("state") or "needs_real_platform_evidence"),
                "summary": f"{BROADCAST_PLATFORM_CHECK_LABELS.get(check_id, check_id or 'broadcast')}: attach redacted real platform evidence",
                "next_actions": [
                    BROADCAST_PLATFORM_CHECK_ACTIONS.get(check_id, "Attach redacted real platform evidence."),
                    "Register it with tools/register_broadcast_platform_evidence.py --confirm-redacted.",
                ],
                "label": str(row.get("label") or BROADCAST_PLATFORM_CHECK_LABELS.get(check_id, check_id)),
                "command": (
                    "python tools/register_broadcast_platform_evidence.py "
                    f"--check-id {check_id} --platform <platform> "
                    "--evidence-path <redacted-evidence> --notes <redacted-notes> --confirm-redacted"
                ),
            }
        )

    def _priority(item: Mapping[str, Any]) -> int:
        try:
            return int(item.get("priority", 999))
        except Exception:
            return 999

    items.sort(key=lambda item: (_priority(item), str(item.get("slot_id") or item.get("case_id") or "")))
    if limit > 0:
        return items[:limit]
    return items


def release_evidence_next_screenstudio_capture_target(
    report: Mapping[str, Any],
    *,
    root: str | Path = ".",
    capture_duration_ms: int = 60_000,
    write_file: bool = True,
) -> dict[str, Any]:
    """Write a one-slot Screen Studio cursor capture script for the next work item."""

    root_path = Path(root).resolve()
    data = dict(report or {})
    out_raw = str(data.get("out_dir") or DEFAULT_OUT_DIR).strip()
    out_dir = Path(out_raw) if out_raw else DEFAULT_OUT_DIR
    if not out_dir.is_absolute():
        out_dir = root_path / out_dir
    work_items = [
        item
        for item in release_evidence_next_items(data, limit=0)
        if str(item.get("kind") or "") == "screenstudio_interaction_evidence"
    ]
    if not work_items:
        return {
            "ok": False,
            "label": "Record next Screen Studio slot",
            "kind": "powershell",
            "path": str(out_dir / "record_next_screenstudio_sidecar.ps1"),
            "exists": False,
            "requires_user": True,
            "reason": "no_screenstudio_interaction_work",
        }
    item = work_items[0]
    video = str(item.get("path") or "").strip()
    slot = str(item.get("slot_id") or "").strip()
    duration = _safe_int(item.get("duration_ms"), capture_duration_ms)
    if duration <= 0:
        duration = max(1000, _safe_int(capture_duration_ms, 60_000))
    frame_w = max(1, _safe_int(item.get("frame_w"), 1920))
    frame_h = max(1, _safe_int(item.get("frame_h"), 1080))
    manifest = root_path / "qa_corpus" / "screenstudio_real_recordings" / "manifest.json"
    script = out_dir / "record_next_screenstudio_sidecar.ps1"
    if write_file:
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Generated by app.release_evidence_sprint.release_evidence_next_screenstudio_capture_target",
            "# Captures exactly one real Screen Studio interaction sidecar. It does not fake evidence.",
            "$ErrorActionPreference = 'Stop'",
            f"$Python = {_ps_quote(_python_command(root_path))}",
            f"$Manifest = {_ps_quote(manifest)}",
            f"$Video = {_ps_quote(video)}",
            f"$Slot = {_ps_quote(slot)}",
            f"$DurationMs = {duration}",
            f"$FrameW = {frame_w}",
            f"$FrameH = {frame_h}",
            f"Set-Location {_ps_quote(root_path)}",
            "",
            "Write-Host \"Next Screen Studio evidence slot: $Slot\"",
            "Write-Host \"Video: $Video\"",
            f"Write-Host \"Missing proof: {', '.join(str(x) for x in list(item.get('missing_requirements') or []))}\"",
            "if (!(Test-Path $Video)) {",
            "  Write-Warning \"Video is missing. Fix the manifest path before recording this slot.\"",
            "  Read-Host 'Press Enter to close'",
            "  exit 1",
            "}",
            "Start-Process -FilePath $Video",
            "Read-Host 'When the video is visible, press Enter, then replay real cursor clicks, drags, and hotkeys'",
            "& $Python 'tools/record_screenstudio_cursor_sidecar.py' --video $Video --duration-ms $DurationMs --frame-w $FrameW --frame-h $FrameH --capture-hotkeys --register --manifest $Manifest --slot-id $Slot",
            "Write-Host ''",
            "Write-Host 'Capture finished. Run Refresh Evidence Status in TigerCapture to update the QA gate.'",
            "Read-Host 'Press Enter to close'",
            "",
        ]
        script.write_text("\n".join(lines), encoding="utf-8-sig")
    return {
        "ok": True,
        "label": f"Record next slot {slot or Path(video).name}",
        "kind": "powershell",
        "path": str(script),
        "exists": script.exists(),
        "requires_user": True,
        "slot_id": slot,
        "video": video,
        "duration_ms": duration,
        "frame_w": frame_w,
        "frame_h": frame_h,
        "missing_requirements": list(item.get("missing_requirements") or []),
        "note": "Opens a visible terminal for one recording; perform real cursor, click, drag, and hotkey actions.",
    }


def release_evidence_next_ai_case_target(
    report: Mapping[str, Any],
    *,
    root: str | Path = ".",
    write_file: bool = True,
) -> dict[str, Any]:
    """Write a one-slot AI real-case registration script for the next template."""

    root_path = Path(root).resolve()
    data = dict(report or {})
    out_raw = str(data.get("out_dir") or DEFAULT_OUT_DIR).strip()
    out_dir = Path(out_raw) if out_raw else DEFAULT_OUT_DIR
    if not out_dir.is_absolute():
        out_dir = root_path / out_dir
    work_items = [
        item
        for item in release_evidence_next_items(data, limit=0)
        if str(item.get("kind") or "") == "ai_real_edit_case"
    ]
    if not work_items:
        return {
            "ok": False,
            "label": "Register next AI real case",
            "kind": "powershell",
            "path": str(out_dir / "register_next_ai_real_case.ps1"),
            "exists": False,
            "requires_user": True,
            "reason": "no_ai_real_case_work",
        }
    item = work_items[0]
    template = str(item.get("template_path") or "").strip()
    case_id = str(item.get("case_id") or "").strip()
    script = out_dir / "register_next_ai_real_case.ps1"
    if write_file:
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Generated by app.release_evidence_sprint.release_evidence_next_ai_case_target",
            "# Registers exactly one filled real AI edit case. It does not accept placeholders.",
            "$ErrorActionPreference = 'Stop'",
            f"$Python = {_ps_quote(_python_command(root_path))}",
            f"$Template = {_ps_quote(template)}",
            f"$CaseId = {_ps_quote(case_id)}",
            f"Set-Location {_ps_quote(root_path)}",
            "",
            "Write-Host \"Next AI real case: $CaseId\"",
            "Write-Host \"Template: $Template\"",
            "if (!(Test-Path $Template)) {",
            "  Write-Warning \"Template is missing. Regenerate the release evidence sprint first.\"",
            "  Read-Host 'Press Enter to close'",
            "  exit 1",
            "}",
            "$TranscriptPath = Read-Host 'Real transcript path (.srt/.vtt/.txt)'",
            "$Prompt = Read-Host 'Natural-language edit request (3+ words)'",
            "$SourceMediaPath = Read-Host 'Source media path (optional)'",
            "$Notes = Read-Host 'Reviewer notes (optional)'",
            "$Confirm = Read-Host 'Type YES to confirm this is real user/project evidence and expected operations were reviewed'",
            "if (!(Test-Path $TranscriptPath)) { throw 'Transcript file is required and must exist.' }",
            "if ([string]::IsNullOrWhiteSpace($Prompt)) { throw 'Natural-language prompt is required.' }",
            "if ($Confirm -ne 'YES') { throw 'Confirmation is required before registering real AI evidence.' }",
            "$TemplateJson = Get-Content -Raw -Encoding UTF8 $Template | ConvertFrom-Json",
            "$TemplateJson.manifest_case.transcript_path = $TranscriptPath",
            "$TemplateJson.manifest_case.prompt = $Prompt",
            "if (![string]::IsNullOrWhiteSpace($SourceMediaPath)) { $TemplateJson.manifest_case.source_media_path = $SourceMediaPath }",
            "if (![string]::IsNullOrWhiteSpace($Notes)) { $TemplateJson.manifest_case.notes = $Notes }",
            "$TemplateJson.acceptance_checklist.real_user_project = $true",
            "$TemplateJson.acceptance_checklist.transcript_or_asr_available = $true",
            "$TemplateJson.acceptance_checklist.prompt_is_natural_language = $true",
            "$TemplateJson.acceptance_checklist.expected_operations_reviewed = $true",
            "$TemplateJson | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $Template",
            "& $Python 'tools/register_ai_edit_corpus_case.py' --from-template $Template --overwrite",
            "Write-Host ''",
            "Write-Host 'AI case registration finished. Run Refresh Evidence Status in TigerCapture to update the QA gate.'",
            "Read-Host 'Press Enter to close'",
            "",
        ]
        script.write_text("\n".join(lines), encoding="utf-8-sig")
    return {
        "ok": True,
        "label": f"Register next AI case {case_id or Path(template).name}",
        "kind": "powershell",
        "path": str(script),
        "exists": script.exists(),
        "requires_user": True,
        "case_id": case_id,
        "template_path": template,
        "note": "Prompts for a real transcript path and natural-language edit request, then registers one filled case.",
    }


def build_release_evidence_sprint(
    root: str | Path = ".",
    *,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    write_files: bool = False,
    max_screenstudio: int = 20,
    max_ai: int = 20,
    capture_duration_ms: int = 60_000,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = root_path / out_path
    sidecar_template_dir = out_path / "screenstudio_sidecar_templates"
    ai_template_dir = out_path / "ai_edit_templates"
    screenstudio_limit = max(0, int(max_screenstudio or 0))
    ai_limit = max(0, int(max_ai or 0))
    ai_deferred = ai_limit <= 0

    from app.ai_edit_corpus_intake import build_ai_edit_corpus_intake_report
    from app.screenstudio_parity import screenstudio_real_recording_corpus_report
    from app.screenstudio_sidecar_intake import build_screenstudio_sidecar_intake_report

    real_corpus = screenstudio_real_recording_corpus_report(deep_probe=False)
    sidecar_intake = build_screenstudio_sidecar_intake_report(
        real_corpus_report=real_corpus,
        template_dir=sidecar_template_dir,
        write_templates=bool(write_files),
        max_templates=screenstudio_limit,
    )
    if ai_deferred:
        ai_intake = {
            "ok": True,
            "summary": {
                "target_min": 0,
                "real_cases": 0,
                "ready_real_cases": 0,
                "missing_real_cases": 0,
                "templates_written": 0,
            },
            "rows": [],
            "next_actions": ["AI evidence collection deferred for this sprint."],
        }
    else:
        ai_intake = build_ai_edit_corpus_intake_report(
            target_min=max(1, ai_limit),
            template_dir=ai_template_dir,
            write_templates=bool(write_files),
        )
    broadcast_report = _broadcast_platform_report(root_path)
    broadcast_rows = _broadcast_platform_rows(broadcast_report)
    broadcast_summary = _broadcast_platform_summary(broadcast_report, broadcast_rows)

    screen_rows = _screenstudio_rows(sidecar_intake, limit=screenstudio_limit)
    ai_rows = [] if ai_deferred else _ai_template_rows(ai_intake, limit=ai_limit)
    scripts: dict[str, str] = {}
    playbook = ""
    if write_files:
        out_path.mkdir(parents=True, exist_ok=True)
        screen_script = _write_screenstudio_script(
            root=root_path,
            out_dir=out_path,
            rows=screen_rows,
            capture_duration_ms=max(1000, int(capture_duration_ms or 60_000)),
        )
        ai_script = _write_ai_script(root=root_path, out_dir=out_path, rows=ai_rows)
        broadcast_script = _write_broadcast_script(root=root_path, out_dir=out_path, rows=broadcast_rows)
        playbook_path = _write_playbook(
            out_dir=out_path,
            screenstudio_script=screen_script,
            ai_script=ai_script,
            broadcast_script=broadcast_script,
            screenstudio_rows=screen_rows,
            ai_rows=ai_rows,
            broadcast_rows=broadcast_rows,
        )
        scripts = {
            "screenstudio_sidecar_capture": str(screen_script),
            "ai_real_case_registration": str(ai_script),
            "broadcast_platform_registration": str(broadcast_script),
        }
        playbook = str(playbook_path)

    sidecar_summary = dict(sidecar_intake.get("summary") or {})
    ai_summary = dict(ai_intake.get("summary") or {})
    report = {
        "kind": "release_evidence_sprint",
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "write_files": bool(write_files),
        "ai_deferred": bool(ai_deferred),
        "claim_unblocked_by_sprint": False,
        "out_dir": str(out_path),
        "summary": {
            "screenstudio_selected": len(screen_rows),
            "screenstudio_ready": _safe_int(sidecar_summary.get("ready"), 0),
            "screenstudio_needs_sidecar": _safe_int(sidecar_summary.get("needs_sidecar"), 0),
            "screenstudio_templates_written": _safe_int(sidecar_summary.get("templates_written"), 0),
            "ai_selected": len(ai_rows),
            "ai_real_cases": _safe_int(ai_summary.get("real_cases"), 0),
            "ai_missing_real_cases": _safe_int(ai_summary.get("missing_real_cases"), 0),
            "ai_templates_written": _safe_int(ai_summary.get("templates_written"), 0),
            "broadcast_platform_ready": _safe_int(broadcast_summary.get("ready"), 0),
            "broadcast_platform_pending": _safe_int(broadcast_summary.get("pending"), 0),
        },
        "scripts": scripts,
        "playbook": playbook,
        "screenstudio": {
            "summary": sidecar_summary,
            "selected_rows": screen_rows,
            "next_actions": list(sidecar_intake.get("next_actions") or []),
        },
        "ai": {
            "summary": ai_summary,
            "selected_rows": ai_rows,
            "next_actions": list(ai_intake.get("next_actions") or []),
        },
        "broadcast": {
            "summary": broadcast_summary,
            "selected_rows": broadcast_rows,
            "next_actions": [
                BROADCAST_PLATFORM_CHECK_ACTIONS.get(str(row.get("check_id") or ""), "Attach redacted real platform evidence.")
                for row in broadcast_rows
                if not row.get("ready")
            ],
            "source_report": {
                "real_platform_evidence": bool(broadcast_report.get("real_platform_evidence")),
                "ok": bool(broadcast_report.get("ok")),
                "summary": dict(broadcast_report.get("summary") or {}),
            },
        },
        "next_actions": [
            "Run tools/prepare_release_evidence_sprint.py --write-files to create scripts and templates.",
            "Run debugCapture/release_evidence_sprint/record_screenstudio_sidecars.ps1 and perform real cursor actions.",
            "Fill AI templates with real transcripts/prompts, then run register_ai_real_cases.ps1.",
            "Run debugCapture/release_evidence_sprint/register_broadcast_platform_evidence.ps1 after private RTMP and Discord checks.",
            "Run tools/qa_release_gap_closure.py --strict after evidence is collected.",
        ],
    }
    report["progress"] = release_evidence_progress(report)
    report["work_queue"] = release_evidence_next_items(report, limit=0)
    return report


def _progress_percent(ready: int, target: int) -> int:
    if target <= 0:
        return 100 if ready > 0 else 0
    return max(0, min(100, int(round((max(0, ready) / max(1, target)) * 100))))


def release_evidence_progress(report: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize real-evidence progress without counting generated templates."""

    data = dict(report or {})
    summary = dict(data.get("summary") or {})
    screen = dict((data.get("screenstudio") or {}).get("summary") or {})
    ai = dict((data.get("ai") or {}).get("summary") or {})
    broadcast = dict((data.get("broadcast") or {}).get("summary") or {})
    ai_deferred = bool(data.get("ai_deferred"))

    screen_target = max(
        20,
        _safe_int(screen.get("target_min"), 0),
        min(_safe_int(summary.get("screenstudio_selected"), 0), _safe_int(screen.get("recordings"), 0) or 0),
    )
    screen_sidecar_ready = _safe_int(
        screen.get("cursor_sidecar_ready"),
        _safe_int(summary.get("screenstudio_ready"), 0),
    )
    screen_interaction_ready = max(
        _safe_int(screen.get("interaction_ready"), 0),
        _safe_int(screen.get("full_interaction_ready"), 0),
    )
    screen_needed = max(0, screen_target - screen_interaction_ready)
    screen_requirements = _screenstudio_requirement_breakdown(screen, target=screen_target)

    ai_target = 0 if ai_deferred else max(20, _safe_int(ai.get("target_min"), 0), _safe_int(summary.get("ai_selected"), 0))
    ai_ready = 0 if ai_deferred else max(_safe_int(ai.get("ready_real_cases"), 0), _safe_int(summary.get("ai_real_cases"), 0))
    ai_needed = max(0, ai_target - ai_ready)
    broadcast_target = max(
        len(BROADCAST_PLATFORM_CHECK_LABELS),
        _safe_int(broadcast.get("target"), 0),
    )
    broadcast_ready = max(
        _safe_int(broadcast.get("ready"), 0),
        _safe_int(summary.get("broadcast_platform_ready"), 0),
    )
    broadcast_needed = max(0, broadcast_target - broadcast_ready)

    screen_pct = _progress_percent(screen_interaction_ready, screen_target)
    ai_pct = _progress_percent(ai_ready, ai_target)
    broadcast_pct = _progress_percent(broadcast_ready, broadcast_target)
    percent_parts = [screen_pct, broadcast_pct]
    if not ai_deferred:
        percent_parts.append(ai_pct)
    overall_pct = int(round(sum(percent_parts) / max(1, len(percent_parts))))
    blockers: list[str] = []
    if screen_needed:
        blockers.append(f"needs_{screen_needed}_interaction_ready_cursor_sidecars")
    for key, row in screen_requirements.items():
        needed = _safe_int(row.get("needed"), 0)
        if needed:
            blockers.append(f"needs_{needed}_{key}")
    if ai_needed:
        blockers.append(f"needs_{ai_needed}_real_ai_edit_cases")
    if broadcast_needed:
        blockers.append(f"needs_{broadcast_needed}_broadcast_platform_evidence")
    blockers = list(dict.fromkeys(blockers))

    return {
        "overall_percent": overall_pct,
        "ready": not blockers,
        "blockers": blockers,
        "screenstudio": {
            "target": screen_target,
            "sidecar_ready": screen_sidecar_ready,
            "interaction_ready": screen_interaction_ready,
            "needed": screen_needed,
            "percent": screen_pct,
            "requirements": screen_requirements,
        },
        "ai": {
            "deferred": ai_deferred,
            "target": ai_target,
            "real_cases": ai_ready,
            "needed": ai_needed,
            "percent": ai_pct,
        },
        "broadcast": {
            "target": broadcast_target,
            "ready": broadcast_ready,
            "needed": broadcast_needed,
            "percent": broadcast_pct,
            "real_platform_evidence": bool(broadcast.get("real_platform_evidence")),
        },
    }


def release_evidence_action_targets(
    report: Mapping[str, Any],
    *,
    root: str | Path = ".",
) -> dict[str, dict[str, Any]]:
    """Return user-facing launch targets for a release evidence sprint report."""

    root_path = Path(root).resolve()
    data = dict(report or {})
    scripts = dict(data.get("scripts") or {})

    def _resolve(value: Any, fallback: str | Path) -> Path:
        raw = str(value or "").strip()
        path = Path(raw) if raw else Path(fallback)
        if not path.is_absolute():
            path = root_path / path
        return path

    out_dir = _resolve(data.get("out_dir"), DEFAULT_OUT_DIR)
    screen_script = _resolve(
        scripts.get("screenstudio_sidecar_capture"),
        out_dir / "record_screenstudio_sidecars.ps1",
    )
    ai_script = _resolve(
        scripts.get("ai_real_case_registration"),
        out_dir / "register_ai_real_cases.ps1",
    )
    broadcast_script = _resolve(
        scripts.get("broadcast_platform_registration"),
        out_dir / "register_broadcast_platform_evidence.ps1",
    )
    playbook = _resolve(data.get("playbook"), out_dir / "README.md")

    targets = {
        "screenstudio_sidecar_capture": {
            "label": "Record cursor sidecars",
            "kind": "powershell",
            "path": screen_script,
            "requires_user": True,
            "note": "Opens a visible terminal; replay real cursor, click, drag, and hotkey actions.",
        },
        "ai_real_case_registration": {
            "label": "Register AI real cases",
            "kind": "powershell",
            "path": ai_script,
            "requires_user": True,
            "note": "Fill AI templates first; registration rejects placeholders.",
        },
        "broadcast_platform_registration": {
            "label": "Register broadcast platform evidence",
            "kind": "powershell",
            "path": broadcast_script,
            "requires_user": True,
            "note": "Attach redacted RTMP/Discord platform evidence; never include stream keys or tokens.",
        },
        "playbook": {
            "label": "Open sprint playbook",
            "kind": "document",
            "path": playbook,
            "requires_user": False,
            "note": "Explains the capture and registration flow.",
        },
        "folder": {
            "label": "Open evidence folder",
            "kind": "folder",
            "path": out_dir,
            "requires_user": False,
            "note": "Contains scripts, templates, and the sprint README.",
        },
    }
    for target in targets.values():
        path = Path(target["path"])
        target["path"] = str(path)
        target["exists"] = path.exists()
    return targets
