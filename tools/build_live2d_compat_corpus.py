from __future__ import annotations

import argparse
import json
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath


JSON_REF_KEYS = ("Physics", "Pose", "DisplayInfo", "UserData")


def safe_name(text: str) -> str:
    text = re.sub(r"[^\w.-]+", "_", text, flags=re.UNICODE).strip("._")
    return text or "model"


def safe_rel(ref: str) -> Path:
    parts: list[str] = []
    for part in PurePosixPath(ref.replace("\\", "/")).parts:
        if part in ("", ".", "/") or part == "..":
            continue
        parts.append(part)
    return Path(*parts)


def read_model(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def iter_refs(data: dict):
    refs = data.get("FileReferences") or {}
    moc = refs.get("Moc")
    if isinstance(moc, str) and moc:
        yield moc
    for key in JSON_REF_KEYS:
        value = refs.get(key)
        if isinstance(value, str) and value:
            yield value
    for tex in refs.get("Textures") or []:
        if isinstance(tex, str) and tex:
            yield tex
    for expr in refs.get("Expressions") or []:
        if isinstance(expr, dict) and isinstance(expr.get("File"), str):
            yield expr["File"]
    for motions in (refs.get("Motions") or {}).values():
        for motion in motions or []:
            if not isinstance(motion, dict):
                continue
            for key in ("File", "Sound"):
                value = motion.get(key)
                if isinstance(value, str) and value:
                    yield value


def resolve_ref(base: Path, ref: str) -> Path | None:
    rel = safe_rel(ref)
    direct = base / rel
    if direct.is_file():
        return direct
    candidates = sorted(base.rglob(PurePosixPath(ref.replace("\\", "/")).name))
    return candidates[0] if candidates else None


def copy_standard_assets(model: Path, out_dir: Path) -> list[Path]:
    data = read_model(model)
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    dst_model = out_dir / model.name
    shutil.copy2(model, dst_model)
    copied.append(dst_model)
    for ref in sorted(set(iter_refs(data))):
        src = resolve_ref(model.parent, ref)
        if src is None:
            continue
        dst = out_dir / safe_rel(ref)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def build_bytes_tree(model: Path, out_dir: Path) -> Path:
    copied = copy_standard_assets(model, out_dir)
    for src in copied:
        if src.name.lower().endswith(".bytes"):
            continue
        dst = src.with_name(src.name + ".bytes")
        shutil.copy2(src, dst)
        if src.name.lower().endswith((
            ".model3.json",
            ".motion3.json",
            ".exp3.json",
            ".physics3.json",
            ".pose3.json",
            ".userdata3.json",
            ".cdi3.json",
            ".moc3",
        )):
            src.unlink()
    return out_dir / (model.name + ".bytes")


def write_bytes_json(dst: Path, name: str, payload: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = {"m_Name": name, "_bytes": list(payload)}
    dst.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def build_wrapped_json(model: Path, out_dir: Path, max_payload: int) -> Path | None:
    data = read_model(model)
    refs = list(sorted(set(iter_refs(data))))
    payloads: list[tuple[str, Path, bytes]] = []
    model_payload = model.read_bytes()
    if len(model_payload) > max_payload:
        return None
    for ref in refs:
        src = resolve_ref(model.parent, ref)
        if src is None:
            continue
        raw = src.read_bytes()
        if len(raw) > max_payload:
            return None
        payloads.append((ref, src, raw))

    out_dir.mkdir(parents=True, exist_ok=True)
    model_wrapper = out_dir / f"{model.stem}.json"
    write_bytes_json(model_wrapper, model.name, model_payload)
    for ref, src, raw in payloads:
        dst_rel = safe_rel(ref)
        if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".ogg", ".m4a"):
            dst = out_dir / dst_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            continue
        if src.name.lower().endswith(".moc3"):
            raw = b"\x00" * 48 + raw
        write_bytes_json(out_dir / dst_rel.with_name(dst_rel.name + ".json"), dst_rel.name, raw)
    return model_wrapper


def build_raw_header(model: Path, out_dir: Path) -> Path:
    copied = copy_standard_assets(model, out_dir)
    for dst in copied:
        if dst.name.lower().endswith(".moc3"):
            raw = dst.read_bytes()
            dst.write_bytes(b"\x00" * 48 + raw)
    return out_dir / model.name


def build_unitypackage(bytes_tree: Path, out_pkg: Path) -> Path:
    root = bytes_tree.parent
    files = [p for p in root.rglob("*") if p.is_file()]
    out_pkg.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_pkg, "w:gz") as tar:
        for idx, src in enumerate(files):
            rel = src.relative_to(root).as_posix()
            temp_dir = out_pkg.parent / f".pkg_{idx:04d}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            pathname = temp_dir / "pathname"
            asset = temp_dir / "asset"
            pathname.write_text(f"Assets/Live2DCompat/{root.name}/{rel}", encoding="utf-8")
            shutil.copy2(src, asset)
            guid = f"asset{idx:04d}"
            tar.add(pathname, arcname=f"{guid}/pathname")
            tar.add(asset, arcname=f"{guid}/asset")
            shutil.rmtree(temp_dir, ignore_errors=True)
    return out_pkg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="resources/live2d_samples")
    parser.add_argument("--output", default="_live2d_compat_corpus")
    parser.add_argument("--max-wrapper-bytes", type=int, default=3_000_000)
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    manifest: list[dict] = []
    models = sorted(source.rglob("*.model3.json"))
    for index, model in enumerate(models, start=1):
        slug = safe_name(f"{index:02d}_{model.parent.name}_{model.stem}")
        bytes_path = build_bytes_tree(model, output / "bytes_tree" / slug)
        manifest.append({"case": "bytes_tree", "source": str(model), "path": str(bytes_path)})

        raw_path = build_raw_header(model, output / "raw_header" / slug)
        manifest.append({"case": "raw_header", "source": str(model), "path": str(raw_path)})

        wrapped_path = build_wrapped_json(
            model, output / "wrapped_json" / slug, args.max_wrapper_bytes
        )
        if wrapped_path is not None:
            manifest.append({"case": "wrapped_json", "source": str(model), "path": str(wrapped_path)})

        pkg_path = build_unitypackage(bytes_path, output / "unitypackage" / f"{slug}.unitypackage")
        manifest.append({"case": "unitypackage", "source": str(model), "path": str(pkg_path)})

    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"models={len(models)}")
    print(f"cases={len(manifest)}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
