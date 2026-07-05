from __future__ import annotations

from tools.qa_gpu_export_parity_matrix import build_gpu_export_parity_matrix


def _preview_report(*, ar_export_gap: bool = True) -> dict:
    _ = ar_export_gap
    return {
        "ok": True,
        "kind": "gpu_preview_pixel_collision",
        "checks": {
            "shader_changed_base": True,
            "ar_pbr_red_overlay_visible": True,
            "shadow_or_reflection_visible": True,
        },
        "actor_checks": {
            "spine": {"visible": True},
            "live2d": {"visible": True},
        },
    }


def _export_report() -> dict:
    return {
        "ok": True,
        "kind": "editor_export_bake",
        "checks": {
            "processed_differs_from_baseline": True,
            "processed_has_text_highlight_pixels": True,
        },
        "summary": {"checks": 2, "passing": 2},
    }


def _synthetic_report() -> dict:
    return {
        "ok": True,
        "kind": "export_parity_smoke",
        "features": {
            "video_filters": True,
            "chroma_key": True,
            "spine_live2d_actor_overlays": True,
            "transitions": True,
            "masked_node_graph": True,
            "tracked_mask_node_graph": True,
        },
    }


def _ar_pbr_export_report() -> dict:
    return {
        "ok": True,
        "kind": "ar_pbr_export_bake",
        "checks": {
            "processed_differs_from_baseline": True,
            "processed_has_ar_pbr_pixels": True,
            "export_rendered_track": True,
        },
        "summary": {"checks": 3, "passing": 3},
    }


def _ar_pbr_full_gpu_report() -> dict:
    return {
        "ok": True,
        "kind": "ar_pbr_full_gpu_export_service",
        "full_gpu_export_available": True,
        "worker_safe": True,
        "smoke_render": {
            "ok": True,
            "mode": "full_model_view_gpu_export_service",
            "fallback": False,
            "rendered_track_count": 1,
            "changed_pixels_proxy": True,
        },
        "blockers": [],
    }


def test_gpu_export_parity_matrix_reaches_release_ready_when_all_features_pass():
    report = build_gpu_export_parity_matrix(
        preview_report=_preview_report(),
        export_report=_export_report(),
        synthetic_report=_synthetic_report(),
        ar_pbr_export_report=_ar_pbr_export_report(),
        ar_pbr_full_gpu_report=_ar_pbr_full_gpu_report(),
    )

    assert report["ok"] is True
    assert report["release_ready"] is True
    assert report["summary"]["blocking_failures"] == 0
    assert report["coverage_gaps"] == []


def test_gpu_export_parity_matrix_blocks_missing_actor_preview():
    preview = _preview_report()
    preview["actor_checks"]["spine"]["visible"] = False

    report = build_gpu_export_parity_matrix(
        preview_report=preview,
        export_report=_export_report(),
        synthetic_report=_synthetic_report(),
        ar_pbr_export_report=_ar_pbr_export_report(),
        ar_pbr_full_gpu_report=_ar_pbr_full_gpu_report(),
    )

    assert report["ok"] is False
    assert report["summary"]["blocking_failures"] == 1
    assert report["blocking_failures"][0]["feature"] == "spine_actor"


def test_gpu_export_parity_matrix_blocks_missing_live2d_preview_coverage():
    preview = _preview_report()
    preview["actor_checks"]["live2d"]["visible"] = False

    report = build_gpu_export_parity_matrix(
        preview_report=preview,
        export_report=_export_report(),
        synthetic_report=_synthetic_report(),
        ar_pbr_export_report=_ar_pbr_export_report(),
        ar_pbr_full_gpu_report=_ar_pbr_full_gpu_report(),
    )

    assert report["ok"] is False
    assert report["release_ready"] is False
    assert report["summary"]["coverage_gaps"] == 1
    assert report["coverage_gaps"][0]["feature"] == "live2d_actor"
    assert report["blocking_failures"][0]["feature"] == "live2d_actor"


def test_gpu_export_parity_matrix_blocks_missing_full_model_view_gpu_helper():
    helper = _ar_pbr_full_gpu_report()
    helper["smoke_render"]["ok"] = False
    helper["smoke_render"]["fallback"] = True

    report = build_gpu_export_parity_matrix(
        preview_report=_preview_report(),
        export_report=_export_report(),
        synthetic_report=_synthetic_report(),
        ar_pbr_export_report=_ar_pbr_export_report(),
        ar_pbr_full_gpu_report=helper,
    )

    assert report["ok"] is False
    assert report["release_ready"] is False
    assert "ar_pbr_full_model_view_gpu_export" in {
        row["feature"] for row in report["blocking_failures"]
    }
