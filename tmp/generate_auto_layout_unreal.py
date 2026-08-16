"""Generate the Figma "Auto Layout" frame into Unreal without its blocked art.

The plugin fails closed: one Blocked layer refuses the whole document, and this
frame has 229 of them, nearly all the vector-shape gate. Dropping exactly those
objects leaves the text, buttons and frames -- the part that was actually fixed
-- so the authored label can be checked in a real Widget Blueprint instead of a
preview.

Blocked objects are removed wherever they live, including inside component
definitions on other artboards. Painter geometry is artboard-absolute, so any
child left behind by a removed parent is reparented to the artboard root and
keeps its exact position.

    .venv/Scripts/python.exe tmp/generate_auto_layout_unreal.py
"""
from __future__ import annotations

import json
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

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_figma import import_fig_file
from app.painter_ui_umg_adapter import package_painter_umg, preflight_painter_umg
from app.unreal_umg_workflow import run_unreal_umg_generation

FRAME = "Auto Layout"
PROJECT = (
    ROOT / "debugCapture" / "component_schema18_buildcheck" / "HostProject"
    / "HostProject.uproject"
)
OUT = ROOT / "debugCapture" / "umg_auto_layout_native_package"

_START = time.monotonic()


def step(message: str) -> None:
    print(f"[{time.monotonic() - _START:7.1f}s] {message}", flush=True)


def drop_objects(document: dict, removed: set[str]) -> dict:
    """Remove ids and reparent their surviving descendants to the artboard."""
    kept = [
        row
        for row in document["objects"]
        if str(row.get("id") or "") not in removed
    ]
    surviving = {str(row["id"]) for row in kept}
    for row in kept:
        parent_id = str(row.get("parent_id") or "")
        while parent_id and parent_id not in surviving:
            parent = next(
                (
                    other
                    for other in document["objects"]
                    if str(other.get("id") or "") == parent_id
                ),
                None,
            )
            parent_id = str(parent.get("parent_id") or "") if parent else ""
        row["parent_id"] = parent_id
    document["objects"] = kept

    # A component whose root object was blocked has no definition left to
    # generate, and the packaged document fails with
    # umg_component_root_layer_missing. Drop the component and detach every
    # reference to it so the surviving rows stay plain objects.
    components = [
        component
        for component in document.get("components") or []
        if str(component.get("root_object_id") or "") in surviving
    ]
    live_component_ids = {str(row.get("id") or "") for row in components}
    document["components"] = components
    for row in kept:
        if str(row.get("component_id") or "") not in live_component_ids:
            row["component_id"] = ""
            row["component_role"] = "none"
            row["component_source_object_id"] = ""
        if str(row.get("component_scope_id") or "") not in live_component_ids:
            row["component_scope_id"] = ""
            row["component_scope_source_object_id"] = ""
    return document


def main() -> int:
    source = (
        Path(os.environ["USERPROFILE"])
        / "Downloads"
        / "Figma auto layout playground (Community).fig"
    )
    step(f"importing {source.name}")
    document, _ = import_fig_file(source)
    board = next(
        row
        for row in document["artboards"]
        if str(row.get("name")) == FRAME
    )
    board_id = str(board["id"])
    document["active_artboard_id"] = board_id
    step(f"frame {FRAME!r} ({board['width']}x{board['height']})")

    for attempt in range(1, 6):
        report = preflight_painter_umg(document, artboard_id=board_id)
        counts = dict(report.get("counts") or {})
        # Painted containers are split into synthetic background/content rows
        # during conversion, so a blocker can name an id the source document
        # does not contain. Map it back to the container it came from.
        blocked = set()
        for row in report.get("blockers") or []:
            object_id = str(row.get("object_id") or "")
            if not object_id:
                continue
            for suffix in ("::umg-content", "::umg-background"):
                if object_id.endswith(suffix):
                    object_id = object_id[: -len(suffix)]
                    break
            blocked.add(object_id)
        step(f"pass {attempt}: counts={counts} blockers={len(blocked)}")
        if not counts.get("Blocked"):
            break
        before = len(document["objects"])
        document = normalize_ui_document(drop_objects(document, blocked))
        document["active_artboard_id"] = board_id
        step(f"  dropped {before - len(document['objects'])} objects")

    on_board = [
        row
        for row in document["objects"]
        if str(row.get("artboard_id") or "") == board_id
    ]
    labels = [
        str((row.get("content") or {}).get("text") or "")
        for row in on_board
        if str((row.get("content") or {}).get("text") or "")
    ]
    step(f"{len(on_board)} objects survive on the frame; labels={labels}")

    package = package_painter_umg(document, OUT, artboard_id=board_id)
    packaged = package["packaged_preflight"]
    step(
        f"packaged ok={package['ok']} counts={packaged['counts']} "
        f"blockers={len(packaged['blockers'])}"
    )
    for row in packaged["blockers"][:5]:
        step(f"  blocker {row.get('name')}: {row.get('reasons')}")

    result = run_unreal_umg_generation(
        PROJECT,
        package["document_path"],
        destination_root="/Game/TigerStudio/AutoLayout",
        timeout_seconds=1800,
    )
    step(f"generation ok={result.get('ok')}")
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in (
                    "ok",
                    "message",
                    "generated_asset_path",
                    "generated_asset_loaded",
                    "generated_widget_count",
                    "generated_component_count",
                    "errors",
                )
            },
            ensure_ascii=False,
            indent=2,
        )[:3000],
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
