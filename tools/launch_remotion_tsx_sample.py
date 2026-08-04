"""Open a linked TSX source in Motion Designer and start loop playback."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.motion_designer.remotion_tsx import (
    create_remotion_tsx_layer,
    prepare_remotion_tsx_frames,
)
from app.motion_designer.schema import MotionComposition
from app.motion_designer.ui.window import MotionDesignerWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--duration-ms", type=int, default=3000)
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve(strict=True)
    prepared = prepare_remotion_tsx_frames(
        source,
        width=args.width,
        height=args.height,
        fps=args.fps,
        duration_ms=args.duration_ms,
        trusted=True,
    )
    composition = MotionComposition(
        name=f"Linked TSX - {source.stem}",
        width=args.width,
        height=args.height,
        fps=args.fps,
        duration_ms=args.duration_ms,
        layers=[create_remotion_tsx_layer(
            source,
            width=args.width,
            height=args.height,
            fps=args.fps,
            duration_ms=args.duration_ms,
            prepared=prepared,
        )],
    )
    app = QApplication.instance() or QApplication(sys.argv)
    window = MotionDesignerWindow(composition)
    window.setWindowTitle(f"Motion Designer - Linked TSX - {source.name}")
    window.resize(1180, 760)
    window.show()

    def start() -> None:
        window._set_loop_playback(True)
        window._set_playback_direction(1)

    QTimer.singleShot(300, start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
