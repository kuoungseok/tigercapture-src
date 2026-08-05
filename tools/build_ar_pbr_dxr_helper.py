"""Build the native Tiger Studio DXR helper with the installed VS 2022 toolchain."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "ar_pbr_dxr_helper"
PROJECT = PROJECT_DIR / "TigerStudioDxrHelper.vcxproj"
BUILD_EXE = PROJECT_DIR / "bin" / "TigerStudioDxrHelper.exe"
OUTPUT_DIR = ROOT / "external" / "tools" / "ar_pbr_dxr"
VSWHERE = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
UE_DXCOMPILER = Path(r"D:\UE_5.8\Engine\Binaries\ThirdParty\ShaderConductor\Win64\dxcompiler.dll")
UE_DXIL = UE_DXCOMPILER.with_name("dxil.dll")


def _visual_studio() -> Path:
    result = subprocess.run(
        [
            str(VSWHERE),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    path = Path(result.stdout.strip())
    if not path.is_dir():
        raise RuntimeError("Visual Studio C++ toolchain was not found")
    return path


def build(*, probe: bool = True) -> dict[str, object]:
    visual_studio = _visual_studio()
    msbuild = visual_studio / "MSBuild" / "Current" / "Bin" / "MSBuild.exe"
    if not msbuild.is_file():
        raise RuntimeError(f"MSBuild was not found: {msbuild}")
    subprocess.run(
        [
            str(msbuild),
            str(PROJECT),
            "/m",
            "/t:Build",
            "/p:Configuration=Release",
            "/p:Platform=x64",
            "/verbosity:minimal",
        ],
        cwd=str(PROJECT_DIR),
        check=True,
    )
    if not BUILD_EXE.is_file():
        raise RuntimeError(f"DXR helper build output is missing: {BUILD_EXE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_exe = OUTPUT_DIR / BUILD_EXE.name
    shutil.copy2(BUILD_EXE, output_exe)
    shutil.copy2(PROJECT_DIR / "Raytrace.hlsl", OUTPUT_DIR / "Raytrace.hlsl")
    if not UE_DXCOMPILER.is_file():
        raise RuntimeError(f"Canonical UE 5.8 dxcompiler.dll is missing: {UE_DXCOMPILER}")
    shutil.copy2(UE_DXCOMPILER, OUTPUT_DIR / "dxcompiler.dll")
    if not UE_DXIL.is_file():
        raise RuntimeError(f"Canonical UE 5.8 dxil.dll is missing: {UE_DXIL}")
    shutil.copy2(UE_DXIL, OUTPUT_DIR / "dxil.dll")
    payload: dict[str, object] = {
        "ok": True,
        "helper": str(output_exe),
        "shader": str(OUTPUT_DIR / "Raytrace.hlsl"),
        "dxcompiler": str(OUTPUT_DIR / "dxcompiler.dll"),
        "dxil": str(OUTPUT_DIR / "dxil.dll"),
    }
    if probe:
        completed = subprocess.run(
            [str(output_exe), "--capabilities-json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        payload["probe_returncode"] = completed.returncode
        try:
            payload["probe"] = json.loads(completed.stdout or completed.stderr or "{}")
        except json.JSONDecodeError:
            payload["probe"] = {"raw": (completed.stdout or completed.stderr).strip()}
        if completed.returncode != 0:
            payload["ok"] = False
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-probe", action="store_true")
    args = parser.parse_args()
    payload = build(probe=not args.no_probe)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
