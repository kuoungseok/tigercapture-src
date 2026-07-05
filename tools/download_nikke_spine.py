"""Download NIKKE (GODDESS OF VICTORY: NIKKE) Spine character samples from the
public nikke-db mirror into resources/spine_samples/nikke/.

nikke-db (https://github.com/Nikke-db/Nikke-db.github.io, the source the
bundled NikkeViewerEX README points at) hosts deobfuscated Spine exports as
plain .skel/.atlas/.png triples under l2d/<char>/. NIKKE units are Spine
4.0/4.1 — within the project's best-effort parser range, complementing the
Spine 3.8 samples (Arknights, Blue Archive).

Each character dir is downloaded only if it yields a parser-supported skel
(3.8 / 4.0 / 4.1); unsupported or incomplete dirs are skipped and reported.
Existing dirs are left untouched (no duplicates). Local sample use only.
"""
from __future__ import annotations

import json
import re
import shutil
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/Nikke-db/Nikke-db.github.io/main/l2d"
OUT = Path("resources/spine_samples/nikke")
# Full repo tree manifest, pre-fetched once via authenticated `gh api
# .../git/trees/main?recursive=1` — avoids the 60/hr unauthenticated
# contents-API rate limit when listing every character folder.
MANIFEST = Path("tools/_nikke_tree.json")
WANT_EXT = (".skel", ".atlas", ".png")


def ensure_manifest() -> None:
    """Fetch the repo tree once via authenticated gh if the manifest is absent."""
    if MANIFEST.exists():
        return
    import subprocess
    print("Fetching repo tree manifest via gh ...")
    out = subprocess.run(
        ["gh", "api",
         "repos/Nikke-db/Nikke-db.github.io/git/trees/main?recursive=1"],
        capture_output=True, text=True, check=True,
    ).stdout
    MANIFEST.write_text(out, encoding="utf-8")


def load_char_files() -> dict[str, list[str]]:
    """Map each top-level l2d/<char>/ dir to its direct .skel/.atlas/.png files
    (ignores nested aim/cover subfolders) using the pre-fetched tree manifest."""
    ensure_manifest()
    tree = json.loads(MANIFEST.read_text(encoding="utf-8"))["tree"]
    chars: dict[str, list[str]] = {}
    for entry in tree:
        path = entry["path"]
        if entry["type"] != "blob" or not path.startswith("l2d/"):
            continue
        parts = path.split("/")
        if len(parts) != 3:            # l2d/<char>/<file> only
            continue
        char, name = parts[1], parts[2]
        if name.endswith(WANT_EXT):
            chars.setdefault(char, []).append(name)
    return chars


def discover_chars(all_files: dict[str, list[str]]) -> list[str]:
    """Named playable-character dirs (exclude cXXX NPCs, scene/bg codes,
    numeric/variant-suffixed folders)."""
    out = []
    for n in all_files:
        if re.match(r"^c\d+", n):          # cXXX common NPC
            continue
        if re.match(r"^e?b[bag]\d+", n):   # background / scene codes
            continue
        if re.search(r"_\d+$", n):         # variant suffix (e.g. foo_1)
            continue
        if n and n[0].isdigit():
            continue
        out.append(n)
    return sorted(out)


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def skel_version(raw: bytes) -> str | None:
    m = re.search(rb"\x07(\d\.\d{1,2}\.\d{1,2})", raw[:60])
    return m.group(1).decode() if m else None


def supported(ver: str | None) -> bool:
    if not ver:
        return False
    a, b = (int(x) for x in ver.split(".")[:2])
    return (a == 3 and b == 8) or (a == 4 and b in (0, 1))


def main() -> int:
    all_files = load_char_files()
    chars = discover_chars(all_files)
    print(f"Discovered {len(chars)} named character dirs.\n")
    added, skipped = [], []
    for char in chars:
        dst_dir = OUT / char
        if dst_dir.exists():
            skipped.append(f"{char} (already present)")
            continue
        files = all_files.get(char, [])
        skels = [f for f in files if f.endswith(".skel")]
        if not (skels and any(f.endswith(".atlas") for f in files)
                and any(f.endswith(".png") for f in files)):
            skipped.append(f"{char} (incomplete triple)")
            continue

        # Verify version before committing the full download.
        ver = skel_version(get(f"{RAW}/{char}/{skels[0]}"))
        if not supported(ver):
            skipped.append(f"{char} (unsupported Spine v{ver})")
            continue

        dst_dir.mkdir(parents=True, exist_ok=True)
        try:
            for name in files:
                (dst_dir / name).write_bytes(get(f"{RAW}/{char}/{name}"))
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(dst_dir, ignore_errors=True)
            skipped.append(f"{char} (download error: {exc})")
            continue
        added.append(f"{char} (v{ver}, {len(files)} files)")
        print(f"  + {char:18s} v{ver}  ({len(files)} files)")

    present = [s for s in skipped if "already present" in s]
    other = [s for s in skipped if "already present" not in s]
    print(f"\nAdded {len(added)} characters.")
    print(f"Already present (skipped): {len(present)}")
    if other:
        print(f"Other skips ({len(other)}):")
        for s in other:
            print("   ", s)
    print(f"\nnikke/ now has {sum(1 for _ in OUT.rglob('*.skel'))} .skel models "
          f"across {len([p for p in OUT.iterdir() if p.is_dir()])} dirs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
