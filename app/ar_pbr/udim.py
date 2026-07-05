"""UDIM texture-tile helpers for AR/PBR material maps."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


UDIM_TOKEN = "<UDIM>"
UDIM_JSON_SUFFIX = "_udim_tiles"
UDIM_TILE_MIN = 1001
UDIM_TILE_MAX = 1999

_UDIM_TOKEN_RE = re.compile(re.escape(UDIM_TOKEN), re.IGNORECASE)
_UDIM_NUMBER_RE = re.compile(r"(?<!\d)(1\d{3})(?!\d)")


def udim_tile_id_from_uv(u: Any, v: Any) -> Any:
    """Return the UDIM tile number for scalar or numpy-array UV values."""
    import numpy as np

    uu = np.floor(np.asarray(u, dtype=np.float32)).astype(np.int32)
    vv = np.floor(np.asarray(v, dtype=np.float32)).astype(np.int32)
    return 1001 + uu + vv * 10


def local_uv_from_udim(u: Any, v: Any) -> tuple[Any, Any]:
    import numpy as np

    return np.mod(np.asarray(u, dtype=np.float32), 1.0), np.mod(np.asarray(v, dtype=np.float32), 1.0)


def is_valid_udim_tile(tile: Any) -> bool:
    try:
        tile_id = int(tile)
    except Exception:
        return False
    if tile_id < UDIM_TILE_MIN or tile_id > UDIM_TILE_MAX:
        return False
    # UDIM columns are 0-9 inside each row.
    return 0 <= (tile_id - 1001) % 10 <= 9


def _candidate_regex_for_name(name: str) -> re.Pattern[str] | None:
    text = str(name or "")
    if not text:
        return None
    if _UDIM_TOKEN_RE.search(text):
        parts: list[str] = []
        pos = 0
        for match in _UDIM_TOKEN_RE.finditer(text):
            parts.append(re.escape(text[pos:match.start()]))
            parts.append(r"(?P<tile>\d{4})")
            pos = match.end()
            break
        parts.append(re.escape(text[pos:]))
        pattern = "".join(parts)
        return re.compile(f"^{pattern}$", re.IGNORECASE)
    match = None
    for candidate in _UDIM_NUMBER_RE.finditer(text):
        if is_valid_udim_tile(candidate.group(1)):
            match = candidate
            if candidate.group(1) == "1001":
                break
    if match is None:
        return None
    start, end = match.span(1)
    pattern = re.escape(text[:start]) + r"(?P<tile>\d{4})" + re.escape(text[end:])
    return re.compile(f"^{pattern}$", re.IGNORECASE)


def _path_candidates(value: str | Path) -> list[Path]:
    path = Path(str(value or ""))
    if path.is_absolute():
        return [path]
    return [path, Path.cwd() / path]


def discover_udim_tiles(value: str | Path) -> dict[int, str]:
    """Discover sibling files belonging to a UDIM tile set."""
    text = str(value or "").strip()
    if not text:
        return {}
    for candidate in _path_candidates(text):
        directory = candidate.parent
        regex = _candidate_regex_for_name(candidate.name)
        if regex is None:
            continue
        try:
            if not directory.is_dir():
                continue
        except Exception:
            continue
        tiles: dict[int, str] = {}
        try:
            for path in directory.iterdir():
                if not path.is_file():
                    continue
                match = regex.match(path.name)
                if match is None:
                    continue
                tile = int(match.group("tile"))
                if not is_valid_udim_tile(tile):
                    continue
                tiles[tile] = str(path.resolve())
        except Exception:
            continue
        if tiles:
            return dict(sorted(tiles.items()))
    return {}


def primary_udim_path(value: str | Path) -> str:
    tiles = discover_udim_tiles(value)
    if not tiles:
        return ""
    tile_id = 1001 if 1001 in tiles else sorted(tiles)[0]
    return str(tiles[tile_id])


def encode_udim_tiles(tiles: Mapping[int | str, str]) -> str:
    clean: dict[str, str] = {}
    for raw_tile, raw_path in tiles.items():
        try:
            tile = int(raw_tile)
        except Exception:
            continue
        if is_valid_udim_tile(tile) and str(raw_path or ""):
            clean[str(tile)] = str(raw_path)
    return json.dumps(dict(sorted(clean.items())), sort_keys=True)


def decode_udim_tiles(value: Any) -> dict[int, str]:
    if isinstance(value, Mapping):
        source = value
    else:
        try:
            source = json.loads(str(value or ""))
        except Exception:
            return {}
    out: dict[int, str] = {}
    if not isinstance(source, Mapping):
        return out
    for raw_tile, raw_path in source.items():
        try:
            tile = int(raw_tile)
        except Exception:
            continue
        if is_valid_udim_tile(tile) and str(raw_path or ""):
            out[tile] = str(raw_path)
    return dict(sorted(out.items()))


def udim_metadata_for_path(value: str | Path) -> dict[str, Any]:
    tiles = discover_udim_tiles(value)
    if not tiles:
        return {
            "enabled": False,
            "tile_count": 0,
            "primary_tile": 0,
            "tiles": {},
            "tiles_json": "",
            "sampling_model": "single_texture",
        }
    primary_tile = 1001 if 1001 in tiles else sorted(tiles)[0]
    return {
        "enabled": True,
        "tile_count": len(tiles),
        "primary_tile": primary_tile,
        "tiles": dict(tiles),
        "tiles_json": encode_udim_tiles(tiles),
        "sampling_model": "uv_integer_tile_lookup",
        "preview_policy": "primary_tile_live_gl_preview_packet_export_full_tile_lookup",
    }
