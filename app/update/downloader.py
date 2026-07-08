"""Download update artifacts into the per-user staging cache."""
from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from app.paths import runtime_data_dir
from app.update.manifest import UpdateArtifact


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    bytes_written: int
    source_url: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "bytes_written": int(self.bytes_written),
            "source_url": self.source_url,
        }


def update_cache_dir() -> Path:
    path = runtime_data_dir() / "updates" / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_artifact(
    artifact: UpdateArtifact,
    *,
    cache_dir: str | Path | None = None,
    timeout: float = 60.0,
) -> DownloadResult:
    target_dir = Path(cache_dir) if cache_dir is not None else update_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = artifact.filename or Path(urlparse(artifact.url).path).name or "TigerCapture-update.bin"
    target = target_dir / filename
    parsed = urlparse(artifact.url)
    if len(parsed.scheme) == 1 and parsed.path:
        source = Path(artifact.url)
        shutil.copyfile(source, target)
        return DownloadResult(path=target, bytes_written=target.stat().st_size, source_url=artifact.url)
    if parsed.scheme == "file":
        source = _path_from_file_url(parsed.path)
        shutil.copyfile(source, target)
        return DownloadResult(path=target, bytes_written=target.stat().st_size, source_url=artifact.url)
    if parsed.scheme in {"", None}:
        source = Path(artifact.url)
        shutil.copyfile(source, target)
        return DownloadResult(path=target, bytes_written=target.stat().st_size, source_url=artifact.url)
    with urlopen(artifact.url, timeout=float(timeout)) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)
    return DownloadResult(path=target, bytes_written=target.stat().st_size, source_url=artifact.url)


def _path_from_file_url(path: str) -> Path:
    text = unquote(path)
    if sys.platform == "win32" and len(text) >= 3 and text[0] == "/" and text[2] == ":":
        text = text[1:]
    return Path(text)
