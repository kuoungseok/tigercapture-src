"""Release-gap closure report for the six current product priorities.

This module deliberately aggregates existing QA/readiness contracts instead of
redefining them.  The goal is to keep product claims honest: an area can have a
working implementation while still blocking a stronger marketing claim.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Mapping


AREA_ORDER = (
    "generative_ai_one_click",
    "screenstudio_real_recording_corpus",
    "preview_scrub_seek",
    "actor_model_compatibility",
    "release_productization",
    "ui_ux_polish",
)


FORBIDDEN_SUBSYSTEM_TOKENS = (
    "ar_pbr",
    "camera_solve",
    "depth/",
    "depth\\",
)


@dataclass(frozen=True)
class _Area:
    id: str
    label: str
    score: int
    ready: bool
    summary: str
    actions: tuple[str, ...]
    evidence: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        if self.ready:
            state = "ready"
        elif self.score >= 70:
            state = "attention"
        else:
            state = "blocked"
        return {
            "id": self.id,
            "label": self.label,
            "score": max(0, min(100, int(self.score))),
            "ready": bool(self.ready),
            "state": state,
            "summary": self.summary,
            "actions": list(self.actions),
            "evidence": dict(self.evidence),
        }


def _resolve(root: str | Path, path: str | Path) -> Path:
    root_path = Path(root).resolve()
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_path / candidate


def _load_json(root: str | Path, path: str | Path) -> dict[str, Any] | None:
    source = _resolve(root, path)
    if not source.exists():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return default


def _clean_actions(actions: Any, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    if isinstance(actions, str):
        raw = [actions]
    elif isinstance(actions, (list, tuple, set)):
        raw = [str(item) for item in actions if str(item).strip()]
    else:
        raw = list(fallback)
    cleaned: list[str] = []
    seen: set[str] = set()
    for action in raw + list(fallback):
        text = str(action).strip()
        if not text:
            continue
        lowered = text.casefold()
        if any(token in lowered for token in FORBIDDEN_SUBSYSTEM_TOKENS):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
    return tuple(cleaned[:8])


def _call(default: dict[str, Any] | None, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        payload = func()
    except Exception as exc:
        payload = dict(default or {})
        payload.setdefault("call_error", f"{type(exc).__name__}: {exc}")
        return payload
    return payload if isinstance(payload, dict) else dict(default or {})


def _claim_blockers(payload: Mapping[str, Any]) -> list[str]:
    blockers = payload.get("claim_blockers")
    if not blockers:
        blockers = payload.get("replacement_claim_blockers")
    if not blockers:
        blockers = payload.get("release_blockers")
    if isinstance(blockers, (list, tuple, set)):
        return [str(item) for item in blockers if str(item).strip()]
    return []


def _ai_area(root: str | Path) -> _Area:
    cached = _load_json(root, "debugCapture/ai_edit_corpus_quality_qa.json")

    def build_default() -> dict[str, Any]:
        from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report

        return build_ai_edit_corpus_quality_report(
            manifest_path=None,
            use_provider=False,
            env=os.environ,
            provider_timeout_seconds=None,
            provider_retries=0,
        )

    payload = cached or _call(cached, build_default)
    score = _safe_int(payload.get("score"), 0)
    safe_mvp = bool(payload.get("safe_mvp_ready") or payload.get("ok"))
    smart_ready = bool(payload.get("smart_edit_claim_ready"))
    provider = dict(payload.get("provider") or {})
    summary = dict(payload.get("summary") or {})
    blockers = _claim_blockers(payload)
    if safe_mvp and score < 75:
        score = 75
    actions = []
    if not smart_ready:
        actions.append("Run tools/prepare_release_evidence_sprint.py --write-files to create AI corpus collection scripts.")
        if any("provider" in item for item in blockers) or not provider.get("direct_generation_ready"):
            actions.append("Wire and exercise the selected AI provider with tools/qa_ai_edit_corpus_quality.py --use-provider.")
        if "real_user_corpus_below_min" in blockers or _safe_int(summary.get("real_cases"), 0) < _safe_int(summary.get("min_real_cases"), 20):
            actions.append("Add real Korean, English, tutorial, short-form, product, and long-video AI edit cases.")
        if "case_failures_present" in blockers:
            actions.append("Fix failing AI edit corpus cases before claiming smart one-click editing.")
        actions.append("Keep public copy at safe MVP wording until smart_edit_claim_ready is true.")
    return _Area(
        id="generative_ai_one_click",
        label="Generative AI one-click editing",
        score=score,
        ready=smart_ready,
        summary=(
            "Smart AI edit claim ready"
            if smart_ready
            else f"Safe MVP={safe_mvp}; smart claim blocked by {', '.join(blockers[:4]) or 'provider/corpus evidence'}."
        ),
        actions=_clean_actions(actions),
        evidence={
            "safe_mvp_ready": safe_mvp,
            "smart_edit_claim_ready": smart_ready,
            "claim_blockers": blockers,
            "provider": {
                "selected": provider.get("selected"),
                "effective": provider.get("effective"),
                "executor_wired": bool(provider.get("executor_wired")),
                "direct_generation_ready": bool(provider.get("direct_generation_ready")),
                "corpus_direct_successes": _safe_int(provider.get("corpus_direct_successes"), 0),
                "corpus_fallbacks": _safe_int(provider.get("corpus_fallbacks"), 0),
            },
            "summary": summary,
        },
    )


def _screenstudio_area(root: str | Path) -> _Area:
    cached = _load_json(root, "debugCapture/screenstudio_real_recording_corpus_qa.json")

    def build_current() -> dict[str, Any]:
        from app.screenstudio_parity import screenstudio_real_recording_corpus_report

        return screenstudio_real_recording_corpus_report(deep_probe=False)

    payload = _call(cached, build_current) if cached is None else cached
    summary = dict(payload.get("summary") or {})
    ready = bool(payload.get("replacement_claim_ready") or payload.get("real_world_ready"))
    score = _safe_int(payload.get("score"), 0)
    valid = _safe_int(summary.get("valid_files"), 0)
    target = _safe_int(summary.get("target_min"), 20)
    sidecars = _safe_int(summary.get("cursor_sidecar_ready"), 0)
    interactions = _safe_int(summary.get("interaction_ready"), 0)
    actions = list(payload.get("next_actions") or [])
    if not actions and not ready:
        actions = [
            "Run tools/prepare_release_evidence_sprint.py --write-files to create sidecar capture scripts.",
            "Attach counted .cursor.json sidecars to real recordings.",
            "Record real click, drag, hotkey, and auto-zoom evidence before claiming Screen Studio replacement.",
            "Run tools/qa_screenstudio_real_recording_corpus.py after filling sidecars.",
        ]
    elif not ready and not any("prepare_release_evidence_sprint" in action for action in actions):
        actions.insert(0, "Run tools/prepare_release_evidence_sprint.py --write-files to create sidecar capture scripts.")
    return _Area(
        id="screenstudio_real_recording_corpus",
        label="Screen Studio real recording corpus",
        score=score,
        ready=ready,
        summary=f"{valid}/{target} valid recordings, {sidecars} cursor sidecars, {interactions} interaction-ready.",
        actions=_clean_actions(actions),
        evidence={
            "replacement_claim_ready": ready,
            "replacement_claim_blockers": list(payload.get("replacement_claim_blockers") or []),
            "summary": summary,
        },
    )


def _preview_scrub_area(root: str | Path) -> _Area:
    cached = _load_json(root, "debugCapture/preview_scrub_readiness_qa.json")
    perf_path = _resolve(root, "debugCapture/preview_perf_report.json")

    def build_current() -> dict[str, Any]:
        from app.preview_scrub_readiness import build_preview_scrub_readiness_report

        return build_preview_scrub_readiness_report(perf_path)

    payload = dict(cached or {})
    if not payload and perf_path.exists():
        payload = _call(cached, build_current)
    summary = dict(payload.get("summary") or {})
    ready = bool(payload.get("release_scrub_claim_ready"))
    score = _safe_int(payload.get("score"), 0)
    blockers = _claim_blockers(payload)
    actions = []
    if not ready:
        if "release_coverage_missing" in blockers or summary.get("missing_release_coverage"):
            actions.append("Add preview perf coverage for basic, mask/filter, nested, actor, audio, long, and 4K projects.")
        if "scrub_blockers_present" in blockers:
            actions.append("Fix blocked scrub projects and rerun tools/qa_preview_scrub_readiness.py.")
        if "score_below_release_threshold" in blockers:
            actions.append("Profile top seek hotspots before claiming smooth release scrubbing.")
    else:
        actions.append("Keep rerunning tools/qa_preview_scrub_readiness.py after decoder, actor, or timeline changes.")
    return _Area(
        id="preview_scrub_seek",
        label="Preview scrub/seek responsiveness",
        score=score,
        ready=ready,
        summary=(
            f"{_safe_int(summary.get('ready_projects'), 0)}/{_safe_int(summary.get('projects'), 0)} projects ready; "
            f"missing coverage={len(summary.get('missing_release_coverage') or [])}."
        ),
        actions=_clean_actions(actions),
        evidence={
            "current_corpus_scrub_ready": bool(payload.get("current_corpus_scrub_ready")),
            "release_scrub_claim_ready": ready,
            "release_blockers": blockers,
            "summary": summary,
            "top_seek_hotspots": list(payload.get("top_seek_hotspots") or [])[:5],
        },
    )


def _actor_area(root: str | Path) -> _Area:
    status = _load_json(root, "debugCapture/actor_corpus_status.json") or {}
    coverage = dict(status.get("coverage") or {})
    model_counts = dict(coverage.get("model_status_counts") or {})
    total = _safe_int(coverage.get("total"), 0)
    spine = _safe_int(coverage.get("spine"), 0)
    live2d = _safe_int(coverage.get("live2d"), 0)
    stress = _safe_int(coverage.get("stress"), 0)
    golden = dict(coverage.get("golden") or {})
    golden_pass = _safe_int(golden.get("pass"), 0)
    quarantined = _safe_int(coverage.get("quarantined"), 0)
    failures = _safe_int(model_counts.get("fail"), 0)
    ok = bool(status.get("ok")) and total >= 100 and failures == 0
    ready = bool(ok and stress >= 10 and golden_pass >= 40 and quarantined <= 1)
    if ready:
        score = 94 if quarantined else 98
    elif ok:
        score = 84
    else:
        score = 45 if total else 0
    actions = []
    if not ready:
        if not total:
            actions.append("Run tools/actor_compat_matrix.py and tools/actor_render_qa.py on the local actor corpus.")
        if failures:
            actions.append("Repair or quarantine failing Live2D/Spine models before broad compatibility claims.")
        if stress < 10:
            actions.append("Add more high-risk actor samples to stress coverage.")
        if golden_pass < 40:
            actions.append("Promote verified actor golden baselines for regression QA.")
    else:
        actions.append("Continue weekly actor_render_qa sweeps before changing Live2D/Spine render code.")
    return _Area(
        id="actor_model_compatibility",
        label="Live2D/Spine real-model compatibility",
        score=score,
        ready=ready,
        summary=f"{total} models ({spine} Spine, {live2d} Live2D), stress={stress}, golden={golden_pass}, quarantined={quarantined}.",
        actions=_clean_actions(actions),
        evidence={
            "ok": bool(status.get("ok")),
            "total": total,
            "spine": spine,
            "live2d": live2d,
            "stress": stress,
            "golden_pass": golden_pass,
            "quarantined": quarantined,
            "model_status_counts": model_counts,
        },
    )


def _release_area(root: str | Path) -> _Area:
    def build_current() -> dict[str, Any]:
        from app.release_positioning import build_release_positioning_report

        return build_release_positioning_report(root)

    payload = _call(None, build_current)
    ready = bool(payload.get("release_copy_claim_ready") or payload.get("ok"))
    checks = dict(payload.get("checks") or {})
    passed = sum(1 for value in checks.values() if value)
    total = len(checks)
    score = int(round((passed / max(1, total)) * 100))
    findings = list(payload.get("findings") or [])
    missing = list(payload.get("missing") or [])
    actions = []
    if findings:
        actions.append("Rewrite public copy that overclaims Screen Studio, CapCut, Resolve, or Fairlight parity.")
    if missing:
        actions.append("Restore missing public positioning files before packaging.")
    if not checks.get("replacement_caveat_present", True):
        actions.append("Keep explicit caveats that Tiger Studio is not a full replacement for pro suites yet.")
    return _Area(
        id="release_productization",
        label="Release productization and public positioning",
        score=score,
        ready=ready,
        summary=f"{passed}/{total} public-positioning checks passed; findings={len(findings)}, missing={len(missing)}.",
        actions=_clean_actions(actions, ("Run tools/qa_public_positioning.py before public builds.",)),
        evidence={
            "release_copy_claim_ready": ready,
            "checks": checks,
            "summary": dict(payload.get("summary") or {}),
            "findings": findings[:8],
            "missing": missing,
        },
    )


def _ux_area(root: str | Path) -> _Area:
    cached = _load_json(root, "debugCapture/product_polish_next_qa.json")

    def build_current() -> dict[str, Any]:
        from app.product_polish import product_polish_readiness_report

        return product_polish_readiness_report()

    payload = _call(cached, build_current)
    areas = [row for row in list(payload.get("areas") or []) if isinstance(row, Mapping)]
    ready = bool(payload.get("implementation_ok") or payload.get("ok"))
    score = _safe_int(payload.get("score"), 0)
    failing = [row for row in areas if not row.get("ok")]
    actions = [str(row.get("label") or row.get("id")) for row in failing]
    if not actions and ready:
        actions.append("Keep running product polish QA after toolbar, dock, timeline, and preset UI changes.")
    return _Area(
        id="ui_ux_polish",
        label="UI/UX polish and editing feel",
        score=score,
        ready=ready,
        summary=f"{len(areas) - len(failing)}/{len(areas)} polish areas passing.",
        actions=_clean_actions(actions),
        evidence={
            "implementation_ok": ready,
            "summary": dict(payload.get("summary") or {}),
            "failing_area_ids": [str(row.get("id")) for row in failing],
        },
    )


def build_release_gap_closure_report(root: str | Path = ".") -> dict[str, Any]:
    """Build a six-area closure report for the current product backlog."""
    root_path = Path(root).resolve()
    builders = (
        _ai_area,
        _screenstudio_area,
        _preview_scrub_area,
        _actor_area,
        _release_area,
        _ux_area,
    )
    rows = [builder(root_path).to_dict() for builder in builders]
    by_id = {row["id"]: row for row in rows}
    ordered = [by_id[area_id] for area_id in AREA_ORDER if area_id in by_id]
    ready = [row for row in ordered if row.get("ready")]
    blocked = [row for row in ordered if row.get("state") == "blocked"]
    attention = [row for row in ordered if row.get("state") == "attention"]
    score = int(round(mean([int(row.get("score", 0) or 0) for row in ordered]))) if ordered else 0
    top_gap = min(ordered, key=lambda row: int(row.get("score", 0) or 0)) if ordered else {}
    next_actions = []
    for row in sorted(ordered, key=lambda item: int(item.get("score", 0) or 0)):
        for action in list(row.get("actions") or [])[:3]:
            next_actions.append(f"{row['label']}: {action}")
    return {
        "kind": "release_gap_closure",
        "ok": True,
        "release_ready": len(ready) == len(ordered),
        "score": score,
        "summary": {
            "areas": len(ordered),
            "ready": len(ready),
            "attention": len(attention),
            "blocked": len(blocked),
            "top_gap": top_gap.get("id", ""),
            "top_gap_score": int(top_gap.get("score", 0) or 0) if top_gap else 0,
        },
        "areas": ordered,
        "next_actions": _clean_actions(next_actions),
        "truth": (
            "This closes the six-area release-gap audit surface. It does not claim full "
            "Screen Studio, CapCut, Resolve, Fairlight, or Fusion parity."
        ),
    }
