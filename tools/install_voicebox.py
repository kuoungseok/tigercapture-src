"""Download the optional Voicebox (jamiepine/voicebox) sidecar under external/tools."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "external" / "tools" / "tts" / "voicebox"
REPOSITORY = "https://github.com/jamiepine/voicebox.git"


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.check_call(command, cwd=str(cwd) if cwd else None)


def _write_manifest(target: Path, payload: dict[str, object]) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / "install_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Voicebox into external/tools/tts/voicebox")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Sidecar target folder")
    parser.add_argument("--repository", default=REPOSITORY, help="Git repository URL")
    parser.add_argument("--branch", default="", help="Optional branch/tag")
    parser.add_argument("--depth", default="1", help="Clone depth; use 0 for full clone")
    parser.add_argument("--update", action="store_true", help="Pull latest if the target repo already exists")
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Create a .venv under the target and pip install backend/requirements.txt",
    )
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    clone_args = ["git", "clone"]
    if str(args.depth or "").strip() not in {"", "0"}:
        clone_args += ["--depth", str(args.depth)]
    if args.branch:
        clone_args += ["--branch", str(args.branch)]
    clone_args += [str(args.repository), str(target)]

    if (target / ".git").exists():
        if args.update:
            _run(["git", "pull", "--ff-only"], cwd=target)
    elif target.exists() and any(target.iterdir()):
        raise SystemExit(f"Target exists and is not an empty git checkout: {target}")
    else:
        _run(clone_args)

    deps_ran = False
    if args.install_deps:
        requirements = target / "requirements.txt"
        if not requirements.exists():
            raise SystemExit(f"Missing backend requirements.txt: {requirements}")
        venv_python = target / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            _run([sys.executable, "-m", "venv", str(target / ".venv")], cwd=target)
        _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=target)
        _run([str(venv_python), "-m", "pip", "install", "-r", str(requirements)], cwd=target)
        deps_ran = True

    manifest = _write_manifest(
        target,
        {
            "schema": "tigercapture.voicebox_install_manifest.v1",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "repository": str(args.repository),
            "branch": str(args.branch or ""),
            "target": str(target),
            "entry_path": str(target / "backend" / "main.py"),
            "requirements_path": str(target / "requirements.txt"),
            "dependencies_installed": deps_ran,
        },
    )
    print(f"Voicebox sidecar manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
