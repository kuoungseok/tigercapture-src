"""Measure what the UMG projection drops, per artboard, against the source.

The widget view shows the source document on the left and
``project_painter_ui_umg_widgets(...)["document"]`` on the right, so "UMG looks
completely different" is a claim about that projection, not about the renderer.
This counts objects and diffs rendered pixels so the gap is a number.

    .venv/Scripts/python.exe tmp/measure_umg_projection.py <file.fig> [frame]
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


def _render(document, artboard_id):
    from app.painter_ui_asset_export import render_ui_artboard

    return render_ui_artboard(document, artboard_id)


def main() -> int:
    source_path = Path(sys.argv[1]).expanduser().resolve()
    wanted = (
        sys.argv[2]
        if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
        else ""
    )

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    from app.painter_ui_figma import import_fig_file
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, report = import_fig_file(source_path)
    boards = document.get("artboards") or []
    print(f"imported {len(boards)} artboards, {len(document.get('objects') or [])} objects")

    exact = [row for row in boards if str(row.get("name")) == wanted]
    targets = exact or [
        row
        for row in boards
        if not wanted or wanted.casefold() in str(row.get("name")).casefold()
    ]
    if not targets:
        print(f"frame {wanted!r} not found; frames = "
              + ", ".join(
                  str(r.get('name')).encode('ascii', 'replace').decode('ascii')
                  for r in boards[:40]
              ))
        return 2

    for board in targets:
        board_id = str(board.get("id"))
        name = str(board.get("name"))
        reference = "--reference" in sys.argv
        projection = project_painter_ui_umg_widgets(
            document,
            artboard_id=board_id,
            reference_unrendered=reference,
        )
        counts = dict(projection.get("counts") or {})
        source_objects = [
            row
            for row in (document.get("objects") or [])
            if str(row.get("artboard_id") or "") == board_id
        ]
        projected = projection.get("document") or {}
        projected_objects = [
            row
            for row in (projected.get("objects") or [])
            if str(row.get("artboard_id") or "") == board_id
        ]
        print(f"\n=== {name} ({board.get('width')}x{board.get('height')}) ===")
        print(f"ok={projection.get('ok')}  counts={counts}")
        print(f"source objects on board: {len(source_objects)}")
        print(f"projected objects on board: {len(projected_objects)}")

        source_ids = {str(r.get("id")) for r in source_objects}
        projected_ids = {str(r.get("id")) for r in projected_objects}
        dropped = source_ids - projected_ids
        added = projected_ids - source_ids
        print(f"dropped ids: {len(dropped)}   added ids: {len(added)}")

        by_kind = collections.Counter(
            str(r.get("kind") or "?")
            for r in source_objects
            if str(r.get("id")) in dropped
        )
        if by_kind:
            print("dropped by kind: " + ", ".join(
                f"{k}={v}" for k, v in by_kind.most_common()
            ))

        kept = [r for r in source_objects if str(r.get("id")) in projected_ids]
        changed = 0
        for row in kept:
            twin = next(
                (p for p in projected_objects if str(p.get("id")) == str(row.get("id"))),
                None,
            )
            if twin is None:
                continue
            if (row.get("style") or {}) != (twin.get("style") or {}):
                changed += 1
        print(f"kept but restyled: {changed} / {len(kept)}")

        try:
            left = _render(document, board_id)
            right = _render(projected, board_id)
        except Exception as error:  # noqa: BLE001 - measurement harness
            print(f"render unavailable: {type(error).__name__}: {error}")
            continue
        if left.size() != right.size():
            print(f"size mismatch {left.size()} vs {right.size()}")
            continue
        # Exact-colour diff is the wrong metric once reference rows are drawn
        # translucently: they add the missing art while deliberately not
        # matching its colour. "Content the view lost entirely" is the claim
        # being tested, so count pixels the source paints over the artboard
        # background that the target leaves as bare background.
        background = left.pixel(0, 0)
        differing = 0
        missing = 0
        source_content = 0
        total = left.width() * left.height()
        for y in range(left.height()):
            for x in range(left.width()):
                source_pixel = left.pixel(x, y)
                target_pixel = right.pixel(x, y)
                if source_pixel != target_pixel:
                    differing += 1
                if source_pixel != background:
                    source_content += 1
                    if target_pixel == background:
                        missing += 1
        print(f"pixel diff: {differing}/{total} = {differing / max(total, 1) * 100:.2f}%")
        print(
            f"missing content: {missing}/{source_content} = "
            f"{missing / max(source_content, 1) * 100:.2f}% of source content"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
