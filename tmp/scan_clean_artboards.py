"""Find artboards of a .fig whose UMG preflight has no blocked layer."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

QApplication([])

from app.painter_ui_figma import import_fig_file
from app.painter_ui_umg_adapter import preflight_painter_umg

start = time.monotonic()
source = Path(sys.argv[1]).expanduser().resolve()
document, _ = import_fig_file(source)
boards = document.get("artboards") or []
print(f"[{time.monotonic()-start:6.1f}s] {len(boards)} artboards", flush=True)

clean = []
for index, board in enumerate(boards):
    try:
        report = preflight_painter_umg(document, artboard_id=str(board["id"]))
    except Exception as error:  # noqa: BLE001 - survey harness
        print(f"  {index}: error {type(error).__name__}", flush=True)
        continue
    counts = dict(report.get("counts") or {})
    if report.get("ok") and not counts.get("Blocked"):
        name = str(board.get("name")).encode("ascii", "replace").decode("ascii")
        clean.append((name, str(board["id"]), counts))
        print(f"  CLEAN {name!r} {counts}", flush=True)
print(f"[{time.monotonic()-start:6.1f}s] clean artboards: {len(clean)}", flush=True)
