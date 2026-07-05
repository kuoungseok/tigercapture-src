"""Download a real Project SEKAI Live2D model from the public Sekai Viewer
mirror (storage.sekai.best) and assemble it into a standard Cubism folder.

The mirror stores already-deobfuscated Cubism payloads. The web viewer
reconstructs a clean ``model3.json`` at runtime (motions live under a shared
``*_motion_base`` tree, textures/moc/physics under the model folder). This
script reproduces that assembly so the result is a self-contained, directly
loadable Cubism model — the same output as Sekai Viewer's "download" button.

Parser work for the raw Unity ``.bytes`` layout is handled elsewhere; this just
fetches genuine game assets into resources/live2d_samples/.
"""
from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

CDN = "https://storage.sekai.best/sekai-live2d-assets/live2d"

# Chosen model: Hatsune Miku, normal costume (variant t03).
MODEL_DIR = "model/v1/main/21_miku/21miku_normal"
MOC = "21miku_normal_3.0_f_t03.moc3"
PHYSICS = "21miku_normal_3.0_f_t03.physics3.json"
TEXTURES = ["21miku_normal_3.0_f_t03.2048/texture_00.png"]
MOTION_BASE = "motion/v1/main/21_miku/21miku_motion_base"

MODEL_NAME = "21miku_normal"
OUT = Path("resources/live2d_samples/ProjectSekai_21miku_normal")

# Keep the fixture light: a representative subset of motions + expressions
# instead of the full 227 + 144 catalogue.
MOTIONS = [
    "w-animalnormal-nodtilthead0101", "w-adult-blushed01", "w-cute-angry01",
    "w-cool-angry01", "w-cutehappy-shakeheadsad0201", "w-cool-posesad01",
    "w-adult-glad01",
]
EXPRESSIONS = [
    "face_smile_01", "face_angry_01", "face_sad_01", "face_surprise_01",
    "face_closeeye_01", "face_blushed_01",
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def save(rel: str, data: bytes) -> None:
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f"  {rel:48s} {len(data):>10,} bytes")


def try_fetch(url: str) -> bytes | None:
    try:
        return fetch(url)
    except Exception as exc:  # noqa: BLE001 - best-effort optional files
        print(f"  skip {url.rsplit('/', 1)[-1]}: {exc}")
        return None


def main() -> int:
    if OUT.exists():
        import shutil
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    print("Required files:")
    save(f"{MODEL_NAME}.moc3", fetch(f"{CDN}/{MODEL_DIR}/{MOC}"))
    save(f"{MODEL_NAME}.physics3.json", fetch(f"{CDN}/{MODEL_DIR}/{PHYSICS}"))
    packed_textures = []
    for idx, tex in enumerate(TEXTURES):
        rel = f"{MODEL_NAME}.2048/texture_{idx:02d}.png"
        save(rel, fetch(f"{CDN}/{MODEL_DIR}/{tex}"))
        packed_textures.append(rel)

    print("Motions:")
    motions_ref: dict[str, list[dict]] = {}
    for name in MOTIONS:
        data = try_fetch(f"{CDN}/{MOTION_BASE}/motion/{name}.motion3.json")
        if data is None:
            continue
        rel = f"motions/{name}.motion3.json"
        save(rel, data)
        motions_ref[name] = [{"File": rel, "FadeInTime": 0.5, "FadeOutTime": 0.5}]

    print("Expressions (loaded as motions, per Sekai Viewer):")
    for name in EXPRESSIONS:
        data = try_fetch(f"{CDN}/{MOTION_BASE}/facial/{name}.motion3.json")
        if data is None:
            continue
        rel = f"motions/{name}.motion3.json"
        save(rel, data)
        motions_ref[name] = [{"File": rel, "FadeInTime": 0.5, "FadeOutTime": 0.5}]

    model3 = {
        "Version": 3,
        "FileReferences": {
            "Moc": f"{MODEL_NAME}.moc3",
            "Textures": packed_textures,
            "Physics": f"{MODEL_NAME}.physics3.json",
            "Motions": motions_ref,
        },
        "Groups": [
            {"Target": "Parameter", "Name": "EyeBlink",
             "Ids": ["ParamEyeROpen", "ParamEyeLOpen"]},
            {"Target": "Parameter", "Name": "LipSync",
             "Ids": ["ParamMouthOpenY"]},
        ],
    }
    model3_path = OUT / f"{MODEL_NAME}.model3.json"
    model3_path.write_text(json.dumps(model3, indent=2), encoding="utf-8")
    print(f"\nWrote {model3_path}")
    print(f"Done: {sum(1 for _ in OUT.rglob('*') if _.is_file())} files in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
