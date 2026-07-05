"""Smoke QA for icon-first micro-interactions."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REQUIRED_ICONS = [
    "cursor", "scissors", "ripple", "roll", "slip", "slide",
    "sliders", "nest", "marker", "play", "speed", "palette",
    "project", "relink", "health", "scope", "mixer", "live2d", "spine",
]


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _pixmap_nonblank(icon_name: str) -> bool:
    from app.icons import app_icon, icon_size

    pix = app_icon(icon_name, size=32).pixmap(icon_size(32))
    if pix.isNull():
        return False
    image = pix.toImage()
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                return True
    return False


def _hover_label_ok(card: Any) -> bool:
    labels = list(getattr(card, "_hover_labels", []) or [])
    if not labels:
        return False
    try:
        card.enterEvent(None)
        entered = all(label.text() for label, _text in labels)
        card.leaveEvent(None)
        left = all(label.text() == "" for label, _text in labels)
    except Exception:
        return False
    return entered and left


def run_micro_interactions_qa() -> dict[str, Any]:
    _qapp()
    from app import effect_cards
    from app.recorder import _hotkey_label_from_pressed
    from app.screenstudio_polish import screenstudio_interaction_report
    from app.studio_theme import paint_timeline_burst

    icon_results = {name: _pixmap_nonblank(name) for name in REQUIRED_ICONS}
    interaction_report = screenstudio_interaction_report(
        [
            {"t_ms": 0, "x_norm": 0.25, "y_norm": 0.35, "kind": "click"},
            {"t_ms": 160, "x_norm": 0.45, "y_norm": 0.45, "kind": "drag"},
            {"t_ms": 360, "x_norm": 0.62, "y_norm": 0.50, "kind": "release"},
            {"t_ms": 520, "x_norm": 0.62, "y_norm": 0.50, "kind": "hotkey", "label": "Ctrl + S"},
        ],
        duration_ms=1800,
        frame_w=1280,
        frame_h=720,
    )
    card_classes = [
        effect_cards.FadeCard,
        effect_cards.ZoomCard,
        effect_cards.TypographyCard,
        effect_cards.SpeedCard,
        effect_cards.Live2DCard,
        effect_cards.SpineCard,
    ]
    cards = []
    for cls in card_classes:
        try:
            card = cls()
            cards.append({
                "class": cls.__name__,
                "hover_label": _hover_label_ok(card),
                "fixed_size": card.minimumWidth() > 0 or card.maximumWidth() > 0,
            })
            card.close()
        except Exception as exc:
            cards.append({"class": cls.__name__, "hover_label": False, "error": str(exc)})

    source = (ROOT / "app" / "video_editor_window.py").read_text(encoding="utf-8", errors="replace")
    style = (ROOT / "app" / "style.py").read_text(encoding="utf-8", errors="replace")
    checks = {
        "all_required_icons_nonblank": all(icon_results.values()),
        "palette_cards_have_rollover_labels": all(row.get("hover_label") for row in cards),
        "timeline_burst_painter_importable": callable(paint_timeline_burst),
        "trackrow_has_flash_timeline_burst": "def flash_timeline_burst" in source,
        "blade_tool_has_animated_entrypoints": (
            "self._install_icon_pulse(self.blade_btn" in source
            and "self._blade_at_playhead" in source
            and '"blade"' in source
        ),
        "global_hover_styles_present": style.count(":hover") >= 20,
        "global_pressed_styles_present": style.count(":pressed") >= 12,
        "hotkey_formatter_privacy_safe": (
            _hotkey_label_from_pressed({0x43}) == ""
            and _hotkey_label_from_pressed({0x11, 0x43}) == "Ctrl + C"
            and _hotkey_label_from_pressed({0x74}) == "F5"
        ),
        "screenstudio_interaction_report_ready": bool(interaction_report.get("ok")),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "summary": {
            "icons": len(icon_results),
            "icon_failures": [name for name, ok in icon_results.items() if not ok],
            "cards": len(cards),
            "hover_label_failures": [row["class"] for row in cards if not row.get("hover_label")],
            "screenstudio_interaction_warnings": list(interaction_report.get("warnings") or []),
        },
        "checks": checks,
        "icons": icon_results,
        "cards": cards,
        "screenstudio_interaction": interaction_report,
        "failures": failures,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run micro-interaction QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/micro_interactions_qa.json"))
    args = parser.parse_args()
    report = run_micro_interactions_qa()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
