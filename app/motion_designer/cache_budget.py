"""Size accounting and directory-level LRU pruning for generated Motion caches."""
from __future__ import annotations

from pathlib import Path
import shutil
from typing import Iterable


DEFAULT_DECOMPOSITION_CACHE_BYTES = 2 * 1024 * 1024 * 1024


def _directory_size(path: Path) -> int:
    total = 0
    for candidate in path.rglob("*"):
        try:
            if candidate.is_file():
                total += candidate.stat().st_size
        except OSError:
            continue
    return total


def enforce_directory_cache_budget(
    root: str | Path,
    *,
    max_bytes: int,
    protected_paths: Iterable[str | Path] = (),
) -> dict[str, object]:
    cache_root = Path(root).expanduser().resolve()
    maximum = max(1, int(max_bytes))
    protected = {Path(path).expanduser().resolve() for path in protected_paths}
    rows: list[tuple[Path, int, float]] = []
    if cache_root.is_dir():
        for child in cache_root.iterdir():
            if not child.is_dir():
                continue
            try:
                rows.append((child.resolve(), _directory_size(child), child.stat().st_mtime))
            except OSError:
                continue
    before_bytes = sum(row[1] for row in rows)
    current_bytes = before_bytes
    removed_paths: list[str] = []
    removed_bytes = 0
    for path, size, _ in sorted(rows, key=lambda row: row[2]):
        if current_bytes <= maximum:
            break
        if path in protected:
            continue
        try:
            shutil.rmtree(path)
        except OSError:
            continue
        current_bytes -= size
        removed_bytes += size
        removed_paths.append(str(path))
    return {
        "ok": current_bytes <= maximum,
        "root": str(cache_root),
        "max_bytes": maximum,
        "before_bytes": before_bytes,
        "current_bytes": max(0, current_bytes),
        "removed_bytes": removed_bytes,
        "removed_paths": removed_paths,
        "entry_count": len(rows) - len(removed_paths),
        "protected_paths": [str(path) for path in sorted(protected)],
    }


__all__ = [
    "DEFAULT_DECOMPOSITION_CACHE_BYTES",
    "enforce_directory_cache_budget",
]
