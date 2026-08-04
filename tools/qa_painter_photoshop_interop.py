"""Prepare and finalize an actual Adobe Photoshop Painter interchange corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_file_exchange import export_flat_image, export_layered_psd
from app.painter_interop_evidence import sha256_file, validate_external_interop_report


def _model(name: str, layer_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name, layer_id=layer_id, node_type="paint", parent_id="",
        visible=True, opacity=100, blend_mode="normal", clipping=False,
        mask=[], layer_type="standard", expanded=True,
    )


def _rgba8(width: int = 64, height: int = 48) -> Image.Image:
    yy, xx = np.mgrid[0:height, 0:width]
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = (xx * 255 // (width - 1)).astype(np.uint8)
    rgba[..., 1] = (yy * 255 // (height - 1)).astype(np.uint8)
    rgba[..., 2] = ((xx + yy) * 255 // (width + height - 2)).astype(np.uint8)
    rgba[..., 3] = ((xx * 3 + yy * 5) % 256).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def _composite_rgba(path: Path) -> Image.Image:
    if path.suffix.casefold() == ".psd":
        from psd_tools import PSDImage
        rendered = PSDImage.open(path).composite(force=True)
        if rendered is None:
            raise ValueError(f"PSD has no composite: {path}")
        return rendered.convert("RGBA")
    with Image.open(path) as image:
        image.load()
        return image.convert("RGBA")


def prepare(folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    for stale in [
        *folder.glob("photoshop_roundtrip_*.psd"),
        folder / "photoshop_observation.json",
        folder / "report.json",
    ]:
        if stale.is_file():
            stale.unlink()
    nonce = uuid4().hex
    (folder / "run_nonce.txt").write_text(nonce, encoding="utf-8")
    image8 = _rgba8()
    ramp = np.linspace(0, 65535, 64 * 48, dtype=np.uint16).reshape(48, 64)
    rgba16 = np.stack((ramp, np.flip(ramp, axis=1), ramp // 2, np.full_like(ramp, 65535)), axis=2)
    reports = [
        export_flat_image(folder / "tiger_png8.png", image8, bit_depth=8),
        export_flat_image(folder / "tiger_png16.png", rgba16, bit_depth=16),
        export_flat_image(folder / "tiger_tiff16.tiff", rgba16, bit_depth=16),
    ]
    bottom = Image.new("RGBA", image8.size, (18, 34, 58, 255))
    middle = Image.new("RGBA", image8.size, (0, 0, 0, 0))
    top = Image.new("RGBA", image8.size, (0, 0, 0, 0))
    for y in range(10, 38):
        for x in range(8, 42):
            middle.putpixel((x, y), (210, 88, 42, 220))
    for y in range(4, 16):
        for x in range(44, 58):
            top.putpixel((x, y), (250, 220, 90, 180))
    composite = Image.alpha_composite(Image.alpha_composite(bottom, middle), top)
    psd = export_layered_psd(folder / "tiger_layers.psd", [
        {"model": _model("Bottom", "bottom"), "image": bottom},
        {"model": _model("Middle", "middle"), "image": middle},
        {"model": _model("Top", "top"), "image": top},
    ], size=image8.size, composite=composite)
    prepared = {
        "schema": "tigerstudio.painter.photoshop-interop-preparation.v1",
        "run_nonce": nonce,
        "internal_exports": [*reports, psd],
    }
    (folder / "preparation.json").write_text(json.dumps(prepared, indent=2), encoding="utf-8")
    return prepared


def finalize(folder: Path) -> dict:
    preparation = json.loads((folder / "preparation.json").read_text(encoding="utf-8"))
    observation = json.loads((folder / "photoshop_observation.json").read_text(encoding="utf-8-sig"))
    nonce_matches = observation.get("run_nonce") == preparation.get("run_nonce")
    observations = list(observation.get("observations") or [])
    by_name = {row["source_name"]: row for row in observations}
    artifacts = []
    for row in observations:
        path = Path(row["roundtrip_path"])
        source_path = folder / row["source_name"]
        alpha_parity = {"compared": False, "max_delta": None, "within_tolerance": False}
        if path.is_file() and source_path.is_file():
            source_alpha = np.asarray(_composite_rgba(source_path).getchannel("A"), dtype=np.int16)
            roundtrip_alpha = np.asarray(_composite_rgba(path).getchannel("A"), dtype=np.int16)
            if source_alpha.shape == roundtrip_alpha.shape:
                max_delta = int(np.abs(source_alpha - roundtrip_alpha).max()) if source_alpha.size else 0
                alpha_parity = {"compared": True, "max_delta": max_delta, "within_tolerance": max_delta <= 1}
        artifacts.append({
            "path": str(path),
            "sha256": sha256_file(path) if path.is_file() else "",
            "opened_by_external_app": True,
            "created_by_external_app": True,
            "source_name": row["source_name"],
            "alpha_parity": alpha_parity,
        })
    external = {
        **observation,
        "artifacts": artifacts,
    }
    validation = validate_external_interop_report(external)
    sixteen = [by_name.get("tiger_png16.png", {}), by_name.get("tiger_tiff16.tiff", {})]
    layer_names = list(by_name.get("tiger_layers.psd", {}).get("layer_names") or [])
    claims = {
        "fresh_external_run": bool(nonce_matches),
        "all_sources_opened": len(observations) == 4,
        "png8_is_8bit": "EIGHT" in str(by_name.get("tiger_png8.png", {}).get("bits_per_channel", "")).upper(),
        "png_tiff_are_16bit": all("SIXTEEN" in str(row.get("bits_per_channel", "")).upper() for row in sixteen),
        "icc_profile_seen": all(bool(row.get("color_profile_name")) for row in observations),
        "alpha_roundtrip_preserved": all(row["alpha_parity"]["within_tolerance"] for row in artifacts),
        "layer_order_preserved": layer_names in (["Top", "Middle", "Bottom"], ["Bottom", "Middle", "Top"]),
        "roundtrip_artifacts_valid": bool(validation["valid"]),
    }
    report = {
        "schema": "tigerstudio.painter.photoshop-interop-qa.v1",
        "evidence_class": "measured_external_application",
        "producer": observation.get("producer"),
        "producer_version": observation.get("producer_version"),
        "execution": observation.get("execution"),
        "run_nonce": observation.get("run_nonce"),
        "claims": claims,
        "observations": observations,
        "artifacts": artifacts,
        "validation": validation,
    }
    (folder / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "finalize"))
    parser.add_argument("--output", type=Path, default=Path("debugCapture/painter/external_interop"))
    args = parser.parse_args()
    report = prepare(args.output) if args.stage == "prepare" else finalize(args.output)
    print(json.dumps({"stage": args.stage, "schema": report["schema"], "claims": report.get("claims")}, ensure_ascii=False))
    return 0 if args.stage == "prepare" or all(report["claims"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
