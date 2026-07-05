from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def run_professional_pipeline_next_qa(*, out: str | Path | None = None) -> dict[str, Any]:
    from app.audio_workflow import (
        ADRCue,
        ElasticAudioRetime,
        SFXLibraryItem,
        build_default_routing_matrix,
        fairlight_engine_report,
    )
    from app.color_workflow import (
        build_professional_color_pipeline_payload,
        professional_color_pipeline_report,
    )
    from app.post_pipeline_workflow import professional_post_pipeline_report
    from app.professional_readiness import audit_resolve_post_pipeline_parity
    from app.professional_workflow_payloads import attach_professional_workflow_payloads

    color_payload = build_professional_color_pipeline_payload(
        hdr_metadata={"standard": "dolby_vision", "dynamic_metadata": True},
        restoration={
            "temporal_nr": 0.35,
            "spatial_nr": 0.25,
            "film_grain": 0.18,
            "deflicker": True,
            "dead_pixel_repair": True,
            "dust_dirt_removal": True,
        },
    )
    color = professional_color_pipeline_report(color_payload)
    routing = build_default_routing_matrix([
        {"id": 1, "role": "dialogue"},
        {"id": 2, "role": "music"},
        {"id": 3, "role": "sfx"},
    ])
    audio = fairlight_engine_report(
        routing,
        adr_cues=[ADRCue("adr_01", 1000, 4200, "Replace noisy dialogue", take_count=2)],
        retimes=[ElasticAudioRetime("dialogue_clip_01", 3200, 3600)],
        sfx_items=[SFXLibraryItem("soft_click", "sfx/ui/soft_click.wav", ("ui", "click"))],
    )
    post = professional_post_pipeline_report()
    enriched = attach_professional_workflow_payloads({
        "project_settings": {
            "fps": 120.0,
            "preview_export_parity_lock": True,
            "color_management": {
                "input_space": "sRGB",
                "working_space": "ACEScg",
                "output_space": "Rec.2020",
                "output_transfer": "PQ",
                "processing_bits": 32,
                "preview_transform_enabled": True,
            },
            "audio": {"sample_rate": 48000, "channel_layout": "5.1"},
        },
        "media_pool": [{"path": "sample_camera_card/A001_C001.mov"}],
        "audio_tracks": [
            {"id": 1, "role": "dialogue", "clips": []},
            {"id": 2, "role": "music", "clips": []},
            {"id": 3, "role": "sfx", "clips": []},
        ],
    })
    parity = audit_resolve_post_pipeline_parity(enriched)

    checks = {
        "color_pipeline": bool(color.get("ok")),
        "fairlight_engine": bool(audio.get("ok")),
        "fusion_compositor": bool(post.get("ok")),
        "payload_builder": bool(enriched.get("color_pipeline_payload") and enriched.get("fairlight_engine_payload") and enriched.get("vfx_node_graphs")),
        "parity_matrix_reads_payload": int((parity.get("category_scores") or {}).get("color", 0) or 0) >= 70
        and int((parity.get("category_scores") or {}).get("audio", 0) or 0) >= 70
        and int((parity.get("category_scores") or {}).get("vfx_fusion", 0) or 0) >= 70,
        "professional_deliver_matrix": len(enriched.get("professional_deliver_jobs") or []) >= 4,
        "local_ml_registry": bool((enriched.get("local_ml_status") or {}).get("ok")),
        "audio_mixer_stress": bool((enriched.get("audio_mixer_stress") or {}).get("ok")),
        "collaboration_model": bool((enriched.get("collaboration_status") or {}).get("ok")),
        "hardware_registry": bool((enriched.get("hardware_status") or {}).get("ok")),
    }
    report = {
        "ok": all(checks.values()),
        "checks": checks,
        "summary": {
            "color_score": int((parity.get("category_scores") or {}).get("color", 0) or 0),
            "audio_score": int((parity.get("category_scores") or {}).get("audio", 0) or 0),
            "vfx_score": int((parity.get("category_scores") or {}).get("vfx_fusion", 0) or 0),
            "deliver_jobs": len(enriched.get("deliver_jobs") or []),
            "professional_deliver_jobs": len(enriched.get("professional_deliver_jobs") or []),
            "vfx_nodes": int((post.get("summary") or {}).get("nodes", 0) or 0),
            "audio_nodes": int((audio.get("summary") or {}).get("nodes", 0) or 0),
            "local_ml_features": int(((post.get("summary") or {}).get("local_ml_features", 0) or 0)),
            "audio_stress_tracks": int(((enriched.get("audio_mixer_stress") or {}).get("virtual_tracks", 0) or 0)),
            "hardware_devices": int(((post.get("summary") or {}).get("hardware_devices", 0) or 0)),
            "restoration_tools": int((color.get("summary") or {}).get("restoration_tools", 0) or 0),
        },
        "color": color,
        "audio": audio,
        "post": post,
        "enriched_project_keys": sorted(enriched.keys()),
        "parity": {
            "score": parity.get("score"),
            "category_scores": parity.get("category_scores"),
            "top_actions": parity.get("top_actions"),
            "professional_depth_actions": parity.get("professional_depth_actions"),
        },
    }
    if out is not None:
        _write_json(Path(out), report)
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate professional Color/Fairlight/Fusion pipeline tranche.")
    parser.add_argument("--out", default="debugCapture/professional_pipeline_next_qa.json")
    args = parser.parse_args()
    report = run_professional_pipeline_next_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {Path(args.out).resolve()}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
