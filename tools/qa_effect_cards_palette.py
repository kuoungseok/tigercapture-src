from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_effect_cards_palette_qa(
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_effect_cards_palette_round",
) -> dict:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

    from app.effect_cards import (
        FadeCard,
        Live2DCard,
        SpeedCard,
        SpineCard,
        TypographyCard,
        ZoomCard,
    )
    from app.font_fallback import apply_ui_font
    from app.style import APP_QSS

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)

    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    host = QWidget()
    host.setObjectName("EffectCardsPaletteQA")
    host.setStyleSheet(
        "QWidget#EffectCardsPaletteQA{background:#101113;border:1px solid #25282E;}"
    )
    layout = QHBoxLayout(host)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    cards = [FadeCard(), ZoomCard(), TypographyCard(), SpeedCard(), SpineCard(), Live2DCard()]
    for card in cards:
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
    host.resize(10 + len(cards) * 40 + 10, 52)
    host.show()
    app.processEvents()

    png = out / "effect_cards_palette.png"
    ok = bool(host.grab().save(str(png)))
    speed_labels = [str(row[3]) for row in SpeedCard.PRESET_ENTRIES]
    host.close()
    host.deleteLater()
    app.processEvents()

    bad_label_markers = ("\ufffd", "\u59e8", "\u5360")
    report = {
        "ok": ok and not any(marker in label for marker in bad_label_markers for label in speed_labels),
        "artifact": str(png.resolve()),
        "card_count": len(cards),
        "speed_labels": speed_labels,
    }
    (out / "effect_cards_palette_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = run_effect_cards_palette_qa()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
