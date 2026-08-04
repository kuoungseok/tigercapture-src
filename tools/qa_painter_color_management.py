"""Measure Painter ICC conversion/proofing and corruption boundaries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_color_management import inspect_icc_profile, soft_proof_rgba, transform_rgba_profile
from app.painter_file_exchange import export_flat_image, inspect_flat_image


DEFAULT_PROFILE_ROOT = Path(r"C:\Windows\System32\spool\drivers\color")


def _fixture() -> Image.Image:
    yy, xx = np.mgrid[0:48, 0:64]
    rgba = np.empty((48, 64, 4), dtype=np.uint8)
    rgba[..., 0] = (xx * 255 // 63).astype(np.uint8)
    rgba[..., 1] = (yy * 255 // 47).astype(np.uint8)
    rgba[..., 2] = ((xx + yy) * 255 // 110).astype(np.uint8)
    rgba[..., 3] = ((xx * 3 + yy * 5) % 256).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def build_report(output_root: Path, profile_root: Path = DEFAULT_PROFILE_ROOT) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    profiles = []
    for path in sorted(profile_root.iterdir()):
        if path.suffix.casefold() not in {".icc", ".icm"}:
            continue
        row = inspect_icc_profile(path)
        row["path"] = str(path)
        profiles.append(row)
    valid_rgb = [row for row in profiles if row["valid"] and row["color_space"].strip() == "RGB"]
    valid_cmyk = [row for row in profiles if row["valid"] and row["color_space"].strip() == "CMYK"]
    if len(valid_rgb) < 2:
        raise RuntimeError("Two valid installed RGB ICC profiles are required")
    if not valid_cmyk:
        raise RuntimeError("One valid installed CMYK proof profile is required")
    srgb = next((row for row in valid_rgb if "srgb color space" in row["description"].casefold()), valid_rgb[0])
    alternate = next(row for row in valid_rgb if row["sha256"] != srgb["sha256"])
    proof = valid_cmyk[0]
    fixture = _fixture()
    transformed, transform_report = transform_rgba_profile(
        fixture,
        source_profile=srgb["path"],
        output_profile=alternate["path"],
    )
    transformed_path = output_root / "rgb_transform.png"
    transformed.save(transformed_path)
    proofed, proof_report = soft_proof_rgba(
        fixture,
        source_profile=srgb["path"],
        proof_profile=proof["path"],
        display_profile=srgb["path"],
    )
    proofed_path = output_root / "cmyk_soft_proof.png"
    proofed.save(proofed_path)
    export_report = export_flat_image(
        output_root / "converted_export.png",
        fixture,
        source_icc=srgb["path"],
        output_icc=alternate["path"],
    )
    damaged_path = output_root / "damaged.png"
    payload = Path(export_report["path"]).read_bytes()
    damaged_path.write_bytes(payload[:-4] + bytes([payload[-4] ^ 0x01]) + payload[-3:])
    damaged = inspect_flat_image(damaged_path)
    return {
        "schema": "tigerstudio.painter.color-management-qa.v1",
        "evidence_class": "measured_local_runtime",
        "claims": {
            "rgb_nonidentity_transform_executed": bool(transform_report["pixel_changed"]),
            "cmyk_soft_proof_executed": bool(proof_report["pixel_changed"]),
            "alpha_preserved": bool(transform_report["alpha_preserved"] and proof_report["alpha_preserved"]),
            "damaged_png_rejected": not bool(damaged["integrity"]["valid"]),
        },
        "profiles": profiles,
        "rgb_transform": transform_report,
        "soft_proof": proof_report,
        "export": export_report,
        "damaged_png": damaged,
        "artifacts": [str(transformed_path), str(proofed_path), export_report["path"], str(damaged_path)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("debugCapture/painter/color_management"))
    args = parser.parse_args()
    report = build_report(args.output)
    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(report_path.resolve()), "claims": report["claims"]}, ensure_ascii=False))
    return 0 if all(report["claims"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
