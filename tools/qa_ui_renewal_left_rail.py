from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


YOUTUBE_IMPORTS = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports")


def _real_media_candidates(limit: int = 3) -> list[Path]:
    candidates: list[Path] = []
    if YOUTUBE_IMPORTS.exists():
        try:
            files = [
                p
                for p in YOUTUBE_IMPORTS.iterdir()
                if p.is_file()
                and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
                and ".part" not in p.name.lower()
            ]
            files.sort(key=lambda p: p.stat().st_size)
            candidates.extend(files[:limit])
        except Exception:
            pass
    if len(candidates) < limit:
        for rel in (
            "qa_corpus/review_demos/media/overview_screen_demo.mp4",
            "qa_corpus/review_demos/media/screenstudio_cursor_demo.mp4",
            "qa_corpus/color_audio_samples/dialogue_noise_cleanup_reference.wav",
        ):
            p = ROOT / rel
            if p.exists():
                candidates.append(p)
            if len(candidates) >= limit:
                break
    return candidates[:limit]


def run_left_rail_qa(
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_left_rail_round",
) -> dict:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

    from app.font_fallback import apply_ui_font
    from app.media_pool import MediaPool
    from app.style import APP_QSS

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)

    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    host = QWidget()
    host.setObjectName("LeftRailRenewalQA")
    host.setStyleSheet(
        "QWidget#LeftRailRenewalQA{background:#0E1014;border:1px solid #20252B;}"
    )
    layout = QHBoxLayout(host)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(0)

    pool = MediaPool(host)
    pool.setFixedWidth(270)
    added: list[str] = []
    for path in _real_media_candidates():
        if pool.add_path(path):
            added.append(str(path))
    layout.addWidget(pool)
    host.resize(286, 640)
    host.show()
    app.processEvents()

    png = out / "media_pool_left_rail.png"
    ok = bool(host.grab().save(str(png)))
    host.close()
    host.deleteLater()
    app.processEvents()

    report = {
        "ok": ok and bool(added),
        "artifact": str(png.resolve()),
        "media_count": len(added),
        "media": added,
    }
    (out / "ui_renewal_left_rail_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = run_left_rail_qa()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
