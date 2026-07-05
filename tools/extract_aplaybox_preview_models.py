"""Extract Aplaybox public preview packets into loadable MMD JSON folders."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import argparse
import gzip
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "local_resources" / "mmd" / "aplaybox_preview"
DEFAULT_OUT = ROOT / "local_resources" / "mmd" / "model_pool" / "playable" / "aplaybox"
DEFAULT_WASM = DEFAULT_SOURCE / "dcf.wasm"
WASM_URL = "https://details.aplaybox.com/static/wasm/dcf.wasm"


def _quote_url_path(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path), parts.query, parts.fragment))


def _download(url: str, path: Path, *, referer: str = "") -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    request = Request(_quote_url_path(url), headers=headers)
    with urlopen(request, timeout=90) as response:
        data = response.read()
    path.write_bytes(data)
    return len(data)


class _DCFDecoder:
    def __init__(self, wasm_path: Path) -> None:
        try:
            import wasmtime
        except Exception as exc:
            raise RuntimeError("wasmtime is required: python -m pip install wasmtime") from exc

        self._wasmtime = wasmtime
        engine = wasmtime.Engine()
        self._store = wasmtime.Store(engine)
        module = wasmtime.Module.from_file(engine, str(wasm_path))
        self._memory = wasmtime.Memory(self._store, wasmtime.MemoryType(wasmtime.Limits(256, 32768)))
        table_type = next(imp.type for imp in module.imports if isinstance(imp.type, wasmtime.TableType))
        table = wasmtime.Table(self._store, table_type, None)
        memcpy = wasmtime.Func(
            self._store,
            wasmtime.FuncType(
                [wasmtime.ValType.i32(), wasmtime.ValType.i32(), wasmtime.ValType.i32()],
                [wasmtime.ValType.i32()],
            ),
            lambda dest, src, count: dest,
        )
        resize = wasmtime.Func(
            self._store,
            wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()]),
            lambda size: 0,
        )
        instance = wasmtime.Instance(self._store, module, [memcpy, resize, self._memory, table])
        exports = instance.exports(self._store)
        self._malloc = exports["malloc"]
        self._free = exports["free"]
        self._func_a = exports["func_a"]

    def decode_key(self, file_name: str) -> tuple[int, int, int]:
        raw = file_name.encode("utf-8") + b"\0"
        ptr = self._malloc(self._store, len(raw))
        try:
            self._memory.write(self._store, raw, ptr)
            result = int(self._func_a(self._store, ptr))
        finally:
            self._free(self._store, ptr)
        return result & 0xFFFF, result >> 16, result


def _decode_packet(decoder: _DCFDecoder, packet_path: Path, source_url: str) -> dict:
    file_name = Path(urlsplit(source_url).path).name
    start, remove_count, key = decoder.decode_key(file_name)
    data = packet_path.read_bytes()
    if start < 0 or remove_count < 0 or start + remove_count > len(data):
        raise ValueError(f"Invalid Aplaybox DCF key for {packet_path}: {key}")
    payload = bytearray(data[:start] + data[start + remove_count :])
    if len(payload) < 2:
        raise ValueError(f"Aplaybox packet is too small: {packet_path}")
    payload[0] = 0x1F
    payload[1] = 0x8B
    return json.loads(gzip.decompress(payload).decode("utf-8"))


def _texture_url(model_url: str, texture: str) -> str:
    base = model_url.rsplit("/", 1)[0] + "/"
    return urljoin(base, texture.replace("\\", "/"))


def _download_textures(model: dict, model_url: str, out_dir: Path, *, referer: str) -> list[dict]:
    downloads: list[dict] = []
    seen: set[str] = set()
    for raw_name in model.get("textures") or []:
        texture = str(raw_name or "").replace("\\", "/").strip().strip("\0")
        if not texture or texture in seen:
            continue
        seen.add(texture)
        texture_path = out_dir / texture
        info = {"texture": texture, "path": str(texture_path.relative_to(ROOT)), "ok": False, "bytes": 0}
        try:
            info["bytes"] = _download(_texture_url(model_url, texture), texture_path, referer=referer)
            info["ok"] = True
        except Exception as exc:
            info["error"] = str(exc)
        downloads.append(info)
    return downloads


def _extract_candidate(candidate: dict, source_root: Path, out_root: Path, decoder: _DCFDecoder) -> list[dict]:
    extracted: list[dict] = []
    slug = str(candidate.get("slug") or "model")
    for item in candidate.get("preview_models") or []:
        packet_path = ROOT / str(item.get("path") or "")
        if not packet_path.is_file():
            packet_path = source_root / slug / f"{item.get('id')}.cf.pbx.gz"
        source_url = str(item.get("url") or "")
        model = _decode_packet(decoder, packet_path, source_url)
        model_id = int(item.get("id") or 0)
        out_dir = out_root / f"{slug}_{model_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "model.pbx.json"
        model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
        referer = f"https://details.aplaybox.com/modelDetails?work_uuid={candidate.get('uuid') or ''}"
        textures = _download_textures(model, source_url, out_dir, referer=referer)
        source = {
            "slug": slug,
            "label": candidate.get("label") or slug,
            "work_uuid": candidate.get("uuid") or "",
            "preview_model_id": model_id,
            "preview_name": item.get("name") or "",
            "source_url": source_url,
            "packet_path": str(packet_path.relative_to(ROOT)),
            "model_path": str(model_path.relative_to(ROOT)),
            "texture_downloads": textures,
            "metadata": model.get("metadata") or {},
        }
        (out_dir / "source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "README.md").write_text(
            "\n".join(
                [
                    f"# Aplaybox Preview {slug} {model_id}",
                    "",
                    "Decoded from the public Aplaybox preview packet.",
                    f"Model file: `{model_path.name}`",
                    f"Source URL: {source_url}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        extracted.append(source)
    return extracted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract Aplaybox preview packets into loadable .pbx.json models")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--wasm", default=str(DEFAULT_WASM))
    args = parser.parse_args(argv)

    source_root = Path(args.source)
    out_root = Path(args.out)
    wasm_path = Path(args.wasm)
    if not wasm_path.is_file():
        _download(WASM_URL, wasm_path)
    manifest_path = source_root / "manifest.json"
    candidates = json.loads(manifest_path.read_text(encoding="utf-8"))
    decoder = _DCFDecoder(wasm_path)
    all_sources: list[dict] = []
    for candidate in candidates:
        all_sources.extend(_extract_candidate(candidate, source_root, out_root, decoder))
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "manifest.json").write_text(json.dumps(all_sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"extracted {len(all_sources)} Aplaybox preview models to {out_root}")
    for item in all_sources:
        meta = item.get("metadata") or {}
        ok_textures = sum(1 for tex in item.get("texture_downloads") or [] if tex.get("ok"))
        print(
            f"{item['slug']}:{item['preview_model_id']} "
            f"verts={meta.get('vertexCount')} faces={meta.get('faceCount')} textures={ok_textures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
