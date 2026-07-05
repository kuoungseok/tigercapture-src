"""Commercial expansion helpers for the editor's next product layer.

This module stays Qt-free on purpose.  It provides small, concrete product
surfaces for the ten areas that are now beyond the closed TODO list: beta QA
bundles, preview engine capability UX, parity lock settings, one-click edit
planning, preset marketplace health, Color/Audio depth, project snapshots,
plugin manifests, and release readiness.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommercialArea:
    id: str
    label: str
    evidence: str
    user_value: str


COMMERCIAL_EXPANSION_AREAS: tuple[CommercialArea, ...] = (
    CommercialArea(
        "beta_feedback_mode",
        "실사용 베타 QA 모드",
        "app.commercial_expansion.export_beta_feedback_bundle",
        "사용자가 문제를 느낀 순간 프로젝트/로그/QA 상태를 한 번에 묶어 재현성을 높입니다.",
    ),
    CommercialArea(
        "preview_frame_server_ux",
        "Preview Frame Server / Hardware Decode UX",
        "app.preview_engine_status + app.video_decoder",
        "4K/긴 프로젝트에서 프리뷰 병목을 사용자가 이해하고 전환할 수 있게 합니다.",
    ),
    CommercialArea(
        "gpu_preview_export_parity_lock",
        "GPU Preview/Export Parity Lock",
        "project_settings.preview_export_parity_lock + professional readiness",
        "프리뷰와 최종 렌더가 달라지는 위험을 프로젝트 설정과 QA에서 명시합니다.",
    ),
    CommercialArea(
        "ai_one_click_edit_flow",
        "AI 원클릭 편집 플로우",
        "app.preset_library.one_click_preset_plan",
        "자동 컷/자막/효과/오디오/템플릿 적용 순서를 하나의 계획으로 보여줍니다.",
    ),
    CommercialArea(
        "preset_marketplace_management",
        "프리셋/템플릿 마켓형 관리",
        "app.preset_library.preset_pack_marketplace_report",
        "팩 품질, 충돌, 활성화 상태를 마켓 카드처럼 관리할 수 있게 합니다.",
    ),
    CommercialArea(
        "audio_postproduction_depth",
        "오디오 후반작업 강화",
        "app.audio_workflow + app.professional_readiness",
        "대화 정리, 라우팅, loudness, automation 준비 상태를 제품 진단으로 고정합니다.",
    ),
    CommercialArea(
        "color_node_workflow_depth",
        "컬러 노드 워크플로우",
        "app.color_page_window + app.workbench.node_graph",
        "Color Page 기능을 노드 기반 전문 워크플로우로 추적합니다.",
    ),
    CommercialArea(
        "project_version_snapshots",
        "프로젝트 버전/스냅샷",
        "app.commercial_expansion.create_project_snapshot",
        "중요 편집 지점의 프로젝트 파일을 해시와 함께 보관하고 되돌림 후보로 남깁니다.",
    ),
    CommercialArea(
        "plugin_script_api",
        "플러그인/스크립트 API",
        "app.commercial_expansion.discover_plugins",
        "외부 프리셋/자동화/QA hook을 검증 가능한 manifest로 받습니다.",
    ),
    CommercialArea(
        "release_productization",
        "릴리즈 제품화",
        "build.ps1 + installer specs + release metadata",
        "설치/업데이트/릴리즈 산출물을 제품 체크리스트에서 추적합니다.",
    ),
)


ALLOWED_PLUGIN_HOOKS = {
    "preset_pack",
    "timeline_command",
    "export_preflight",
    "qa_report",
    "media_import",
    "project_template",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _status(
    ok: bool,
    summary: str,
    *,
    score: int | None = None,
    actions: list[str] | None = None,
    artifacts: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "ok": bool(ok),
        "score": int(score if score is not None else (100 if ok else 60)),
        "summary": summary,
        "actions": actions or [],
        "artifacts": artifacts or [],
    }
    row.update(extra)
    return row


def export_beta_feedback_bundle(
    *,
    project_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Create a compact repro bundle manifest with safe local artifacts.

    The bundle intentionally copies only JSON/log/project files that already
    exist locally.  Heavy media stays referenced by path so a feedback export
    cannot accidentally duplicate a long capture.
    """
    base = Path(root) if root is not None else ROOT
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir is not None else base / "debugCapture" / "beta_feedback" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, Any]] = []
    runtime_log_files: tuple[Path, ...] = ()
    try:
        from app.paths import runtime_log_dir

        log_dir = runtime_log_dir()
        runtime_log_files = (
            log_dir / "recent_actions.jsonl",
            log_dir / "crash_report_latest.json",
        )
    except Exception:
        runtime_log_files = ()

    artifact_sources: list[tuple[str, Path]] = [
        ("debugCapture/productization_loop_qa.json", base / "debugCapture" / "productization_loop_qa.json"),
        ("debugCapture/commercial_expansion_qa.json", base / "debugCapture" / "commercial_expansion_qa.json"),
        ("debugCapture/visual_baseline_audit.json", base / "debugCapture" / "visual_baseline_audit.json"),
        ("debugCapture/color_audio_accuracy_qa.json", base / "debugCapture" / "color_audio_accuracy_qa.json"),
        ("debugCapture/preview_perf_report.json", base / "debugCapture" / "preview_perf_report.json"),
    ]
    artifact_sources.extend((f"runtime_logs/{path.name}", path) for path in runtime_log_files)
    for rel, src in artifact_sources:
        if not src.exists() or not src.is_file():
            continue
        dst = out_dir / rel.replace("/", "__").replace("\\", "__")
        shutil.copy2(src, dst)
        copied.append({"kind": "artifact", "source": str(src), "path": str(dst), "sha256": _sha256(dst)})

    project_info: dict[str, Any] = {}
    if project_path:
        src = Path(project_path)
        if src.exists() and src.is_file():
            dst = out_dir / f"project__{src.name}"
            shutil.copy2(src, dst)
            project_info = {"source": str(src), "path": str(dst), "sha256": _sha256(dst)}

    try:
        from app.preview_engine_status import preview_engine_status

        preview_status = preview_engine_status()
    except Exception as exc:
        preview_status = {"error": repr(exc)}

    manifest = {
        "ok": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
        "project": project_info,
        "preview_engine": preview_status,
        "copied": copied,
        "artifact_count": len(copied) + (1 if project_info else 0),
        "notes": [
            "Media files are referenced by the copied project; they are not duplicated into this lightweight bundle.",
            "Attach this folder with a short repro note when reporting a UI/preview/export issue.",
        ],
    }
    _write_json(out_dir / "feedback_bundle_manifest.json", manifest)
    return manifest


