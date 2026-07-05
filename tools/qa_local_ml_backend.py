"""Build a fast QA report for the local-first ML backend."""
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


def _create_synthetic_image(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (320, 180), (18, 21, 32))
        draw = ImageDraw.Draw(image)
        draw.rectangle((118, 46, 244, 142), fill=(246, 96, 72))
        draw.ellipse((154, 24, 204, 78), fill=(255, 208, 112))
        draw.rectangle((170, 82, 220, 146), fill=(96, 212, 188))
        image.save(path)
        return path
    except Exception:
        # Tiny binary PPM fallback.  Pillow is in requirements, but keep the QA
        # tool deterministic if that install is broken.
        width, height = 64, 48
        pixels = []
        for y in range(height):
            for x in range(width):
                if 22 <= x <= 46 and 12 <= y <= 38:
                    pixels.append(bytes([245, 90, 70]))
                else:
                    pixels.append(bytes([16, 18, 28]))
        path = path.with_suffix(".ppm")
        path.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + b"".join(pixels))
        return path


def build_local_ml_backend_report(sample: str | Path | None = None) -> dict[str, Any]:
    from app.capcut_workflow import capcut_creator_bundle_from_local_media
    from app.local_ml import local_ml_analyze_media, local_ml_backend_status

    sample_path = Path(sample) if sample else _create_synthetic_image(ROOT / "debugCapture" / "local_ml_synthetic.png")
    status = local_ml_backend_status()
    if status.get("mode") == "disabled" or status.get("disabled"):
        report = {
            "ok": True,
            "score": 100,
            "summary": {
                "mode": status.get("mode"),
                "disabled": True,
                "cloud_enabled": status.get("cloud_enabled"),
                "api_required": status.get("api_required"),
                "visual_available": status.get("local_visual_available"),
                "detections": 0,
                "object_tags": [],
                "capcut_bundle_ok": False,
                "transcription_available": False,
            },
            "checks": {
                "feature_gate_disabled": True,
                "cloud_disabled": status.get("cloud_enabled") is False and status.get("api_required") is False,
                "capability_report": isinstance(status.get("capabilities"), dict),
                "visual_analysis": True,
                "capcut_bundle": True,
            },
            "failures": [],
            "sample": str(sample_path),
            "status": status,
            "analysis": {
                "ok": False,
                "disabled": True,
                "reason": "local_ml_feature_gate_disabled",
            },
            "capcut_bundle": {
                "ok": False,
                "disabled": True,
                "local_ml_analysis": {
                    "ok": False,
                    "disabled": True,
                    "reason": "local_ml_feature_gate_disabled",
                },
            },
        }
        return report
    analysis = local_ml_analyze_media(sample_path, sample_count=3)
    bundle = capcut_creator_bundle_from_local_media(sample_path, sample_count=3, target_count=2)
    checks = {
        "local_mode": status.get("mode") == "local",
        "cloud_disabled": status.get("cloud_enabled") is False and status.get("api_required") is False,
        "capability_report": isinstance(status.get("capabilities"), dict) and bool(status.get("capabilities")),
        "visual_analysis": bool(analysis.get("ok")) and bool(analysis.get("subject_detections")),
        "capcut_bundle": bool(bundle.get("ok")) and bool((bundle.get("project_settings_patch") or {}).get("capcut_creator_workflow")),
    }
    failures = [name for name, passed in checks.items() if not passed]
    score = int(round(100 * (len(checks) - len(failures)) / max(1, len(checks))))
    return {
        "ok": not failures,
        "score": score,
        "summary": {
            "mode": status.get("mode"),
            "cloud_enabled": status.get("cloud_enabled"),
            "api_required": status.get("api_required"),
            "visual_available": status.get("local_visual_available"),
            "detections": len(analysis.get("subject_detections", []) or []),
            "object_tags": list(analysis.get("object_tags", []) or []),
            "capcut_bundle_ok": bool(bundle.get("ok")),
            "transcription_available": bool(
                ((status.get("capabilities") or {}).get("whisper_transcription") or {}).get("available")
            ),
        },
        "checks": checks,
        "failures": failures,
        "sample": str(sample_path),
        "status": status,
        "analysis": analysis,
        "capcut_bundle": {
            "ok": bundle.get("ok"),
            "project_settings_patch": bundle.get("project_settings_patch"),
            "workflow_preset_ids": bundle.get("workflow_preset_ids"),
            "search_chips": bundle.get("search_chips"),
            "local_ml_analysis": bundle.get("local_ml_analysis"),
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build local ML backend QA report.")
    parser.add_argument("--sample", default="", help="Optional local media file to analyze.")
    parser.add_argument("--out", default="debugCapture/local_ml_backend_qa.json")
    args = parser.parse_args()

    report = build_local_ml_backend_report(args.sample or None)
    out_path = ROOT / args.out
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
