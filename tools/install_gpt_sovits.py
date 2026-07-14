"""Download the optional GPT-SoVITS sidecar under external/tools."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "external" / "tools" / "tts" / "gpt-sovits"
REPOSITORY = "https://github.com/RVC-Boss/GPT-SoVITS.git"


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.check_call(command, cwd=str(cwd) if cwd else None)


def _write_manifest(target: Path, payload: dict[str, object]) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / "install_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _write_preset_template(target: Path) -> Path:
    preset_dir = target / "voice_presets"
    preset_dir.mkdir(parents=True, exist_ok=True)
    template = preset_dir / "example_voice.json"
    if not template.exists():
        template.write_text(
            json.dumps(
                {
                    "id": "example_voice",
                    "label": "Example Reference Voice",
                    "ref_audio_path": "D:/path/to/reference.wav",
                    "prompt_text": "Reference audio transcript goes here.",
                    "prompt_lang": "ja",
                    "text_lang": "ja",
                    "text_split_method": "cut5",
                    "speed_factor": 1.0,
                    "notes": "Replace this with a real local reference voice before synthesis.",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return template


def main() -> int:
    parser = argparse.ArgumentParser(description="Download GPT-SoVITS into external/tools/tts/gpt-sovits")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Sidecar target folder")
    parser.add_argument("--repository", default=REPOSITORY, help="Git repository URL")
    parser.add_argument("--branch", default="", help="Optional branch/tag")
    parser.add_argument("--depth", default="1", help="Clone depth; use 0 for full clone")
    parser.add_argument("--update", action="store_true", help="Pull latest if the target repo already exists")
    parser.add_argument("--install-deps", action="store_true", help="Run upstream install.ps1 after clone")
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

    template = _write_preset_template(target)
    deps_ran = False
    if args.install_deps:
        install_ps1 = target / "install.ps1"
        if not install_ps1.exists():
            raise SystemExit(f"Missing upstream install.ps1: {install_ps1}")
        _run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(install_ps1)], cwd=target)
        deps_ran = True

    manifest = _write_manifest(
        target,
        {
            "schema": "tigercapture.gpt_sovits_install_manifest.v1",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "repository": str(args.repository),
            "branch": str(args.branch or ""),
            "target": str(target),
            "api_path": str(target / "api_v2.py"),
            "config_path": str(target / "GPT_SoVITS" / "configs" / "tts_infer.yaml"),
            "voice_preset_template": str(template),
            "dependencies_installed": deps_ran,
        },
    )
    print(f"GPT-SoVITS sidecar manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
