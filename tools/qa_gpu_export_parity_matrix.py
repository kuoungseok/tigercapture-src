from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


if os.environ.get("TIGERCAPTURE_QA_FORCE_OFFSCREEN", "").strip():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "gpu_export_parity_matrix_qa.json"


def _as_bool(payload: dict[str, Any], *keys: str) -> bool:
    row: Any = payload
    for key in keys:
        if not isinstance(row, dict):
            return False
        row = row.get(key)
    return bool(row)


def _component_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(report.get("ok")),
        "kind": report.get("kind", ""),
        "summary": report.get("summary", {}),
        "report": report.get("report", ""),
    }


def build_gpu_export_parity_matrix(
    *,
    preview_report: dict[str, Any],
    export_report: dict[str, Any],
    synthetic_report: dict[str, Any],
    ar_pbr_export_report: dict[str, Any] | None = None,
    ar_pbr_full_gpu_report: dict[str, Any] | None = None,
    actor_loading_report: dict[str, Any] | None = None,
    actor_lane_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preview_checks = preview_report.get("checks", {}) if isinstance(preview_report, dict) else {}
    export_checks = export_report.get("checks", {}) if isinstance(export_report, dict) else {}
    synthetic_features = synthetic_report.get("features", {}) if isinstance(synthetic_report, dict) else {}
    ar_pbr_checks = ar_pbr_export_report.get("checks", {}) if isinstance(ar_pbr_export_report, dict) else {}
    ar_pbr_full_gpu_smoke = ar_pbr_full_gpu_report.get("smoke_render", {}) if isinstance(ar_pbr_full_gpu_report, dict) else {}
    actor_checks = preview_report.get("actor_checks", {}) if isinstance(preview_report, dict) else {}
    spine_actor = actor_checks.get("spine", {}) if isinstance(actor_checks, dict) else {}
    live2d_actor = actor_checks.get("live2d", {}) if isinstance(actor_checks, dict) else {}
    actor_loading_ok = bool((actor_loading_report or {}).get("ok", True))
    actor_lane_ok = bool((actor_lane_report or {}).get("ok", True))

    rows = [
        {
            "feature": "color_grade",
            "preview": bool(preview_checks.get("shader_changed_base")),
            "export": bool(export_checks.get("processed_differs_from_baseline")),
            "release_blocking": True,
            "note": "GL shader path changes pixels; export-bake output differs from baseline.",
        },
        {
            "feature": "shader_clip_effects",
            "preview": bool(preview_checks.get("shader_changed_base")),
            "export": bool(synthetic_features.get("video_filters") and synthetic_features.get("chroma_key")),
            "release_blocking": True,
            "note": "Preview shader effects and synthetic export filter/chroma bake are both covered.",
        },
        {
            "feature": "typography",
            "preview": "covered_by_editor_e2e",
            "export": bool(export_checks.get("processed_has_text_highlight_pixels")),
            "release_blocking": False,
            "note": "Final export text pixels are verified here; full editor preview text is covered by Editor E2E Smoke.",
        },
        {
            "feature": "spine_actor",
            "preview": bool(spine_actor.get("visible")),
            "export": bool(synthetic_features.get("spine_live2d_actor_overlays")),
            "release_blocking": True,
            "note": "Preview uses real Spine direct GL overlay when local sample exists; export uses synthetic actor overlay bake.",
        },
        {
            "feature": "live2d_actor",
            "preview": bool(live2d_actor.get("visible")),
            "export": bool(synthetic_features.get("spine_live2d_actor_overlays")),
            "release_blocking": True,
            "note": "Preview uploads a real rendered Live2D sample when local sample exists; export uses synthetic Live2D MOV bake.",
        },
        {
            "feature": "live2d_actor_workflow",
            "preview": actor_loading_ok,
            "export": actor_lane_ok,
            "release_blocking": True,
            "note": "Live2D/Spine loading progress UX and actor-lane workflow smoke are both healthy.",
        },
        {
            "feature": "ar_pbr_overlay",
            "preview": bool(
                preview_checks.get("ar_pbr_red_overlay_visible")
                and preview_checks.get("shadow_or_reflection_visible")
            ),
            "export": bool(
                ar_pbr_checks.get("processed_differs_from_baseline")
                and ar_pbr_checks.get("processed_has_ar_pbr_pixels")
                and ar_pbr_checks.get("export_rendered_track")
            ),
            "release_blocking": False,
            "note": "GPU preview packets are visible; final export verifies AR/PBR model bake through the export compositor.",
        },
        {
            "feature": "ar_pbr_full_model_view_gpu_export",
            "preview": bool(
                preview_checks.get("ar_pbr_red_overlay_visible")
                and preview_checks.get("shadow_or_reflection_visible")
            ),
            "export": bool(
                (ar_pbr_full_gpu_report or {}).get("full_gpu_export_available")
                and ar_pbr_full_gpu_smoke.get("ok")
                and ar_pbr_full_gpu_smoke.get("mode") == "full_model_view_gpu_export_service"
                and not bool(ar_pbr_full_gpu_smoke.get("fallback"))
            ),
            "release_blocking": True,
            "note": "The worker-safe helper must render a real smoke frame with the model-view GPU path, not the packet fallback.",
        },
        {
            "feature": "transitions",
            "preview": "covered_by_project_player_unit",
            "export": bool(synthetic_features.get("transitions")),
            "release_blocking": False,
            "note": "Synthetic render_clip_tracks dissolve export is verified; ProjectPlayer transition preview has separate unit coverage.",
        },
        {
            "feature": "masked_node_graph",
            "preview": "covered_by_project_audit",
            "export": bool(synthetic_features.get("masked_node_graph") and synthetic_features.get("tracked_mask_node_graph")),
            "release_blocking": False,
            "note": "Synthetic export covers static and tracked mask node graphs.",
        },
    ]

    for row in rows:
        preview_ok = row["preview"] is True or isinstance(row["preview"], str)
        export_ok = row["export"] is True or isinstance(row["export"], str)
        row["ok"] = bool(preview_ok and export_ok)

    component_ok = all(
        bool(component.get("ok"))
        for component in (
            preview_report,
            export_report,
            synthetic_report,
            ar_pbr_export_report or {"ok": False},
            ar_pbr_full_gpu_report or {"ok": False},
            actor_loading_report or {"ok": True},
            actor_lane_report or {"ok": True},
        )
    )
    blocking_failures = [
        row for row in rows
        if bool(row.get("release_blocking")) and not bool(row.get("ok"))
    ]
    coverage_gaps = [
        row for row in rows
        if not bool(row.get("ok"))
    ]
    payload = {
        "ok": bool(component_ok and not blocking_failures),
        "release_ready": bool(component_ok and not coverage_gaps),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "gpu_export_parity_matrix",
        "summary": {
            "features": len(rows),
            "passing": sum(1 for row in rows if row.get("ok")),
            "coverage_gaps": len(coverage_gaps),
            "blocking_failures": len(blocking_failures),
            "components_ok": component_ok,
        },
        "components": {
            "gpu_preview_pixel_collision": _component_summary(preview_report),
            "editor_export_bake": _component_summary(export_report),
            "export_parity_smoke": _component_summary(synthetic_report),
            "ar_pbr_export_bake": _component_summary(ar_pbr_export_report or {}),
            "ar_pbr_full_gpu_export_service": _component_summary(ar_pbr_full_gpu_report or {}),
            "actor_loading_ux": _component_summary(actor_loading_report or {"ok": True}),
            "actor_lane_workflow": _component_summary(actor_lane_report or {"ok": True}),
        },
        "matrix": rows,
        "coverage_gaps": coverage_gaps,
        "blocking_failures": blocking_failures,
    }
    return payload


def run_gpu_export_parity_matrix_qa(
    *,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    from tools.qa_gpu_preview_pixel_collision import run_gpu_preview_pixel_collision_qa

    report_path = report_path if report_path.is_absolute() else ROOT / report_path
    base_dir = report_path.parent / "gpu_export_parity_matrix"
    base_dir.mkdir(parents=True, exist_ok=True)
    preview_report = run_gpu_preview_pixel_collision_qa(
        out=ROOT / "debugCapture" / "gpu_preview_pixel_collision_qa.json",
        screenshot=ROOT / "debugCapture" / "gpu_preview_pixel_collision.png",
        visible=False,
    )
    from tools.qa_editor_export_bake import run_editor_export_bake_qa
    from tools.qa_ar_pbr_export_bake import run_ar_pbr_export_bake_qa
    from tools.qa_ar_pbr_full_gpu_export_service import run_ar_pbr_full_gpu_export_service_qa
    from tools.qa_actor_loading_ux import run_actor_loading_ux_qa
    from tools.qa_actor_lane_workflow import run_actor_lane_workflow_qa
    from tools.verify_export_parity import run_export_parity_smoke_report

    export_report = run_editor_export_bake_qa(
        out_dir=base_dir / "editor_export_bake",
        report_path=ROOT / "debugCapture" / "editor_export_bake_qa.json",
    )
    synthetic_report = run_export_parity_smoke_report(
        report_path=ROOT / "debugCapture" / "export_parity_smoke_qa.json",
        verbose=False,
    )
    ar_pbr_export_report = run_ar_pbr_export_bake_qa(
        out_dir=base_dir / "ar_pbr_export_bake",
        report_path=ROOT / "debugCapture" / "ar_pbr_export_bake_qa.json",
    )
    ar_pbr_full_gpu_report = run_ar_pbr_full_gpu_export_service_qa(probe=True, smoke_render=True)
    (ROOT / "debugCapture" / "ar_pbr_full_gpu_export_service_qa.json").write_text(
        json.dumps(ar_pbr_full_gpu_report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    actor_loading_report = run_actor_loading_ux_qa()
    (ROOT / "debugCapture" / "actor_loading_ux_qa.json").write_text(
        json.dumps(actor_loading_report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    actor_lane_report = run_actor_lane_workflow_qa(include_samples=True)
    (ROOT / "debugCapture" / "actor_lane_workflow_qa.json").write_text(
        json.dumps(actor_lane_report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    payload = build_gpu_export_parity_matrix(
        preview_report=preview_report,
        export_report=export_report,
        synthetic_report=synthetic_report,
        ar_pbr_export_report=ar_pbr_export_report,
        ar_pbr_full_gpu_report=ar_pbr_full_gpu_report,
        actor_loading_report=actor_loading_report,
        actor_lane_report=actor_lane_report,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run combined GPU preview/export parity matrix QA.")
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    report = run_gpu_export_parity_matrix_qa(report_path=args.out)
    print(json.dumps({
        "ok": report.get("ok"),
        "release_ready": report.get("release_ready"),
        "report": report.get("report"),
        "summary": report.get("summary"),
        "coverage_gaps": [
            row.get("feature") for row in report.get("coverage_gaps", []) or []
        ],
    }, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
