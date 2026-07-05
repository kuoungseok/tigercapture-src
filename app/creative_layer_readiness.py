"""Conservative creative-layer readiness diagnostics.

The editor has many creator-facing surfaces: filters, transitions, animated
type, node graphs, Live2D/Spine actors, and AR/PBR assets. This report keeps the
product claim honest by separating action/QA evidence from full professional
compositing or template-ecosystem parity.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


CREATIVE_LAYER_READINESS_SCHEMA = "tigerstudio.creative_layer_readiness.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _preset_count(summary: Mapping[str, Any], kind: str) -> int:
    by_kind = summary.get("by_kind") if isinstance(summary.get("by_kind"), Mapping) else {}
    return _int(by_kind.get(kind), 0)


def _has_all(action_ids: set[str], names: Iterable[str]) -> bool:
    return all(name in action_ids for name in names)


def build_creative_layer_readiness_report(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_ids: Iterable[str] = (),
    preset_summary: Mapping[str, Any] | None = None,
    ar_pbr_full_gpu_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a claim-safe report for creative layer product depth."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), Mapping) else {}
    presets = preset_summary if isinstance(preset_summary, Mapping) else {}
    actions = {str(row) for row in action_ids if str(row)}

    video_clip_count = _int(summary.get("video_clip_count"), 0)
    effect_count = _preset_count(presets, "effect")
    transition_count = _preset_count(presets, "transition")
    title_count = _preset_count(presets, "title")
    actor_count = _preset_count(presets, "actor")
    sticker_count = _preset_count(presets, "sticker")
    template_count = _preset_count(presets, "template")
    ar_pbr_gpu = ar_pbr_full_gpu_report if isinstance(ar_pbr_full_gpu_report, Mapping) else {}
    ar_pbr_smoke = ar_pbr_gpu.get("smoke_render") if isinstance(ar_pbr_gpu.get("smoke_render"), Mapping) else {}
    ar_pbr_full_gpu_ok = bool(
        ar_pbr_gpu.get("full_gpu_export_available")
        and ar_pbr_smoke.get("ok")
        and ar_pbr_smoke.get("mode") == "full_model_view_gpu_export_service"
        and not bool(ar_pbr_smoke.get("fallback"))
    )

    rows = [
        {
            "id": "effects_filter_stack",
            "label": "Effect/filter stack",
            "status": "ready" if "clip.set_filter" in actions and effect_count >= 32 else "partial",
            "score": 82 if "clip.set_filter" in actions and effect_count >= 32 else 66,
            "evidence": [
                "clip.set_filter action exists" if "clip.set_filter" in actions else "clip.set_filter action missing",
                f"effect_preset_count={effect_count}",
                f"video_clip_count={video_clip_count}",
            ],
            "remaining": [
                "Per-effect A/B preview and export parity evidence should stay visible in QA.",
                "A dedicated effect stack inspector is still shallower than Premiere/Resolve/Fusion.",
            ],
        },
        {
            "id": "transition_workflow",
            "label": "Transition workflow",
            "status": "ready" if _has_all(actions, ("transition.apply", "transition.clear")) and transition_count >= 24 else "partial",
            "score": 84 if _has_all(actions, ("transition.apply", "transition.clear")) and transition_count >= 24 else 58,
            "evidence": [
                "transition.apply action exists" if "transition.apply" in actions else "transition.apply action missing",
                "transition.clear action exists" if "transition.clear" in actions else "transition.clear action missing",
                f"transition_preset_count={transition_count}",
            ],
            "remaining": [
                "Timeline handles and visual edge labels should make transition regions obvious.",
                "Transition preview/export parity should be sampled with real media, not only metadata.",
            ],
        },
        {
            "id": "typography_motion",
            "label": "Typography and motion text",
            "status": "ready" if _has_all(actions, ("text.add", "text.set_keyframes")) and title_count >= 30 else "partial",
            "score": 80 if _has_all(actions, ("text.add", "text.set_keyframes")) and title_count >= 30 else 62,
            "evidence": [
                "text.add and text.set_keyframes actions exist"
                if _has_all(actions, ("text.add", "text.set_keyframes"))
                else "text action coverage is incomplete",
                f"title_preset_count={title_count}",
                f"sticker_preset_count={sticker_count}",
            ],
            "remaining": [
                "Template previews should show the exact title/sticker animation rather than generic motion.",
                "More short-form typography packs are needed for CapCut-style immediacy.",
            ],
        },
        {
            "id": "node_graph_productization",
            "label": "Node graph productization",
            "status": "partial" if _has_all(actions, ("node.graph.set", "node.add", "node.connect", "node.set_param", "node.delete")) else "missing",
            "score": 64 if _has_all(actions, ("node.graph.set", "node.add", "node.connect", "node.set_param", "node.delete")) else 28,
            "evidence": [
                "node graph actions cover set/add/connect/set_param/delete"
                if _has_all(actions, ("node.graph.set", "node.add", "node.connect", "node.set_param", "node.delete"))
                else "node graph action coverage is incomplete",
            ],
            "remaining": [
                "This is not yet a Fusion-style compositor: no full 2D/3D node engine, expressions, macro library, or deep GPU node cache.",
                "Node debug, bypass, preview, and export parity UI needs more real-world QA.",
            ],
        },
        {
            "id": "live2d_spine_actor_workflow",
            "label": "Live2D/Spine actor workflow",
            "status": "partial" if _has_all(actions, ("actor.add", "actor.set_transform", "actor.set_keyframes")) else "missing",
            "score": 68 if _has_all(actions, ("actor.add", "actor.set_transform", "actor.set_keyframes")) else 34,
            "evidence": [
                "actor add/transform/keyframe actions exist"
                if _has_all(actions, ("actor.add", "actor.set_transform", "actor.set_keyframes"))
                else "actor action coverage is incomplete",
                f"actor_preset_count={actor_count}",
            ],
            "remaining": [
                "Actual Live2D/Spine model corpus QA must keep expanding; Unity-exported variants remain risky.",
                "Actor editor loading, motion mapping, independent preview sync, and export bake evidence must stay separate from data-model action coverage.",
            ],
        },
        {
            "id": "ar_pbr_3d_compositing",
            "label": "AR/PBR 3D compositing",
            "status": "partial",
            "score": 66 if ar_pbr_full_gpu_ok else 54,
            "evidence": [
                "AR/PBR import, preview, and export hooks exist in the product tree",
                "Worker-safe model-view GPU export smoke passed"
                if ar_pbr_full_gpu_ok
                else "3D action surface is intentionally not treated as complete until model-view GPU preview/export parity is proven",
            ],
            "remaining": [
                "Live depth-FBO, material parity, camera/SLAM robustness, and real-asset renderer matching still need more QA."
                if ar_pbr_full_gpu_ok
                else "Live depth-FBO, material parity, camera/SLAM robustness, and worker-safe GPU export service remain product blockers.",
                "Do not sell this as dedicated DCC/offline-renderer-grade rendering yet.",
            ],
        },
        {
            "id": "template_ecosystem",
            "label": "Template/preset ecosystem",
            "status": "partial" if template_count >= 10 and (effect_count + transition_count + title_count) >= 80 else "needs_expansion",
            "score": 60 if template_count >= 10 and (effect_count + transition_count + title_count) >= 80 else 44,
            "evidence": [
                f"template_preset_count={template_count}",
                f"creator_preset_total={effect_count + transition_count + title_count + sticker_count}",
            ],
            "remaining": [
                "CapCut-scale templates need larger volume, stronger thumbnails, and one-click default results.",
                "Preset application feedback must be obvious on timeline clips and in preview.",
            ],
        },
    ]

    score = int(round(sum(_int(row.get("score"), 0) for row in rows) / max(1, len(rows))))
    blockers = [
        row["id"]
        for row in rows
        if str(row.get("status")) in {"missing", "needs_expansion"} or _int(row.get("score"), 0) < 60
    ]
    return {
        "schema": CREATIVE_LAYER_READINESS_SCHEMA,
        "score": score,
        "full_creative_suite_claim_ok": False,
        "safe_positioning": "creator-grade creative layer foundations; not a full Fusion/After Effects/Marmoset/CapCut ecosystem replacement",
        "rows": rows,
        "blockers": blockers,
        "next_actions": [
            "Keep transition/effect/title regions visible on the timeline so users can see what is applied.",
            "Expand exact preset previews and export parity QA for effects, titles, transitions, actors, and AR/PBR.",
            "Separate Live2D/Spine/AR-PBR renderer quality gates from simple action/data-model coverage.",
        ],
    }


def format_creative_layer_readiness_summary(report: Mapping[str, Any]) -> str:
    score = _int(report.get("score"), 0)
    claim = bool(report.get("full_creative_suite_claim_ok"))
    blockers = ", ".join(str(row) for row in list(report.get("blockers") or [])[:6])
    return (
        f"Creative layer readiness {score}/100. "
        f"Full creative-suite claim: {'allowed' if claim else 'not allowed'}. "
        f"Blockers: {blockers or 'none'}."
    )