def beta_feedback_status(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    crash_reporter = base / "app" / "crash_reporter.py"
    crash_dialog = base / "app" / "crash_report_dialog.py"
    qa_dashboard = base / "app" / "qa_dashboard.py"
    try:
        from app.paths import runtime_log_dir

        has_recent_actions = (runtime_log_dir() / "recent_actions.jsonl").exists()
    except Exception:
        has_recent_actions = (base / "logs" / "recent_actions.jsonl").exists()
    ok = crash_reporter.exists() and crash_dialog.exists() and qa_dashboard.exists()
    return _status(
        ok,
        f"bundle exporter ready, recent actions {'present' if has_recent_actions else 'not yet present'}",
        score=100 if ok else 55,
        actions=[] if ok else ["Restore crash reporter, crash dialog, and QA Dashboard before beta feedback mode."],
        artifacts=[str(base / "debugCapture" / "beta_feedback")],
    )


def preview_frame_server_status(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    try:
        from app.preview_engine_status import preview_engine_status

        engine = preview_engine_status()
    except Exception as exc:
        engine = {"error": repr(exc)}
    video_decoder = (base / "app" / "video_decoder.py").exists()
    perf_tool = (base / "tools" / "qa_preview_perf.py").exists()
    frame_server_knob = "frame_server" in engine
    hw_knob = "hw_decode" in engine
    ok = video_decoder and perf_tool and frame_server_knob and hw_knob
    actions = []
    if ok:
        actions.append("Use TIGERCAPTURE_PREVIEW_DECODER_AUTO=1 for measured auto-selection on heavy projects.")
    else:
        actions.append("Restore video_decoder preview frame-server controls and preview performance QA.")
    return _status(
        ok,
        (
            f"decoder={'yes' if video_decoder else 'no'}, frame_server_knob={'yes' if frame_server_knob else 'no'}, "
            f"hw_decode_knob={'yes' if hw_knob else 'no'}"
        ),
        score=100 if ok else 60,
        actions=actions,
        engine=engine,
    )


def apply_gpu_parity_lock_settings(doc: dict[str, Any], *, enabled: bool = True) -> dict[str, Any]:
    """Stamp project settings for strict preview/export parity checks."""
    settings = doc.setdefault("project_settings", {})
    if not isinstance(settings, dict):
        settings = {}
        doc["project_settings"] = settings
    lock = {
        "enabled": bool(enabled),
        "mode": "strict-preview-export",
        "requires": [
            "shader_clip_fx",
            "preview_effect_prerender",
            "actor_overlay_bake",
            "color_lut_metadata_qa",
            "audio_mixdown_diagnostics",
        ],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    settings["preview_export_parity_lock"] = lock
    return lock


def gpu_parity_lock_status(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(doc or {})
    settings = _as_dict(payload.get("project_settings"))
    lock = _as_dict(settings.get("preview_export_parity_lock"))
    try:
        from app.professional_readiness import audit_gpu_preview_export_consistency

        audit = audit_gpu_preview_export_consistency(payload) if payload else {"score": 100, "parity_checks": []}
    except Exception as exc:
        audit = {"score": 0, "error": repr(exc), "parity_checks": []}
    configured = bool(lock.get("enabled"))
    ok = "error" not in audit
    actions = []
    if not configured:
        actions.append("Call apply_gpu_parity_lock_settings(project_doc) before release-sensitive exports.")
    return _status(
        ok,
        f"parity audit score {int(audit.get('score', 0) or 0)}, lock {'enabled' if configured else 'available'}",
        score=100 if ok and configured else (92 if ok else 50),
        actions=actions,
        lock=lock,
        audit=audit,
    )


def build_ai_one_click_edit_plan(project_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.preset_library import one_click_preset_plan
    from tools.qa_preset_application_corpus import preset_plan_export_parity

    summary = dict(project_summary or {
        "shortform": True,
        "tutorial": True,
        "screen_recording": True,
        "dialogue": True,
    })
    plan = one_click_preset_plan(summary)
    parity = preset_plan_export_parity(plan)
    steps = [
        {
            "index": idx + 1,
            "id": preset.id,
            "kind": preset.kind,
            "name": preset.name,
            "tags": list(preset.tags),
        }
        for idx, preset in enumerate(plan)
    ]
    return {
        "ok": bool(steps) and bool(parity.get("ok", True)),
        "summary": summary,
        "steps": steps,
        "step_count": len(steps),
        "export_parity": parity,
        "first_template": next((row for row in steps if row["kind"] == "template"), None),
    }


def one_click_status() -> dict[str, Any]:
    plan = build_ai_one_click_edit_plan()
    ok = bool(plan.get("ok")) and int(plan.get("step_count", 0) or 0) >= 5
    return _status(
        ok,
        f"{plan.get('step_count', 0)} planned step(s), parity={'ok' if _as_dict(plan.get('export_parity')).get('ok', True) else 'attention'}",
        score=100 if ok else 70,
        actions=[] if ok else ["Expand one-click plans so short-form/tutorial/dialogue projects receive template-first plans."],
        plan=plan,
    )


def marketplace_status() -> dict[str, Any]:
    from app.preset_library import preset_ecosystem_report, preset_pack_marketplace_report

    ecosystem = preset_ecosystem_report()
    marketplace = preset_pack_marketplace_report()
    packs = _as_list(marketplace.get("packs"))
    ok = bool(ecosystem.get("ok")) and int(ecosystem.get("score", 0) or 0) >= 90
    return _status(
        ok,
        f"ecosystem {ecosystem.get('score', 0)}/100, installed marketplace packs {len(packs)}",
        score=int(ecosystem.get("score", 0) or 0),
        actions=[] if ok else ["Open Preset Pack Manager and resolve invalid/conflicting packs."],
        ecosystem=ecosystem,
        marketplace=marketplace,
    )


def audio_post_status(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import numpy as np

        from app.audio_accuracy import audio_signal_diagnostics
        from app.audio_workflow import dialogue_cleanup_effects, loudness_target
        from app.professional_readiness import audit_audio_mix_readiness

        prepared_doc = doc or {
            "audio_tracks": [{
                "id": 1,
                "bus_id": "dialogue",
                "automation_points": [(0, 1.0), (1000, 0.85)],
                "clips": [{
                    "id": 1,
                    "offset_ms": 0,
                    "duration_ms": 3000,
                    "effects": {
                        **dialogue_cleanup_effects(strength=0.7),
                        "loudness": loudness_target("podcast").to_effect_payload(),
                    },
                }],
            }],
        }
        audit = audit_audio_mix_readiness(prepared_doc)
        pcm = np.full((480, 2), 0.12, dtype=np.float32)
        diag = audio_signal_diagnostics(pcm, target_lufs=-19.1, true_peak_limit_db=-1.0, tolerance_lufs=6.0)
        ok = int(audit.get("score", 0) or 0) >= 90
    except Exception as exc:
        audit = {"score": 0, "error": repr(exc)}
        diag = {}
        ok = False
    return _status(
        ok,
        f"audio readiness {int(audit.get('score', 0) or 0)}/100",
        score=int(audit.get("score", 0) or 0),
        actions=[] if ok else ["Apply dialogue cleanup, loudness targets, bus routing, and automation before delivery."],
        audit=audit,
        diagnostics=diag,
    )


def color_node_status(doc: dict[str, Any] | None = None, root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    try:
        from app.professional_readiness import audit_color_workflow_depth

        prepared_doc = doc or {
            "project_settings": {
                "color_management": {
                    "input_space": "sRGB",
                    "working_space": "ACEScg",
                    "output_space": "Rec.709",
                    "output_transfer": "bt709",
                    "preview_transform_enabled": True,
                },
            },
            "video_tracks": [{
                "clips": [{
                    "id": 1,
                    "timeline_in_ms": 0,
                    "source_in_ms": 0,
                    "source_out_ms": 1000,
                    "color_workflow": {
                        "qualifier": {"enabled": True, "softness": 0.12, "clean_black": 0.1},
                        "window": {"enabled": True, "track_object": True},
                        "curves": {"master": [(0, 0), (255, 255)]},
                    },
                }],
            }],
        }
        audit = audit_color_workflow_depth(prepared_doc)
        workbench_node_ui = (base / "app" / "workbench" / "node_graph" / "widget.py").exists()
        color_page = (base / "app" / "color_page_window.py").exists()
        ok = int(audit.get("score", 0) or 0) >= 85 and workbench_node_ui and color_page
    except Exception as exc:
        audit = {"score": 0, "error": repr(exc)}
        workbench_node_ui = False
        color_page = False
        ok = False
    return _status(
        ok,
        f"color readiness {int(audit.get('score', 0) or 0)}/100, node UI={'yes' if workbench_node_ui else 'no'}",
        score=100 if ok else int(audit.get("score", 0) or 0),
        actions=[] if ok else ["Use Color Page + Workbench node graph for secondary grade workflows."],
        audit=audit,
    )


def create_project_snapshot(
    project_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    label: str = "",
    root: str | Path | None = None,
) -> dict[str, Any]:
    src = Path(project_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(str(src))
    base = Path(root) if root is not None else ROOT
    snapshot_root = Path(output_dir) if output_dir is not None else base / "debugCapture" / "project_snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in (label or "manual")).strip("_") or "manual"
    dst = snapshot_root / f"{src.stem}__{stamp}__{safe_label}{src.suffix}"
    shutil.copy2(src, dst)
    row = {
        "ok": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "label": label or "manual",
        "source": str(src),
        "path": str(dst),
        "sha256": _sha256(dst),
        "size": dst.stat().st_size,
    }
    index_path = snapshot_root / "snapshots.json"
    index = _load_json(index_path)
    snapshots = _as_list(index.get("snapshots"))
    snapshots.append(row)
    _write_json(index_path, {"version": 1, "snapshots": snapshots[-200:]})
    return row


def list_project_snapshots(*, snapshot_dir: str | Path | None = None, root: str | Path | None = None) -> list[dict[str, Any]]:
    base = Path(root) if root is not None else ROOT
    folder = Path(snapshot_dir) if snapshot_dir is not None else base / "debugCapture" / "project_snapshots"
    return [row for row in _as_list(_load_json(folder / "snapshots.json").get("snapshots")) if isinstance(row, dict)]


def project_snapshot_status(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    snapshots = list_project_snapshots(root=base)
    recovery_ready = (base / "app" / "recovery_dialog.py").exists()
    ok = recovery_ready
    return _status(
        ok,
        f"{len(snapshots)} project snapshot(s), recovery UI={'yes' if recovery_ready else 'no'}",
        score=100 if ok else 55,
        actions=[] if ok else ["Restore Recovery dialog before relying on project snapshots."],
        snapshots=snapshots[-8:],
    )


def validate_plugin_manifest(data: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    plugin_id = str(data.get("id") or "").strip()
    name = str(data.get("name") or "").strip()
    version = str(data.get("version") or "").strip()
    hooks = _as_list(data.get("hooks"))
    if not plugin_id:
        issues.append({"severity": "high", "message": "Plugin manifest is missing id."})
    if not name:
        issues.append({"severity": "medium", "message": "Plugin manifest is missing display name."})
    if not version:
        issues.append({"severity": "medium", "message": "Plugin manifest is missing version."})
    if not hooks:
        issues.append({"severity": "low", "message": "Plugin manifest declares no hooks."})
    normalized_hooks: list[dict[str, Any]] = []
    for hook in hooks:
        hook = _as_dict(hook)
        kind = str(hook.get("kind") or "").strip()
        if kind not in ALLOWED_PLUGIN_HOOKS:
            issues.append({"severity": "high", "message": f"Unsupported plugin hook: {kind or '<empty>'}"})
        normalized_hooks.append({
            "kind": kind,
            "entry": str(hook.get("entry") or ""),
            "label": str(hook.get("label") or kind),
        })
    high = sum(1 for issue in issues if issue.get("severity") == "high")
    return {
        "ok": high == 0,
        "id": plugin_id,
        "name": name,
        "version": version,
        "hooks": normalized_hooks,
        "issues": issues,
    }


def discover_plugins(*, plugin_roots: Iterable[str | Path] | None = None, root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    roots = [Path(p) for p in plugin_roots] if plugin_roots is not None else [
        base / "plugins",
        base / "resources" / "plugins",
        base / "local_resources" / "plugins",
    ]
    rows: list[dict[str, Any]] = []
    for folder in roots:
        if not folder.exists():
            continue
        candidates = list(folder.glob("*/plugin.json")) + list(folder.glob("*.plugin.json"))
        for manifest_path in candidates:
            data = _load_json(manifest_path)
            row = validate_plugin_manifest(data)
            row["path"] = str(manifest_path)
            rows.append(row)
    issues = [issue for row in rows for issue in _as_list(row.get("issues")) if isinstance(issue, dict)]
    high = sum(1 for issue in issues if issue.get("severity") == "high")
    return {
        "ok": high == 0,
        "plugin_count": len(rows),
        "plugins": rows,
        "issues": issues,
        "allowed_hooks": sorted(ALLOWED_PLUGIN_HOOKS),
    }


def plugin_api_status(root: str | Path | None = None) -> dict[str, Any]:
    discovered = discover_plugins(root=root)
    ok = bool(discovered.get("ok")) and bool(ALLOWED_PLUGIN_HOOKS)
    return _status(
        ok,
        f"{discovered.get('plugin_count', 0)} plugin manifest(s), {len(ALLOWED_PLUGIN_HOOKS)} allowed hook kind(s)",
        score=100 if ok else 60,
        actions=[] if ok else ["Fix invalid plugin manifests before enabling script/plugin automation."],
        discovered=discovered,
    )


def release_productization_status(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    checks = {
        "build_script": (base / "build.ps1").exists(),
        "pyinstaller_spec": (base / "TigerCapture.spec").exists(),
        "inno_installer": (base / "installer.iss").exists(),
        "nsis_installer": (base / "installer.nsi").exists(),
        "version_info": (base / "version_info.txt").exists(),
        "native_worker_project": (base / "native" / "tigercapture_worker" / "Cargo.toml").exists(),
        "github_workflows": (base / ".github").exists(),
    }
    passed = sum(1 for value in checks.values() if value)
    ok = passed >= 6
    return _status(
        ok,
        f"release checklist {passed}/{len(checks)} present",
        score=100 if ok else int(round(100 * passed / max(1, len(checks)))),
        actions=[] if ok else ["Complete installer/build/version/native worker release wiring."],
        checks=checks,
    )


def build_commercial_expansion_report(
    *,
    project_doc: dict[str, Any] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    doc = dict(project_doc or {})
    parity_doc = dict(project_doc or {"project_settings": {}, "video_tracks": [], "audio_tracks": []})
    apply_gpu_parity_lock_settings(parity_doc, enabled=True)
    statuses = {
        "beta_feedback_mode": beta_feedback_status(base),
        "preview_frame_server_ux": preview_frame_server_status(base),
        "gpu_preview_export_parity_lock": gpu_parity_lock_status(parity_doc),
        "ai_one_click_edit_flow": one_click_status(),
        "preset_marketplace_management": marketplace_status(),
        "audio_postproduction_depth": audio_post_status(doc if doc else None),
        "color_node_workflow_depth": color_node_status(doc if doc else None, root=base),
        "project_version_snapshots": project_snapshot_status(base),
        "plugin_script_api": plugin_api_status(base),
        "release_productization": release_productization_status(base),
    }
    areas: list[dict[str, Any]] = []
    for area in COMMERCIAL_EXPANSION_AREAS:
        row = dict(statuses.get(area.id) or _status(False, "Area missing from report."))
        row.update({
            "id": area.id,
            "label": area.label,
            "evidence": area.evidence,
            "user_value": area.user_value,
        })
        areas.append(row)
    score = int(round(sum(int(row.get("score", 0) or 0) for row in areas) / max(1, len(areas))))
    attention = [row for row in areas if not row.get("ok")]
    return {
        "ok": not attention,
        "score": score,
        "summary": {
            "areas": len(areas),
            "passing": len(areas) - len(attention),
            "attention": len(attention),
        },
        "areas": areas,
        "next_actions": [action for row in attention for action in _as_list(row.get("actions"))][:12],
    }
