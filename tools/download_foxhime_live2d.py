"""Download Fox Hime Zero (狐姫Zero) Live2D models from the Eikanya/Live2d-model
collection into resources/live2d_samples/FoxHimeZero/.

Fox Hime Zero's shrine-maiden fox-girl models (mori / ruri) are clean,
all-ages, Cubism (moc3 v1) avatars with full motion + expression sets — the
same shape as a Japanese VTuber Live2D model, so they exercise the Cubism
loader the same way. File lists come from a pre-fetched git-tree manifest
(tools/_eik_tree.json); files are pulled from raw.githubusercontent.

Local sample use only.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/Eikanya/Live2d-model/master"
SRC_PREFIX = "galgame live2d/Fox Hime Zero"
MANIFEST = Path("tools/_eik_tree.json")
OUT = Path("resources/live2d_samples/FoxHimeZero")
MODELS = ["mori_miko", "mori_suit", "ruri_miko"]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main() -> int:
    tree = json.loads(MANIFEST.read_text(encoding="utf-8"))["tree"]
    for model in MODELS:
        prefix = f"{SRC_PREFIX}/{model}/"
        rels = [t["path"][len(prefix):] for t in tree
                if t.get("type") == "blob" and t["path"].startswith(prefix)]
        print(f"=== {model} ({len(rels)} files) ===")
        for rel in rels:
            src = f"{RAW}/{urllib.parse.quote(prefix + rel)}"
            dst = OUT / model / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(get(src))
        print(f"  done: {model}")
    total = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"\nDone: {total} files in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
