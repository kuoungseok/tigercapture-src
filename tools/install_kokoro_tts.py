"""Install the optional Kokoro TTS runtime under external/tools.

This script intentionally installs into a target directory instead of the app
venv so the editor can keep Kokoro as an optional local provider.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "external" / "tools" / "tts" / "kokoro"


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.check_call(command, env=env)


def _write_manifest(target: Path, payload: dict[str, object]) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / "install_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _warmup(target: Path, voice: str, text: str) -> Path:
    package_dir = target / "python"
    venv_python = target / ".venv" / "Scripts" / "python.exe"
    cache_dir = target / "hf_cache"
    output = target / "warmup" / "kokoro_warmup.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    helper = ROOT / "tools" / "kokoro_synthesize.py"
    python = venv_python if venv_python.exists() else sys.executable
    command = [
        str(python),
        str(helper),
        "--root",
        str(target),
        "--output",
        str(output),
        "--voice",
        str(voice or "af_heart"),
        "--language",
        "j" if str(voice or "").startswith(("jf_", "jm_")) else "a",
        "--text",
        str(text or "Tiger Studio local voice test."),
    ]
    env = dict(os.environ)
    env["HF_HOME"] = str(cache_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    if package_dir.exists():
        env["PYTHONPATH"] = str(package_dir)
    _run(command, env=env)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Kokoro TTS into external/tools/tts/kokoro")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Runtime target folder")
    parser.add_argument("--warmup", action="store_true", help="Run one short synthesis to download/cache model files")
    parser.add_argument("--voice", default="af_heart", help="Warm-up voice")
    parser.add_argument("--text", default="Tiger Studio local voice test.", help="Warm-up text")
    parser.add_argument("--no-japanese", action="store_true", help="Skip Japanese G2P extras")
    parser.add_argument("--target-packages", action="store_true", help="Install into target/python instead of an external venv")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    package_dir = target / "python"
    venv_dir = target / ".venv"
    venv_python = venv_dir / "Scripts" / "python.exe"
    cache_dir = target / "pip_cache"
    hf_cache = target / "hf_cache"
    target.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    hf_cache.mkdir(parents=True, exist_ok=True)

    packages = [
        "kokoro>=0.9.4",
        "soundfile",
        "misaki[en]",
        "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
    ]
    if not args.no_japanese:
        packages.append("misaki[ja]")

    env = dict(os.environ)
    env["PIP_CACHE_DIR"] = str(cache_dir)
    install_mode = "venv"
    uv = shutil.which("uv")
    if args.target_packages:
        package_dir.mkdir(parents=True, exist_ok=True)
        pip_python = sys.executable
        pip_args = ["--target", str(package_dir)]
        install_mode = "target"
        pip_command = [str(pip_python), "-m", "pip", "install", "--upgrade", *pip_args, *packages]
    else:
        if uv and not venv_python.exists():
            _run([uv, "venv", str(venv_dir), "--python", "3.12"], env=env)
        if not venv_python.exists():
            _run([sys.executable, "-m", "venv", str(venv_dir)], env=env)
        if uv:
            pip_command = [uv, "pip", "install", "--python", str(venv_python), "--upgrade", *packages]
        else:
            _run([str(venv_python), "-m", "ensurepip", "--upgrade"], env=env)
            pip_command = [str(venv_python), "-m", "pip", "install", "--upgrade", *packages]
    _run(pip_command, env=env)

    warmup_output = ""
    if args.warmup:
        warmup_output = str(_warmup(target, str(args.voice or "af_heart"), str(args.text or "Tiger Studio local voice test.")))

    manifest = _write_manifest(
        target,
        {
            "schema": "tigercapture.kokoro_install_manifest.v1",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "target": str(target),
            "package_dir": str(package_dir),
            "venv_dir": str(venv_dir),
            "venv_python": str(venv_python),
            "hf_cache": str(hf_cache),
            "install_mode": install_mode,
            "packages": packages,
            "warmup_output": warmup_output,
        },
    )
    print(f"Installed Kokoro runtime manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
