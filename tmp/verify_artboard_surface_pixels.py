"""Prove the view-clipped artboard surfaces paint the same canvas pixels.

Renders the same document twice - once with surfaces clipped to the view, once
with the previous whole-board surfaces - and reports the worst per-channel
difference across every zoom and pan step.

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tmp/verify_artboard_surface_pixels.py
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_artboard_surface_zoom import (  # noqa: E402
    WIDGET_HEIGHT,
    WIDGET_WIDTH,
    build_document,
)

CASES = (
    ("overview 6%", 6, 0),
    ("overview 11%", 11, 0),
    ("fit 40%", 40, 0),
    ("100%", 100, 0),
    ("100% panned", 100, 3),
    ("240%", 240, 0),
    ("400%", 400, 0),
    ("400% panned", 400, 5),
    ("800%", 800, 0),
    ("800% panned", 800, 9),
)
PAN_DX = 90.0


def build_effects_document():
    """A board far wider than the canvas, with effects across the clip edge."""
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_masks import create_ui_mask

    document = create_ui_document(4000, 2600, name="Effects QA")
    gradient = {
        "type": "linear",
        "visible": True,
        "opacity": 1.0,
        "gradient": {
            "type": "linear",
            "start": {"x": 0.0, "y": 0.0},
            "end": {"x": 1.0, "y": 1.0},
            "width": {"x": 0.0, "y": 1.0},
            "stops": [
                {"position": 0.0, "color": "#2563EBFF"},
                {"position": 1.0, "color": "#F97316FF"},
            ],
        },
    }
    document, _backdrop = add_ui_object(
        document,
        kind="rectangle",
        name="Gradient Bed",
        x=1200,
        y=200,
        width=1400,
        height=900,
        style={"fills": [gradient], "fill": "#2563EB"},
    )
    document, _shadow = add_ui_object(
        document,
        kind="rectangle",
        name="Straddling Shadow",
        x=1500,
        y=300,
        width=700,
        height=400,
        style={
            "fill": "#111827",
            "radius": 24.0,
            "shadow": {"x": 40.0, "y": 30.0, "blur": 120.0, "spread": 20.0},
        },
    )
    document, _reach_back = add_ui_object(
        document,
        kind="rectangle",
        name="Offscreen Shadow Reaching Back",
        x=2100,
        y=500,
        width=300,
        height=300,
        style={
            "fill": "#DC2626",
            "shadow": {"x": -220.0, "y": 0.0, "blur": 200.0, "spread": 40.0},
        },
    )
    document, _glass = add_ui_object(
        document,
        kind="rectangle",
        name="Background Blur Glass",
        x=1400,
        y=700,
        width=600,
        height=320,
        style={
            "fill": "#FFFFFF44",
            "background_blur": 28.0,
            "radius": 18.0,
        },
    )
    document, _blurred = add_ui_object(
        document,
        kind="text",
        name="Blurred Label",
        x=1550,
        y=140,
        width=520,
        height=60,
        content={"text": "Layer blur across the clip edge"},
        style={
            "text_color": "#0F172A",
            "font_size": 44.0,
            "layer_blur": 6.0,
            "text_shadow": {"x": 8.0, "y": 8.0, "blur": 60.0},
        },
    )
    document, mask = add_ui_object(
        document,
        kind="rectangle",
        name="Alpha Mask",
        x=1300,
        y=1200,
        width=900,
        height=400,
        style={
            "fills": [
                {
                    "type": "linear",
                    "visible": True,
                    "opacity": 1.0,
                    "gradient": {
                        "type": "linear",
                        "start": {"x": 0.0, "y": 0.5},
                        "end": {"x": 1.0, "y": 0.5},
                        "width": {"x": 0.0, "y": 1.0},
                        "stops": [
                            {"position": 0.0, "color": "#FFFFFFFF"},
                            {"position": 1.0, "color": "#FFFFFF00"},
                        ],
                    },
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0,
        },
        content={
            "figma_mask": {
                "type": "alpha",
                "requires_raster_alpha": True,
                "workspace_rendering": "pixel_alpha",
            }
        },
    )
    document, target = add_ui_object(
        document,
        kind="frame",
        name="Masked Target",
        x=1300,
        y=1200,
        width=900,
        height=400,
        style={"fill": "#00000000", "stroke": "#00000000", "stroke_width": 0},
    )
    document, _child = add_ui_object(
        document,
        kind="rectangle",
        name="Masked Child",
        parent_id=target["id"],
        x=1300,
        y=1200,
        width=900,
        height=400,
        style={"fill": "#16A34AFF"},
    )
    document, _mask = create_ui_mask(
        document,
        mask["id"],
        target_ids=[target["id"]],
    )
    return document


def render(document, *, full_board: bool, zoom: int, pan_index: int):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_workspace import PainterUIDesignOverlay

    original = PainterUIDesignOverlay._artboard_surface_rect
    if full_board:
        def surface_rect(self, viewport):
            return (
                0,
                0,
                max(1, int(math.ceil(viewport.width()))),
                max(1, int(math.ceil(viewport.height()))),
            )

        PainterUIDesignOverlay._artboard_surface_rect = surface_rect
    try:
        overlay = PainterUIDesignOverlay()
        overlay.resize(WIDGET_WIDTH, WIDGET_HEIGHT)
        overlay.set_document(document)
        board = overlay._document["artboards"][0]
        scale = zoom / 100.0
        overlay._view_scale = scale
        overlay._view_offset = QPointF(
            -float(board["x"]) * scale + 40.0 - pan_index * PAN_DX,
            -float(board["y"]) * scale + 40.0,
        )
        frame = QImage(
            overlay.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        overlay.render(frame)
        overlay.close()
        overlay.deleteLater()
        return frame.copy()
    finally:
        PainterUIDesignOverlay._artboard_surface_rect = original


def compare(left, right) -> tuple[int, int]:
    worst = 0
    differing = 0
    for y in range(left.height()):
        for x in range(left.width()):
            a = left.pixel(x, y)
            b = right.pixel(x, y)
            if a == b:
                continue
            differing += 1
            for shift in (0, 8, 16, 24):
                worst = max(
                    worst,
                    abs(((a >> shift) & 0xFF) - ((b >> shift) & 0xFF)),
                )
    return worst, differing


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from app.painter_ui_templates import instantiate_ui_template

    documents = [
        ("synthetic", build_document()),
        ("effects across clip edge", build_effects_document()),
    ]
    for template_id in (
        "saas_dashboard",
        "analytics_command_center",
        "game_hud",
        "design_system_starter",
    ):
        documents.append(
            (template_id, instantiate_ui_template(template_id)[0])
        )
    total_pixels = WIDGET_WIDTH * WIDGET_HEIGHT
    failures = 0
    for source, document in documents:
      print(f"== {source}")
      for label, zoom, pan_index in CASES:
        before = render(
            document,
            full_board=True,
            zoom=zoom,
            pan_index=pan_index,
        )
        after = render(
            document,
            full_board=False,
            zoom=zoom,
            pan_index=pan_index,
        )
        worst, differing = compare(before, after)
        share = differing / total_pixels * 100.0
        status = "ok" if worst == 0 else f"DIFF worst={worst}"
        if worst:
            failures += 1
        print(
            f"  {label:<14} {status:<18} differing {differing} px "
            f"({share:.4f}%)"
        )
    del app
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
