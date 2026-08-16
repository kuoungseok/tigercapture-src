"""Build only the editor modules of the UMG plugin and refresh the bundle.

``tools/build_unreal_umg_plugin.py`` runs RunUAT BuildPlugin, which builds the
editor target and then a game target in the same run. The editor target keeps
succeeding while the second invocation intermittently dies with
``Result: Failed (ConflictingInstance)`` -- UBT's own mutex is still held by the
invocation that just finished. The editor DLLs are the ones the generation path
loads, so this builds that target directly instead of waiting out a race.

    .venv/Scripts/python.exe tmp/build_plugin_editor_only.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(r"D:\UE_5.8\Engine")
SOURCE_PLUGIN = ROOT / "resources" / "unreal_plugins" / "UMG" / "TigerStudioUMG"
PROJECT = (
    ROOT / "debugCapture" / "component_schema18_buildcheck" / "HostProject"
    / "HostProject.uproject"
)
PROJECT_PLUGIN = PROJECT.parent / "Plugins" / "TigerStudioUMG"
BUNDLE = ROOT / "bundled" / "unreal_plugins" / "UMG" / "TigerStudioUMG"


def main() -> int:
    if not SOURCE_PLUGIN.is_dir():
        raise SystemExit(f"plugin source missing: {SOURCE_PLUGIN}")

    # The installed copy ships without Source, so the build needs it staged.
    staged_source = PROJECT_PLUGIN / "Source"
    if staged_source.exists():
        shutil.rmtree(staged_source)
    shutil.copytree(SOURCE_PLUGIN / "Source", staged_source)
    shutil.copy2(
        SOURCE_PLUGIN / "TigerStudioUMG.uplugin",
        PROJECT_PLUGIN / "TigerStudioUMG.uplugin",
    )
    print("staged plugin source into the host project", flush=True)

    command = [
        str(ENGINE / "Binaries" / "ThirdParty" / "DotNet" / "10.0" / "win-x64" / "dotnet.exe"),
        str(ENGINE / "Binaries" / "DotNET" / "UnrealBuildTool" / "UnrealBuildTool.dll"),
        "UnrealEditor",
        "Win64",
        "Development",
        f"-Project={PROJECT}",
        f"-plugin={PROJECT_PLUGIN / 'TigerStudioUMG.uplugin'}",
        "-noubtmakefiles",
        "-nohotreload",
    ]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=3600,
    )
    tail = (process.stdout or "").splitlines()[-30:]
    print("\n".join(tail), flush=True)
    if process.returncode != 0:
        print("stderr:", (process.stderr or "")[-2000:], flush=True)
        raise SystemExit(f"UnrealBuildTool failed: {process.returncode}")

    built = PROJECT_PLUGIN / "Binaries" / "Win64"
    target = BUNDLE / "Binaries" / "Win64"
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for item in built.glob("*"):
        if item.suffix.lower() in {".pdb", ".lib", ".exp"}:
            continue
        shutil.copy2(item, target / item.name)
        copied.append(item.name)
    print("refreshed bundle:", ", ".join(sorted(copied)), flush=True)

    # Leave the installed copy source-free the way the bundle ships it.
    shutil.rmtree(staged_source, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
