"""Build the private Tiger Studio UMG source into a distribution-safe bundle."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "TigerStudioUMG"
DEFAULT_ENGINE_ROOT = Path(r"D:\UE_5.8\Engine")
SOURCE = ROOT / "resources" / "unreal_plugins" / "UMG" / PLUGIN_NAME
OUTPUT = ROOT / "bundled" / "unreal_plugins" / "UMG" / PLUGIN_NAME
PUBLIC_PARTS = ("Binaries", "Config", "Content", "Resources")


def build_plugin(engine_root: Path, output: Path) -> None:
    run_uat = engine_root / "Build" / "BatchFiles" / "RunUAT.bat"
    descriptor = SOURCE / f"{PLUGIN_NAME}.uplugin"
    if not run_uat.is_file():
        raise FileNotFoundError(f"Unreal AutomationTool is missing: {run_uat}")
    if not descriptor.is_file():
        raise FileNotFoundError(f"Plugin descriptor is missing: {descriptor}")

    with tempfile.TemporaryDirectory(prefix="tigerstudio_umg_") as temporary:
        package = Path(temporary) / "package"
        subprocess.run(
            [
                str(run_uat),
                "BuildPlugin",
                f"-Plugin={descriptor}",
                f"-Package={package}",
                "-TargetPlatforms=Win64",
                "-Rocket",
            ],
            check=True,
        )

        staging = output.with_name(f".{output.name}.installing")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        shutil.copy2(package / f"{PLUGIN_NAME}.uplugin", staging)
        for part in PUBLIC_PARTS:
            source_part = package / part
            if source_part.exists():
                shutil.copytree(
                    source_part,
                    staging / part,
                    ignore=shutil.ignore_patterns("*.pdb", "*.lib", "*.exp"),
                )

        output.parent.mkdir(parents=True, exist_ok=True)
        backup = output.with_name(f".{output.name}.backup")
        if backup.exists():
            shutil.rmtree(backup)
        if output.exists():
            output.replace(backup)
        try:
            staging.replace(output)
        except Exception:
            if backup.exists() and not output.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)

    if (output / "Source").exists() or (output / "Intermediate").exists():
        raise RuntimeError("Distribution bundle unexpectedly contains private build source.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", type=Path, default=DEFAULT_ENGINE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build_plugin(args.engine_root.resolve(), args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
