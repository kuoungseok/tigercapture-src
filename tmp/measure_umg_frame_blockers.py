"""Break down one artboard's UMG blockers, and price each gate marginally.

Whole-document reason histograms hid the answer earlier: most objects carry
several reasons at once, so "635 objects mention strokes" is not the same as
"635 objects unlock when strokes work". This reports, per artboard, both the
raw reason counts and the marginal unlock — how many objects have a reason set
that is a subset of the gates being lifted.

    .venv/Scripts/python.exe tmp/measure_umg_frame_blockers.py <file.fig> <frame>
"""
from __future__ import annotations

import collections
import itertools
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    source_path = Path(sys.argv[1]).expanduser().resolve()
    wanted = sys.argv[2] if len(sys.argv) > 2 else ""

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    from app.painter_ui_figma import import_fig_file
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, _ = import_fig_file(source_path)
    boards = document.get("artboards") or []
    exact = [row for row in boards if str(row.get("name")) == wanted]
    targets = exact or [
        row for row in boards
        if wanted.casefold() in str(row.get("name")).casefold()
    ]
    if not targets:
        print("frame not found")
        return 2

    board = targets[0]
    board_id = str(board.get("id"))
    safe = str(board.get("name")).encode("ascii", "replace").decode("ascii")
    projection = project_painter_ui_umg_widgets(document, artboard_id=board_id)

    widgets = [
        row for row in projection.get("widgets") or []
        if isinstance(row, dict)
    ]
    blocked = [
        row for row in widgets
        if str(row.get("disposition") or "") == "Blocked"
    ]
    print(f"=== {safe} ===")
    print(f"widgets={len(widgets)}  blocked={len(blocked)}")

    reason_sets = [
        frozenset(str(value) for value in row.get("reasons") or [])
        for row in blocked
    ]
    counts = collections.Counter(
        reason for row in reason_sets for reason in row
    )
    print("\n-- raw reason counts --")
    for reason, count in counts.most_common(20):
        print(f"{count:5d}  {reason}")

    print("\n-- reason-set sizes --")
    for size, count in sorted(
        collections.Counter(len(row) for row in reason_sets).items()
    ):
        print(f"  {count:5d} objects carry {size} reason(s)")

    print("\n-- most common exact reason sets --")
    for combo, count in collections.Counter(reason_sets).most_common(5):
        print(f"{count:5d}  " + " + ".join(sorted(combo)))

    gates = [reason for reason, _ in counts.most_common(10)]
    print("\n-- marginal unlock: lifting ONE gate --")
    for gate in gates:
        freed = sum(1 for row in reason_sets if row <= {gate})
        print(f"{freed:5d}  {gate}")

    print("\n-- marginal unlock: lifting gate PAIRS/TRIPLES (top 8) --")
    scored: list[tuple[int, tuple[str, ...]]] = []
    for size in (2, 3, 4, 5):
        for combo in itertools.combinations(gates[:8], size):
            allowed = set(combo)
            freed = sum(1 for row in reason_sets if row <= allowed)
            scored.append((freed, combo))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    seen: set[int] = set()
    shown = 0
    for freed, combo in scored:
        if freed in seen or freed == 0:
            continue
        seen.add(freed)
        print(f"{freed:5d}  " + " + ".join(combo))
        shown += 1
        if shown >= 8:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
