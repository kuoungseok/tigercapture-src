"""Measure how buttons and text survive the UMG projection.

Game widgets carry their art as images, so shape fidelity matters far less than
whether the information and the interactive controls come through. This reports,
per kind, how many objects reach UMG, what blocks the rest, and — for the ones
that do arrive — whether their label text and fill colour changed.

    .venv/Scripts/python.exe tmp/measure_umg_button_text.py <file.fig> [frame]
"""
from __future__ import annotations

import collections
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_INFORMATION_KINDS = ("button", "text")


def _label(row) -> str:
    content = row.get("content")
    content = content if isinstance(content, dict) else {}
    return str(content.get("text") or "")


def main() -> int:
    source_path = Path(sys.argv[1]).expanduser().resolve()
    wanted = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else ""

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    from app.painter_ui_figma import import_fig_file
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, _ = import_fig_file(source_path)
    boards = document.get("artboards") or []
    exact = [row for row in boards if str(row.get("name")) == wanted]
    targets = exact or [
        row for row in boards
        if wanted and wanted.casefold() in str(row.get("name")).casefold()
    ] or boards

    totals: dict[str, collections.Counter] = {
        kind: collections.Counter() for kind in _INFORMATION_KINDS
    }
    reasons: dict[str, collections.Counter] = {
        kind: collections.Counter() for kind in _INFORMATION_KINDS
    }
    label_lost = collections.Counter()
    label_changed: list[tuple[str, str, str]] = []
    fill_changed: list[tuple[str, str, str, str]] = []

    for board in targets:
        board_id = str(board.get("id"))
        projection = project_painter_ui_umg_widgets(document, artboard_id=board_id)
        widgets_by_id = projection.get("widgets_by_id") or {}
        projected = {
            str(row.get("id")): row
            for row in (projection.get("document") or {}).get("objects", [])
        }
        for row in document.get("objects") or []:
            if str(row.get("artboard_id") or "") != board_id:
                continue
            kind = str(row.get("kind") or "")
            if kind not in _INFORMATION_KINDS:
                continue
            widget = widgets_by_id.get(str(row.get("id"))) or {}
            disposition = str(widget.get("disposition") or "absent")
            totals[kind][disposition] += 1
            if disposition == "Blocked":
                for reason in widget.get("reasons") or []:
                    reasons[kind][str(reason)] += 1
            twin = projected.get(str(row.get("id")))
            source_label = _label(row)
            if twin is None:
                if source_label:
                    label_lost[kind] += 1
                continue
            target_label = _label(twin)
            if source_label != target_label:
                label_changed.append((kind, source_label, target_label))
            source_fill = str((row.get("style") or {}).get("fill") or "")
            target_fill = str((twin.get("style") or {}).get("fill") or "")
            if source_fill != target_fill:
                fill_changed.append(
                    (kind, str(row.get("name") or ""), source_fill, target_fill)
                )

    print(f"artboards measured: {len(targets)}")
    for kind in _INFORMATION_KINDS:
        counter = totals[kind]
        total = sum(counter.values())
        print(f"\n=== {kind}: {total} source object(s) ===")
        for disposition, count in counter.most_common():
            share = count / max(total, 1) * 100
            print(f"  {disposition:10s} {count:5d}  ({share:5.1f}%)")
        if reasons[kind]:
            print("  top block reasons:")
            for reason, count in reasons[kind].most_common(6):
                print(f"    {count:5d}  {reason}")
        print(f"  labels lost with the object: {label_lost[kind]}")

    print(f"\nlabels changed in place: {len(label_changed)}")
    for kind, before, after in label_changed[:10]:
        print(f"  {kind}: {before!r} -> {after!r}")
    print(f"\nfills changed in place: {len(fill_changed)}")
    for kind, name, before, after in fill_changed[:10]:
        print(f"  {kind} {name!r}: {before} -> {after}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
