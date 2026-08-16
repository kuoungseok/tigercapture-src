"""How many of a click's _resolved_cache_key calls actually re-digest?"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = "E:/ClaudeCodeApp/GifCam"
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402
from app.actions.registry import ActionRegistry  # noqa: E402
from app.drawing import PaintDialog, create_blank_paint_pixmap  # noqa: E402
from app.painter_ui_figma import import_figma_json  # noqa: E402
import app.painter_ui_themes as T  # noqa: E402
import app.painter_ui_document as D  # noqa: E402

calls = []
_orig_key = T._resolved_cache_key
_orig_digest = D.canonical_payload_digest


def key(document):
    t = time.perf_counter()
    memo = T._CACHE_KEY_MEMO.get(id(document))
    ident = None
    try:
        objects = document.get("objects")
        ident = T._cache_key_identity(document, objects)
    except Exception:
        pass
    hit = memo is not None and memo[0] is document and memo[1] == ident
    r = _orig_key(document)
    calls.append((hit, (time.perf_counter() - t) * 1000, id(document),
                  ident[0] if ident else None, len(document)))
    return r


T._resolved_cache_key = key

QApplication.instance() or QApplication([])
d = PaintDialog(
    background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
    initial_strokes=[], time_ms=0, standalone=True,
)
ActionRegistry(owner=d).execute("paint.ui.workspace.set", {"mode": "ui_design"})
doc, _ = import_figma_json(ROOT + "/tmp/auto_layout_playground.json", image_dir=None)
d._painter_ui_document = doc
page = doc["active_page_id"]
boards = {r["id"] for r in doc["artboards"] if r["page_id"] == page}
ids = [r["id"] for r in doc["objects"] if r["artboard_id"] in boards][:8]
d._select_painter_ui_object(ids[0])

for i in range(3):
    calls.clear()
    t = time.perf_counter()
    d._select_painter_ui_object(ids[1 + i])
    wall = (time.perf_counter() - t) * 1000
    print(f"\nclick {i + 1}: {wall:.0f} ms, {len(calls)} key calls")
    for hit, ms, did, oid, nkeys in calls:
        print(f"   memo {'HIT ' if hit else 'MISS'} {ms:7.1f} ms  doc=0x{did:x} objs=0x{oid or 0:x} keys={nkeys}")
