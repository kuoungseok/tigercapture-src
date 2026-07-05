"""Download KonoSuba: Fantastic Days Live2D models from the Eikanya/Live2d-model
collection into resources/live2d_samples/KonoSuba/.

Unlike BanG Dream! in the same collection (which is legacy Cubism 2 *.moc and
not loadable by the project's Cubism 3/4 runtime), KonoSuba FD ships modern
moc3 + model3.json models with motions + textures — recognisable anime
characters (Aqua, etc.) that load directly, same as a VTuber Live2D model.

File lists are gathered via authenticated `gh api` (per-folder, recursing into
motions/ and textures/); files are pulled from raw.githubusercontent.

Local sample use only.
"""
from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "Eikanya/Live2d-model"
RAW = f"https://raw.githubusercontent.com/{REPO}/master"
SRC = "为美好的世界献上祝福！Fantastic Days"
OUT = Path("resources/live2d_samples/KonoSuba")

# Repo folder code -> friendly local name. Main playable roster, base costume
# (the "10X4...100" series, +10 per character). Character identities for the
# first six were confirmed by inspecting the texture atlas; the rest are kept
# under their asset code (identify on demand by viewing textures/texture_00.png).
MODELS = {
    "1004100": "kazuma",
    "1014100aqua": "aqua",
    "1024100": "megumin",
    "1034100": "darkness",
    "1044100": "chris",
    "1054100": "wiz",
    "1064100": "char_1064100",
    "1074100": "char_1074100",
    "1084100": "char_1084100",
    "1094100": "char_1094100",
    "1104100": "char_1104100",
    "1114100": "char_1114100",
    "1124100": "char_1124100",
    "1134100": "char_1134100",
    "1144100": "char_1144100",
    "1154100": "char_1154100",
    "1164100": "char_1164100",
    "1174100": "char_1174100",
    "1184100": "char_1184100",
    "1194100": "char_1194100",
}
SUBDIRS = ["", "motions", "textures"]


def gh_list(path: str) -> list[dict]:
    raw = subprocess.run(
        ["gh", "api", f"repos/{REPO}/contents/{urllib.parse.quote(path)}"],
        capture_output=True,
    ).stdout
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main() -> int:
    for code, friendly in MODELS.items():
        print(f"=== {friendly} ({code}) ===")
        n = 0
        for sub in SUBDIRS:
            src_dir = f"{SRC}/{code}" + (f"/{sub}" if sub else "")
            for entry in gh_list(src_dir):
                if entry.get("type") != "file":
                    continue
                rel = (f"{sub}/" if sub else "") + entry["name"]
                url = f"{RAW}/{urllib.parse.quote(f'{SRC}/{code}/{rel}')}"
                dst = OUT / friendly / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(fetch(url))
                n += 1
        print(f"  {n} files")
    total = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"\nDone: {total} files in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
