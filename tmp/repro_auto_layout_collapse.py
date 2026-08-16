from __future__ import annotations

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.painter_ui_figma import import_fig_file

FIG_PATH = Path.home() / "Downloads" / "Figma auto layout playground (Community).fig"


def main() -> None:
    document, report = import_fig_file(FIG_PATH)
    print("warnings:", len(report.get("warnings", [])))
    for warning in report.get("warnings", [])[:20]:
        print("  warn:", warning)

    objects = document.get("objects", [])
    by_id = {str(obj["id"]): obj for obj in objects}
    children_by_parent: dict[str, list[dict]] = {}
    for obj in objects:
        parent_id = obj.get("parent_id")
        if parent_id is not None:
            children_by_parent.setdefault(str(parent_id), []).append(obj)

    candidates = [
        obj for obj in objects
        if str(obj.get("kind")) in {"frame", "group"}
        and str(obj.get("name", "")).strip().casefold() == "auto layout"
    ]
    print(f"\nfound {len(candidates)} frame/group object(s) named exactly 'Auto Layout':")
    for obj in candidates:
        print(
            f"  id={obj['id']} name={obj.get('name')!r} kind={obj.get('kind')} "
            f"parent_id={obj.get('parent_id')}"
        )

    def dump(obj: dict, depth: int) -> None:
        oid = str(obj["id"])
        layout = obj.get("layout") or {}
        indent = "  " * depth
        print(
            f"{indent}- id={oid} name={obj.get('name')!r} kind={obj.get('kind')} "
            f"visible={obj.get('visible')} size=({obj.get('width')},{obj.get('height')}) "
            f"pos=({obj.get('x')},{obj.get('y')}) mode={layout.get('mode')} "
            f"w_sizing={layout.get('width_sizing')} h_sizing={layout.get('height_sizing')} "
            f"positioning={layout.get('positioning')}"
        )
        if depth >= 4:
            return
        for kid in children_by_parent.get(oid, []):
            dump(kid, depth + 1)

    for obj in candidates:
        print(f"\n--- tree for {obj.get('name')!r} ---")
        dump(obj, 0)


if __name__ == "__main__":
    main()
