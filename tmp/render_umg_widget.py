"""Render the generated Widget Blueprint to a PNG through the plugin.

Reading WidgetTree back through the Python API is not possible here -- the
property is not exposed on the blueprint, its generated class, or the CDO -- so
the honest way to tell whether the authored font took effect is to render the
widget and count the text rows in the pixels.

    .venv/Scripts/python.exe tmp/render_umg_widget.py
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
OUTPUT = ROOT / "debugCapture" / "umg_auto_layout_render.png"

SCRIPT = '''
import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(["/Game/TigerStudio"], True)

subsystem = unreal.get_editor_subsystem(unreal.TigerStudioUMGImportSubsystem)
result = subsystem.render_widget_blueprint_to_png(
    {asset!r},
    {output!r},
    unreal.Vector2D(1280.0, 720.0),
)


def read(value, *names):
    for name in names:
        try:
            return value.get_editor_property(name)
        except Exception:
            pass
        try:
            return getattr(value, name)
        except Exception:
            pass
    return None


unreal.log("TIGERRENDER ok=" + str(read(result, "success", "b_success")))
unreal.log("TIGERRENDER message=" + str(read(result, "message")))
unreal.log("TIGERRENDER output=" + str(read(result, "output_path")))
unreal.log("TIGERRENDER size=" + str(read(result, "width")) + "x" + str(read(result, "height")))
'''


def main() -> int:
    script_path = Path(tempfile.mkdtemp(prefix="tigerrender_")) / "render.py"
    script_path.write_text(
        SCRIPT.format(asset=ASSET, output=str(OUTPUT)),
        encoding="utf-8",
    )
    subprocess.run(
        [
            str(EDITOR_CMD),
            str(PROJECT),
            f"-ExecutePythonScript={script_path.as_posix()}",
            "-unattended",
            "-nop4",
            "-nosplash",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=1800,
    )
    log = PROJECT.parent / "Saved" / "Logs" / "HostProject.log"
    if log.is_file():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if "TIGERRENDER" in line or "LogPython: Error" in line:
                print(line.strip())
    print("png exists:", OUTPUT.is_file(), OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
