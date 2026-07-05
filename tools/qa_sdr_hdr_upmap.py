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


def run_sdr_hdr_upmap_qa(*, out: str | Path | None = None) -> dict[str, Any]:
    from app.sdr_hdr_upmap import SDRHDRUpmapProfile, sdr_to_hdr_upmap_report

    profile = SDRHDRUpmapProfile(max_frames=2)
    report = sdr_to_hdr_upmap_report(
        "qa_samples/sdr_reference.mp4",
        "debugCapture/sdr_hdr_upmap_frames",
        profile,
        run=False,
    )
    command_text = " ".join(str(part) for part in report.get("command") or [])
    gallery = report.get("preset_gallery") if isinstance(report.get("preset_gallery"), dict) else {}
    review_model = report.get("review_model") if isinstance(report.get("review_model"), dict) else {}
    checks = {
        "dry_run_report": bool(report.get("dry_run")),
        "scene_linear_float_filter": "format=rgb48le" in str(report.get("ffmpeg_filter") or "")
        and "gbrpf32le" in str(report.get("ffmpeg_filter") or ""),
        "exr_encoder": "-c:v exr" in command_text,
        "float_pixel_format": "-pix_fmt gbrpf32le" in command_text,
        "provider_contract": "provider" in report and "configured" in dict(report.get("provider") or {}),
        "preset_gallery": int(gallery.get("preset_count", 0) or 0) >= 4,
        "review_model": bool(review_model.get("ready")) and bool(review_model.get("controls")),
        "honest_claim": report.get("claim_level") == "ltx_style_hdr_exr_foundation_not_neural_ltx_parity",
    }
    payload = {
        "ok": all(checks.values()),
        "checks": checks,
        "summary": {
            "engine": report.get("engine"),
            "real_ltx_model": bool(report.get("real_ltx_model")),
            "target": (report.get("profile") or {}).get("target"),
            "output_pattern": report.get("output_pattern"),
            "preset_count": int(gallery.get("preset_count", 0) or 0),
            "review_cards": len(review_model.get("cards") if isinstance(review_model.get("cards"), list) else []),
        },
        "report": report,
    }
    if out is not None:
        _write_json(Path(out), payload)
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate the SDR -> HDR/EXR upmap foundation.")
    parser.add_argument("--out", default="debugCapture/sdr_hdr_upmap_qa.json")
    args = parser.parse_args()
    report = run_sdr_hdr_upmap_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {Path(args.out).resolve()}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
