"""QA gate for PyInstaller resource packaging contracts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "debugCapture" / "packaging_resources_qa.json"


REQUIRED_SPEC_TOKENS = {
    "TigerCapture.spec": [
        "app/locales/*.py",
        "resources/tigercapture.ico",
        "resources/luts/*.cube",
        "resources/ui/sound_editor/*.png",
        "bundled/unreal_plugins/UMG/TigerStudioUMG",
        "copy_metadata('imageio_ffmpeg')",
    ],
    "mac/TigerCapture-mac.spec": [
        "app' / 'locales' / '*.py",
        "resources' / 'tigercapture.ico",
        "resources' / 'luts' / '*.cube",
        "resources' / 'ui' / 'sound_editor' / '*.png",
        "copy_metadata('imageio_ffmpeg')",
    ],
}


REQUIRED_FILES = [
    "resources/tigercapture.ico",
    "resources/luts/teal_orange.cube",
    "resources/luts/muted_film.cube",
    "resources/luts/film_warm.cube",
    "resources/luts/cool_blue.cube",
    "resources/ui/sound_editor/jog_dial_metal_sparse_base.png",
    "resources/unreal_plugins/UMG/TigerStudioUMG/TigerStudioUMG.uplugin",
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_report() -> dict[str, Any]:
    spec_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for rel, tokens in REQUIRED_SPEC_TOKENS.items():
        path = ROOT / rel
        text = _read(path)
        missing = [token for token in tokens if token not in text]
        if not path.is_file():
            blockers.append(f"missing_spec:{rel}")
        for token in missing:
            blockers.append(f"missing_token:{rel}:{token}")
        spec_rows.append(
            {
                "path": rel,
                "exists": path.is_file(),
                "required_token_count": len(tokens),
                "missing_tokens": missing,
            }
        )

    file_rows: list[dict[str, Any]] = []
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        exists = path.is_file()
        if not exists:
            blockers.append(f"missing_file:{rel}")
        file_rows.append({"path": rel, "exists": exists, "size": path.stat().st_size if exists else 0})

    return {
        "schema": "tigerstudio.qa.packaging_resources.v1",
        "ok": not blockers,
        "blockers": blockers,
        "summary": {
            "spec_count": len(spec_rows),
            "required_file_count": len(file_rows),
            "missing_count": len(blockers),
        },
        "specs": spec_rows,
        "files": file_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    report = build_report()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "summary": report["summary"], "out": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
