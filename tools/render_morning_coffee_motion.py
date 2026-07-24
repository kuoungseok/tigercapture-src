"""Build and render the Morning Coffee Motion AI demonstration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.ai_generation import generate_motion_ai_proposal
from app.motion_designer.ai_workspace import MotionAIReference
from app.motion_designer.export_pipeline import MotionProfileExporter
from app.motion_designer.schema import (
    Keyframe,
    MotionBehaviorRef,
    MotionComposition,
    MotionLayer,
    SourceRef,
)


OUTPUT_DIR = ROOT / "outputs" / "motion_ai" / "morning_coffee"
HERO_IMAGE = OUTPUT_DIR / "morning_coffee_hero.png"
DURATION_MS = 8_000
WIDTH = 1_280
HEIGHT = 720
FPS = 30.0

PROMPT = """
Create a complete premium 8-second 16:9 morning-coffee motion graphic from the supplied hero image.
The image shows a warm sunrise apartment kitchen, a ceramic coffee cup on the right, and clean copy space on the left.
Return exactly four chronological beats that cover 0-8000 ms without overlap or gaps.
Use the image as a full-bleed reference in every beat. Keep movement restrained and cinematic: fades, holds, and gentle zoom only.
Use these exact on-screen English lines, one per beat, in this order:
1. GOOD MORNING
2. BREW SLOWLY
3. TAKE ONE QUIET SIP
4. START FRESH
Tone: warm, quiet, premium, editorial, optimistic. Avoid sales language, logos, extra copy, and busy layouts.
""".strip()

FALLBACK_BEATS = (
    (0, 2_000, "GOOD MORNING", "06:45 / THE CITY IS STILL QUIET"),
    (2_000, 4_000, "BREW SLOWLY", "HOT WATER / FRESHLY GROUND BEANS"),
    (4_000, 6_200, "TAKE ONE QUIET SIP", "ONE MINUTE THAT BELONGS TO YOU"),
    (6_200, 8_000, "START FRESH", "MAKE THE FIRST MOMENT YOURS"),
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _fade_pair(duration_ms: int, *, enter_ms: int = 520, exit_ms: int = 420) -> list[MotionBehaviorRef]:
    return [
        MotionBehaviorRef(
            kind="fade",
            start_ms=0,
            end_ms=min(enter_ms, duration_ms),
            params={"direction": "in", "easing": "ease_out", "hold_after": True},
        ),
        MotionBehaviorRef(
            kind="fade",
            start_ms=max(0, duration_ms - exit_ms),
            end_ms=duration_ms,
            params={"direction": "out", "easing": "ease_in", "hold_after": True},
        ),
    ]


def _text_layer(
    *,
    name: str,
    text: str,
    start_ms: int,
    end_ms: int,
    position: tuple[float, float],
    width: int,
    height: int,
    font_size: int,
    weight: int,
    color: str,
    tracking: float = 0.0,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(
            kind="typography",
            params={
                "text": text,
                "font_family": "Bahnschrift",
                "font_size": font_size,
                "font_weight": weight,
                "fill": color,
                "stroke_width": 0.0,
                "alignment": "left",
                "width": width,
                "height": height,
                "line_height": 1.08,
                "letter_spacing": tracking,
            },
        ),
        in_ms=start_ms,
        out_ms=end_ms,
        behaviors=_fade_pair(end_ms - start_ms),
        metadata={"generated_for": "morning_coffee_demo"},
    )
    layer.transform.anchor.default = [0.0, 0.5]
    layer.transform.position.default = [float(position[0]), float(position[1])]
    return layer


def _final_storyboard(provider_beats: list[dict]) -> list[dict]:
    result: list[dict] = []
    for index, (start_ms, end_ms, expected_text, supporting_text) in enumerate(FALLBACK_BEATS):
        provider = provider_beats[index] if index < len(provider_beats) else {}
        result.append({
            "index": index + 1,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "title": expected_text,
            "supporting_text": supporting_text,
            "purpose": str(provider.get("purpose") or "Morning ritual progression"),
            "motion": str(provider.get("motion") or ("fade" if index != 3 else "zoom_in")),
            "provider_beat_id": str(provider.get("id") or ""),
            "provider_text": str(provider.get("text") or ""),
        })
    return result


def _build_composition(base: MotionComposition, storyboard: list[dict], plan: dict) -> MotionComposition:
    composition = MotionComposition.from_dict(base.to_dict())
    composition.name = "Morning Coffee / Start Fresh"
    composition.revision += 1
    composition.layers = []
    composition.metadata.update({
        "demo": "morning_coffee_motion_ai",
        "storyboard_provider": plan.get("metadata", {}).get("provider_contract", {}).get("provider", "claude_mcp"),
        "storyboard_plan_id": str(plan.get("id") or ""),
        "editorial_adaptation": "single continuous hero shot with provider-authored four-beat pacing",
    })

    background = MotionLayer(
        name="Morning Coffee Hero",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(HERO_IMAGE.resolve()),
            params={"width": WIDTH, "height": HEIGHT, "fit": "cover"},
        ),
        in_ms=0,
        out_ms=DURATION_MS,
        metadata={"role": "hero_background", "ai_generated": True},
    )
    background.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[WIDTH / 2 + 8, HEIGHT / 2 + 7], interpolation="bezier"),
        Keyframe(time_ms=DURATION_MS, value=[WIDTH / 2 - 10, HEIGHT / 2 - 4], interpolation="bezier"),
    ]
    background.transform.scale.keyframes = [
        Keyframe(time_ms=0, value=[1.025, 1.025], interpolation="bezier"),
        Keyframe(time_ms=DURATION_MS, value=[1.085, 1.085], interpolation="bezier"),
    ]
    composition.layers.append(background)

    overlay = MotionLayer(
        name="Editorial Contrast Gradient",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle",
            "width": WIDTH,
            "height": HEIGHT,
            "fill": "#00000000",
            "stroke_width": 0.0,
            "gradient": {
                "type": "linear",
                "start": [0.0, 0.5],
                "end": [1.0, 0.5],
                "stops": [
                    {"position": 0.0, "color": "#D923160F"},
                    {"position": 0.48, "color": "#9B23160F"},
                    {"position": 0.74, "color": "#2023160F"},
                    {"position": 1.0, "color": "#0023160F"},
                ],
            },
        }),
        in_ms=0,
        out_ms=DURATION_MS,
        metadata={"role": "copy_contrast"},
    )
    overlay.transform.position.default = [WIDTH / 2, HEIGHT / 2]
    composition.layers.append(overlay)

    top_rule = MotionLayer(
        name="Top Accent Rule",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle", "width": 112, "height": 4,
            "fill": "#E6BE8A4E", "stroke_width": 0.0,
        }),
        in_ms=0,
        out_ms=DURATION_MS,
        behaviors=[MotionBehaviorRef(
            kind="slide", start_ms=0, end_ms=700,
            params={"direction": "in", "distance": [-80.0, 0.0], "hold_after": True},
        )],
    )
    top_rule.transform.anchor.default = [0.0, 0.5]
    top_rule.transform.position.default = [96.0, 94.0]
    composition.layers.append(top_rule)

    label = _text_layer(
        name="Morning Label",
        text="MORNING RITUAL  /  06:45",
        start_ms=0,
        end_ms=DURATION_MS,
        position=(96, 126),
        width=520,
        height=54,
        font_size=20,
        weight=500,
        color="#FFE9CDA8",
        tracking=2.0,
    )
    label.behaviors = [label.behaviors[0]]
    composition.layers.append(label)

    for beat in storyboard:
        start_ms = int(beat["start_ms"])
        end_ms = int(beat["end_ms"])
        title = str(beat["title"])
        title_size = 61 if len(title) <= 14 else 50
        composition.layers.append(_text_layer(
            name=f"Beat {beat['index']} Title",
            text=title,
            start_ms=start_ms,
            end_ms=end_ms,
            position=(96, 292),
            width=700,
            height=122,
            font_size=title_size,
            weight=600,
            color="#FFFFF8EF",
            tracking=0.6,
        ))
        composition.layers.append(_text_layer(
            name=f"Beat {beat['index']} Supporting Copy",
            text=str(beat["supporting_text"]),
            start_ms=start_ms + 170,
            end_ms=end_ms,
            position=(99, 384),
            width=690,
            height=62,
            font_size=20,
            weight=400,
            color="#FFE8D6C0",
            tracking=1.2,
        ))

    footer = _text_layer(
        name="Motion Signature",
        text="TIGER STUDIO  /  MOTION DESIGNER",
        start_ms=0,
        end_ms=DURATION_MS,
        position=(96, 652),
        width=520,
        height=40,
        font_size=14,
        weight=400,
        color="#BFEBDCCB",
        tracking=1.6,
    )
    footer.behaviors = [footer.behaviors[0]]
    composition.layers.append(footer)
    return composition


def main() -> int:
    if not HERO_IMAGE.is_file():
        raise FileNotFoundError(f"Missing generated hero image: {HERO_IMAGE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base = MotionComposition(
        name="Morning Coffee AI Draft",
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_ms=DURATION_MS,
    )
    reference = MotionAIReference(
        kind="image",
        name=HERO_IMAGE.name,
        uri=str(HERO_IMAGE.resolve()),
        mime_type="image/png",
        metadata={"description": "warm sunrise kitchen, coffee cup on right, copy space on left"},
    )
    proposal = generate_motion_ai_proposal(
        base,
        PROMPT,
        [reference],
        provider_id="claude_mcp",
        timeout_seconds=150,
    )
    proposal_payload = proposal.to_dict()
    plan = dict(proposal.analysis.get("generation_plan") or {})
    provider_beats = [dict(item) for item in plan.get("beats", []) if isinstance(item, dict)]
    storyboard = _final_storyboard(provider_beats)
    composition = _build_composition(base, storyboard, plan)

    _write_json(OUTPUT_DIR / "claude_proposal.json", proposal_payload)
    _write_json(OUTPUT_DIR / "scenario.json", {
        "title": "Morning Coffee / Start Fresh",
        "logline": "Before the city wakes, one deliberate cup creates a quiet starting line for the day.",
        "prompt": PROMPT,
        "image": str(HERO_IMAGE.resolve()),
        "provider": proposal.provider,
        "provider_warnings": list(proposal.warnings),
        "provider_storyboard": provider_beats,
        "final_storyboard": storyboard,
    })
    _write_json(OUTPUT_DIR / "composition.json", composition.to_dict())

    app = QApplication.instance() or QApplication([])
    exporter = MotionProfileExporter()
    preview_paths: list[str] = []
    for index, time_ms in enumerate((900, 2_900, 5_000, 7_000), start=1):
        path = OUTPUT_DIR / f"preview_{index}_{time_ms}ms.png"
        exporter.export(composition, "png_still", path, time_ms=time_ms)
        preview_paths.append(str(path.resolve()))
    video_path = OUTPUT_DIR / "morning_coffee_motion.mp4"
    export_result = exporter.export(composition, "h264_mp4", video_path, fps=FPS)
    app.processEvents()

    manifest = {
        "ok": True,
        "provider": proposal.provider,
        "provider_contract": proposal.analysis.get("provider_contract", {}),
        "duration_ms": DURATION_MS,
        "fps": FPS,
        "resolution": [WIDTH, HEIGHT],
        "layer_count": len(composition.layers),
        "preview_paths": preview_paths,
        "video_path": str(video_path.resolve()),
        "video_bytes": video_path.stat().st_size,
        "export": export_result,
    }
    _write_json(OUTPUT_DIR / "render_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
