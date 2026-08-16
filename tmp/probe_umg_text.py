"""Report what the generated Widget Blueprint actually holds for each text.

The document says Inter at 24 css px in a 454 px box, which wraps to three
lines. Reading the asset back is the only way to tell whether the font binding
survived generation or whether the widget is still on the engine default.

    .venv/Scripts/python.exe tmp/probe_umg_text.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR_CMD = Path(r"D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
PROJECT = (
    ROOT / "debugCapture" / "component_schema18_buildcheck" / "HostProject"
    / "HostProject.uproject"
)
ASSET = (
    "/Game/TigerStudio/AutoLayout/painter_figma_document_snapshot_figma_artboard_2411_13170"
    "/Widgets/WBP_TS_painter_figma_document_snapshot_figma_artboard_2411_13170"
)

SCRIPT = '''
import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(["/Game/TigerStudio"], True)

blueprint = unreal.EditorAssetLibrary.load_asset({asset!r})
unreal.log("TIGERPROBE asset=" + str(blueprint))

# WidgetTree is exposed in different places across UE versions, so try each.
generated = blueprint.generated_class()
tree = None
for label, holder in (
    ("generated_class", generated),
    ("cdo", unreal.get_default_object(generated)),
    ("blueprint", blueprint),
):
    try:
        tree = holder.get_editor_property("widget_tree")
    except Exception as error:
        unreal.log("TIGERPROBE no widget_tree on " + label + ": " + str(error)[:80])
        continue
    if tree is not None:
        unreal.log("TIGERPROBE widget_tree from " + label)
        break
if tree is None:
    raise SystemExit("no widget tree")
root = tree.get_editor_property("root_widget")

widgets = []


def walk(widget):
    if widget is None:
        return
    widgets.append(widget)
    if isinstance(widget, unreal.PanelWidget):
        for index in range(widget.get_children_count()):
            walk(widget.get_child_at(index))


walk(root)
unreal.log("TIGERPROBE widgets=" + str(len(widgets)))
count = 0
for widget in widgets:
    if not isinstance(widget, unreal.TextBlock):
        continue
    count += 1
    font = widget.get_editor_property("font")
    slot = widget.get_editor_property("slot")
    size = ""
    try:
        size = str(slot.get_editor_property("size"))
    except Exception:
        size = "(no size)"
    unreal.log(
        "TIGERPROBE text=" + repr(str(widget.get_text()))[:60]
        + " font_object=" + str(font.font_object)
        + " typeface=" + str(font.typeface_font_name)
        + " size=" + str(font.size)
        + " autowrap=" + str(widget.get_editor_property("auto_wrap_text"))
        + " slot_size=" + size
    )
unreal.log("TIGERPROBE textblocks=" + str(count))
'''


def main() -> int:
    script_path = Path(tempfile.mkdtemp(prefix="tigerprobe_")) / "probe.py"
    script_path.write_text(SCRIPT.format(asset=ASSET), encoding="utf-8")
    process = subprocess.run(
        [
            str(EDITOR_CMD),
            str(PROJECT),
            f"-ExecutePythonScript={script_path.as_posix()}",
            "-unattended",
            "-nop4",
            "-nosplash",
            "-nullrhi",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=1800,
    )
    blob = f"{process.stdout or ''}\n{process.stderr or ''}"
    hits = [
        line.strip()
        for line in blob.splitlines()
        if "TIGERPROBE" in line
        or "LogPython: Error" in line
        or "Traceback" in line
        or "AttributeError" in line
        or "TypeError" in line
    ]
    print("\n".join(hits) or "(no probe output)")
    if not hits:
        print("--- last 25 lines ---")
        print("\n".join(blob.splitlines()[-25:]))
    print("returncode:", process.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
