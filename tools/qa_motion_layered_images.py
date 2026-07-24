"""Generate layered-image Motion QA evidence from durable repository assets."""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.image_decomposition import (
    compile_decomposition_layers,
    decompose_image,
)
from app.motion_designer.image_motion_validation import (
    validate_compiled_image_layers,
)
from app.motion_designer.schema import MotionComposition


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_layered_images_qa"


@dataclass(frozen=True)
class QASample:
    sample_id: str
    source: Path
    width: int
    height: int


def default_samples() -> list[QASample]:
    return [
        QASample(
            "feature_collage_16x9",
            ROOT / "resources" / "branding"
            / "tiger_studio_actual_feature_collage_no_center_girl_v21.png",
            640,
            360,
        ),
        QASample(
            "character_9x16",
            ROOT / "qa_corpus" / "actor_golden"
            / "live2d_Hiyori.model3_1b74efa9c33fde9b.png",
            360,
            640,
        ),
        QASample(
            "brand_graphic_1x1",
            ROOT / "resources" / "branding" / "tiger_studio_logo.png",
            480,
            480,
        ),
    ]


def _contact_sheet(paths: Iterable[Path], output: Path) -> Path:
    images = [Image.open(path).convert("RGB") for path in paths]
    if not images:
        raise ValueError("contact sheet requires at least one image")
    thumb_width = 320
    thumbs: list[Image.Image] = []
    for image in images:
        height = max(1, round(image.height * thumb_width / max(1, image.width)))
        thumbs.append(image.resize((thumb_width, height), Image.Resampling.LANCZOS))
    canvas = Image.new(
        "RGB",
        (thumb_width * len(thumbs), max(item.height for item in thumbs) + 34),
        (16, 18, 23),
    )
    painter = ImageDraw.Draw(canvas)
    for index, image in enumerate(thumbs):
        x = index * thumb_width
        canvas.paste(image, (x, 0))
        painter.text((x + 8, image.height + 9), ("START", "MIDDLE", "END")[index], fill=(232, 235, 240))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def run_qa(
    *,
    output_dir: Path = DEFAULT_OUTPUT,
    render_mp4: bool = True,
    force_analysis: bool = False,
) -> dict:
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_root = output_dir / "cache"
    renderer = MotionExportRenderer()
    reports: list[dict] = []
    started = time.perf_counter()

    for sample in default_samples():
        if not sample.source.is_file():
            reports.append({
                "sample_id": sample.sample_id,
                "ok": False,
                "error": f"missing durable source: {sample.source}",
            })
            continue
        sample_dir = output_dir / sample.sample_id
        decomposition = decompose_image(
            sample.source,
            width=sample.width,
            height=sample.height,
            max_elements=7,
            include_depth=True,
            segmentation_mode="auto",
            inpaint_mode="auto",
            reconstruct_text=True,
            cache_root=cache_root,
            force=force_analysis,
        )
        variants: dict[str, dict] = {}
        for variant in ("clean", "dynamic", "collage"):
            composition = MotionComposition(
                name=f"{sample.sample_id} / {variant}",
                width=sample.width,
                height=sample.height,
                fps=30.0,
                duration_ms=3000,
            )
            layers = compile_decomposition_layers(
                composition,
                decomposition,
                reference_id=sample.sample_id,
                name=sample.sample_id,
                in_ms=0,
                out_ms=3000,
                center=(sample.width / 2.0, sample.height / 2.0),
                size=(sample.width, sample.height),
                beat_id="qa_beat",
                motion_style="active reveal",
                motion_variant=variant,
                prompt=f"{variant} layered image motion quality assurance",
                audio_hits_ms=(320, 760, 1220),
            )
            composition.layers = layers
            validation = validate_compiled_image_layers(layers)
            variant_dir = sample_dir / variant
            times = [0, 1500, 2999]
            frames = [
                renderer.save_png(
                    composition,
                    time_ms,
                    variant_dir / f"frame_{time_ms:04d}ms.png",
                )
                for time_ms in times
            ]
            sheet = _contact_sheet(frames, variant_dir / "contact_sheet.png")
            mp4_path = ""
            if render_mp4 and variant == "dynamic":
                mp4_path = str(
                    renderer.export_mp4(
                        composition,
                        variant_dir / "dynamic_preview.mp4",
                        fps=12.0,
                    ).resolve()
                )
            variants[variant] = {
                "ok": validation.ok,
                "validation": validation.to_dict(),
                "layer_count": len(layers),
                "frames": [str(item.resolve()) for item in frames],
                "contact_sheet": str(sheet.resolve()),
                "mp4": mp4_path,
            }
        reports.append({
            "sample_id": sample.sample_id,
            "ok": bool(
                decomposition.diagnostics.get("validation", {}).get("ok")
                and all(item["ok"] for item in variants.values())
            ),
            "source": str(sample.source.resolve()),
            "canvas": [sample.width, sample.height],
            "algorithm": decomposition.algorithm,
            "provider": decomposition.diagnostics.get("segmentation_backend"),
            "decomposition_validation": decomposition.diagnostics.get("validation"),
            "motion_locked_component_count": decomposition.diagnostics.get(
                "motion_locked_component_count", 0
            ),
            "variants": variants,
        })

    report = {
        "schema": "tigerstudio.motion.layered_image_qa.v1",
        "ok": bool(reports) and all(item.get("ok") for item in reports),
        "sample_count": len(reports),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "output_dir": str(output_dir),
        "samples": reports,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-mp4", action="store_true")
    parser.add_argument("--force-analysis", action="store_true")
    args = parser.parse_args()
    report = run_qa(
        output_dir=args.output_dir,
        render_mp4=not args.no_mp4,
        force_analysis=args.force_analysis,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
