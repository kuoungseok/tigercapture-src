"""Capture the compact Painter UI named Styles library."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.painter_ui_document import (
    add_ui_object,
    add_ui_token,
    create_ui_document,
)
from app.painter_ui_style_library import PainterUIStyleLibrary
from app.painter_ui_styles import add_ui_style, apply_ui_style


def _sample() -> dict:
    document = create_ui_document(1440, 900, name="Desktop")
    document, token = add_ui_token(
        document,
        name="Brand Blue",
        kind="color",
        token_value="#4B8FCA",
        scope=["style.fill"],
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Primary CTA",
        x=96,
        y=96,
        width=220,
        height=48,
        style={
            "fill": "#4B8FCA",
            "font_family": "Inter",
            "font_size": 16,
            "shadow": {"blur": 18, "color": "#00000042"},
        },
    )
    document["selection"] = {
        "object_id": button["id"],
        "object_ids": [button["id"]],
    }
    for name, kind, properties, bindings in (
        (
            "Brand / Primary",
            "color",
            {"fill": "#4B8FCA"},
            {"style.fill": token["id"]},
        ),
        (
            "Body / Strong",
            "text",
            {"font_family": "Inter", "font_size": 16},
            {},
        ),
        (
            "Elevation / Panel",
            "effect",
            {"shadow": {"blur": 18, "color": "#00000042"}},
            {},
        ),
    ):
        document, style = add_ui_style(
            document,
            name=name,
            kind=kind,
            properties=properties,
            token_bindings=bindings,
        )
        document, _ = apply_ui_style(
            document,
            target_id=button["id"],
            style_id=style["id"],
        )
    document, grid = add_ui_style(
        document,
        name="Desktop / 12 Column",
        kind="layout_grid",
        properties={
            "layout_grids": [
                {
                    "mode": "columns",
                    "count": 12,
                    "gutter": 24,
                    "margin": 80,
                }
            ]
        },
    )
    document, _ = apply_ui_style(
        document,
        target_id=document["active_artboard_id"],
        style_id=grid["id"],
    )
    return document


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    panel = PainterUIStyleLibrary()
    panel.resize(360, 650)
    panel.set_document(_sample())
    panel.show()
    app.processEvents()
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "painter_ui_designer_m3_named_styles.png"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not panel.grab().save(str(output)):
        raise RuntimeError(f"Failed to save Styles QA: {output}")
    print(output)
    panel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
