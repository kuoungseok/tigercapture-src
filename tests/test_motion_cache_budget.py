from __future__ import annotations

import os
from pathlib import Path

from app.motion_designer.cache_budget import enforce_directory_cache_budget


def _entry(root: Path, name: str, size: int, timestamp: float) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "payload.bin").write_bytes(b"x" * size)
    os.utime(directory, (timestamp, timestamp))
    return directory


def test_directory_cache_budget_removes_oldest_and_protects_active_entry(tmp_path) -> None:
    oldest = _entry(tmp_path, "oldest", 100, 10)
    protected = _entry(tmp_path, "protected", 100, 20)
    newest = _entry(tmp_path, "newest", 100, 30)

    report = enforce_directory_cache_budget(
        tmp_path,
        max_bytes=200,
        protected_paths=(protected,),
    )

    assert report["ok"] is True
    assert not oldest.exists()
    assert protected.exists()
    assert newest.exists()
    assert report["current_bytes"] == 200
    assert report["removed_bytes"] == 100
