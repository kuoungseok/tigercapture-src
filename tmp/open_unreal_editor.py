"""Open the Unreal Editor on the host project with a generated asset in front.

``-ExecCmds=Asset.Open ...`` is not a real console command, and a ``/Game/...``
argument passed through Git Bash is rewritten into a filesystem path, so the
first attempt opened the project with nothing on screen. The editor runs a
startup Python script instead, which is the mechanism the generation workflow
already uses.

    .venv/Scripts/python.exe tmp/open_unreal_editor.py "/Game/.../WBP_TS_x"
"""
from __future__ import annotations

import subprocess
import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path(r"D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe")
PROJECT = (
    ROOT / "debugCapture" / "component_schema18_buildcheck" / "HostProject"
    / "HostProject.uproject"
)

_OPEN_SCRIPT = '''
import unreal

ASSET_PATH = {asset!r}

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(["/Game/TigerStudio"], True)


def open_asset(delta_seconds):
    unreal.unregister_slate_post_tick_callback(handle)
    asset = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if asset is None:
        unreal.log_error("Tiger: asset not found: " + ASSET_PATH)
        return
    subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    subsystem.open_editor_for_assets([asset])
    unreal.log("Tiger: opened " + ASSET_PATH)


# The asset editor cannot open while the engine is still starting up, so this
# defers to the first Slate tick.
handle = unreal.register_slate_post_tick_callback(open_asset)
'''


def main() -> int:
    if not EDITOR.is_file():
        raise SystemExit(f"Unreal Editor not found: {EDITOR}")
    if not PROJECT.is_file():
        raise SystemExit(f"Host project not found: {PROJECT}")
    if len(sys.argv) < 2:
        raise SystemExit("usage: open_unreal_editor.py <asset object path>")

    asset = sys.argv[1]
    # Kept out of the temp tree so the -ExecCmds argument stays space-free.
    script_path = ROOT / "tmp" / "unreal_open_asset.py"
    script_path.write_text(_OPEN_SCRIPT.format(asset=asset), encoding="utf-8")

    command = [
        str(EDITOR),
        str(PROJECT),
        # NOT -ExecutePythonScript: that mode runs the script and then calls
        # UUnrealEdEngine::CloseEditor(), so the asset window appeared for an
        # instant and the editor quit. The py console command just runs the
        # file and leaves the editor up.
        f"-ExecCmds=py {script_path.as_posix()}",
        "-nosplash",
    ]
    print("asset:", asset, flush=True)
    print("script:", script_path, flush=True)
    subprocess.Popen(command, cwd=str(PROJECT.parent))
    print("launched", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
