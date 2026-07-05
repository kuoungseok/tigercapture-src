"""YouTube URL import helpers.

This module is intentionally optional.  Tiger Studio can run without yt-dlp;
when yt-dlp is installed, a YouTube URL can be downloaded as an MP4 and then
registered in the Media Pool.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Any
from urllib.parse import urlparse


ProgressCallback = Callable[[int, str], None]

_AUTO_FORMAT_SELECTOR = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bestvideo+bestaudio/best"
_QUALITY_PRESETS: tuple[tuple[str, str, int | None], ...] = (
    ("auto", "Auto - best available", None),
    ("4320p", "8K / 4320p max", 4320),
    ("2160p", "4K / 2160p max", 2160),
    ("1440p", "1440p max", 1440),
    ("1080p", "1080p max", 1080),
    ("720p", "720p max", 720),
    ("480p", "480p max", 480),
    ("360p", "360p max", 360),
)


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    host = parsed.netloc.lower()
    return parsed.scheme in {"http", "https"} and (
        host == "youtu.be"
        or host.endswith(".youtu.be")
        or host == "youtube.com"
        or host.endswith(".youtube.com")
    )


def youtube_quality_choices() -> list[tuple[str, str]]:
    """Return UI-ready quality choices as ``(preset_id, label)`` rows."""
    return [(preset_id, label) for preset_id, label, _height in _QUALITY_PRESETS]


def youtube_quality_label(quality: str | int | None) -> str:
    height = _quality_height(quality)
    if height is None:
        return "Auto - best available"
    if height >= 4320:
        return "8K / 4320p max"
    if height >= 2160:
        return "4K / 2160p max"
    return f"{height}p max"


def _quality_height(quality: str | int | None) -> int | None:
    if quality is None:
        return None
    if isinstance(quality, int):
        return quality if quality > 0 else None
    value = str(quality or "").strip().lower()
    if value in {"", "auto", "best", "source", "original", "max"}:
        return None
    for preset_id, _label, height in _QUALITY_PRESETS:
        if value == preset_id:
            return height
    match = re.search(r"(\d{3,4})", value)
    if match:
        height = int(match.group(1))
        return height if height > 0 else None
    return None


def youtube_format_selector(quality: str | int | None = None) -> str:
    """Build a yt-dlp format selector for the requested maximum height."""
    height = _quality_height(quality)
    if height is None:
        return _AUTO_FORMAT_SELECTOR
    cap = f"[height<={height}]"
    return (
        f"bv*{cap}[ext=mp4]+ba[ext=m4a]/"
        f"b{cap}[ext=mp4]/"
        f"bv*{cap}+ba/"
        f"b{cap}/"
        f"best{cap}/"
        "best"
    )


def youtube_import_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return yt_dlp_cli_command() is not None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def yt_dlp_cli_command() -> list[str] | None:
    """Return a usable yt-dlp command even when the running app Python lacks it."""
    candidates: list[list[str]] = []
    exe = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if exe:
        candidates.append([exe])
    root = _repo_root()
    if sys.platform.startswith("win"):
        venv_exe = root / ".venv" / "Scripts" / "yt-dlp.exe"
        venv_py = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_exe = root / ".venv" / "bin" / "yt-dlp"
        venv_py = root / ".venv" / "bin" / "python"
    if venv_exe.exists():
        candidates.append([str(venv_exe)])
    if venv_py.exists():
        candidates.append([str(venv_py), "-m", "yt_dlp"])
    # Last resort: the current executable might have yt_dlp as a module even if
    # the import check above was bypassed by caller-specific path state.
    candidates.append([sys.executable, "-m", "yt_dlp"])

    for cmd in candidates:
        try:
            result = subprocess.run(
                [*cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
                **_hidden_subprocess_kwargs(),
            )
            if result.returncode == 0:
                return cmd
        except Exception:
            continue
    return None


def youtube_import_output_dir(root: Path | str) -> Path:
    out = Path(root).expanduser() / "YouTube Imports"
    out.mkdir(parents=True, exist_ok=True)
    return out


def youtube_output_template(out_dir: Path | str) -> str:
    return str(Path(out_dir) / "%(title).120B [%(id)s].%(ext)s")


def _hidden_subprocess_kwargs() -> dict[str, Any]:
    try:
        from app.subprocess_utils import hidden_subprocess_kwargs

        return hidden_subprocess_kwargs()
    except Exception:
        if sys.platform.startswith("win"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}
        return {}


def _ffmpeg_location_args() -> list[str]:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return ["--ffmpeg-location", str(Path(get_ffmpeg_exe()).resolve())]
    except Exception:
        return []


def _existing_final_mp4(out_dir: Path, info: dict[str, Any], candidate: Path | None) -> Path | None:
    candidates: list[Path] = []
    if candidate is not None:
        candidates.extend([candidate, candidate.with_suffix(".mp4")])
    for row in info.get("requested_downloads") or []:
        if isinstance(row, dict):
            fp = row.get("filepath") or row.get("_filename") or row.get("filename")
            if fp:
                p = Path(str(fp))
                candidates.extend([p, p.with_suffix(".mp4")])
    for key in ("filepath", "_filename", "filename"):
        if info.get(key):
            p = Path(str(info[key]))
            candidates.extend([p, p.with_suffix(".mp4")])
    for p in candidates:
        try:
            if p.is_file() and p.suffix.lower() == ".mp4":
                return p.resolve()
        except Exception:
            continue
    mp4s = [p for p in out_dir.glob("*.mp4") if p.is_file()]
    if not mp4s:
        return None
    return max(mp4s, key=lambda p: p.stat().st_mtime_ns).resolve()


def download_youtube_to_mp4(
    url: str,
    out_dir: Path | str,
    *,
    quality: str | int | None = None,
    progress_cb: ProgressCallback | None = None,
) -> Path:
    """Download one YouTube URL as MP4 and return the final local file path."""
    url = str(url or "").strip()
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are supported.")
    try:
        from yt_dlp import YoutubeDL
    except Exception:
        return _download_youtube_to_mp4_cli(url, out_dir, quality=quality, progress_cb=progress_cb)

    out_root = youtube_import_output_dir(out_dir)
    latest_candidate: Path | None = None

    def _emit(percent: int, label: str) -> None:
        if callable(progress_cb):
            progress_cb(max(0, min(100, int(percent))), label)

    def _progress_hook(row: dict[str, Any]) -> None:
        nonlocal latest_candidate
        status = str(row.get("status") or "")
        filename = row.get("filename")
        if filename:
            latest_candidate = Path(str(filename))
        if status == "downloading":
            total = float(row.get("total_bytes") or row.get("total_bytes_estimate") or 0.0)
            done = float(row.get("downloaded_bytes") or 0.0)
            pct = int(done / total * 80.0) if total > 0 else 5
            _emit(pct, "Downloading")
        elif status == "finished":
            _emit(84, "Preparing MP4")

    def _post_hook(row: dict[str, Any]) -> None:
        status = str(row.get("status") or "")
        if status == "started":
            _emit(88, "Merging MP4")
        elif status == "finished":
            _emit(96, "Finalizing")

    opts: dict[str, Any] = {
        "format": youtube_format_selector(quality),
        "merge_output_format": "mp4",
        "outtmpl": youtube_output_template(out_root),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "windowsfilenames": True,
        "progress_hooks": [_progress_hook],
        "postprocessor_hooks": [_post_hook],
    }
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        opts["ffmpeg_location"] = str(Path(get_ffmpeg_exe()).resolve())
    except Exception:
        pass

    _emit(1, "Starting")
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    if not isinstance(info, dict):
        raise RuntimeError("yt-dlp did not return video metadata.")
    final_path = _existing_final_mp4(out_root, info, latest_candidate)
    if final_path is None:
        raise RuntimeError("Download finished, but no MP4 output was found.")
    _emit(100, "Imported")
    return final_path


def _download_youtube_to_mp4_cli(
    url: str,
    out_dir: Path | str,
    *,
    quality: str | int | None = None,
    progress_cb: ProgressCallback | None = None,
) -> Path:
    cmd_base = yt_dlp_cli_command()
    if cmd_base is None:
        raise RuntimeError(
            "yt-dlp is not installed or not visible to this app. "
            "Install it in the app environment, or keep .venv\\Scripts\\yt-dlp.exe available."
        )

    out_root = youtube_import_output_dir(out_dir)
    latest_candidate: Path | None = None

    def _emit(percent: int, label: str) -> None:
        if callable(progress_cb):
            progress_cb(max(0, min(100, int(percent))), label)

    cmd = [
        *cmd_base,
        "--no-playlist",
        "-f",
        youtube_format_selector(quality),
        "--merge-output-format",
        "mp4",
        "--windows-filenames",
        "--newline",
        "--progress-template",
        "download:%(progress._percent_str)s",
        "--print",
        "after_move:filepath",
        "-o",
        youtube_output_template(out_root),
        *_ffmpeg_location_args(),
        url,
    ]

    _emit(1, "Starting yt-dlp")
    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_hidden_subprocess_kwargs(),
        )
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            lines.append(line)
            if len(lines) > 80:
                lines = lines[-80:]
            match = re.search(r"(\d+(?:\.\d+)?)%", line)
            if match:
                pct = min(84, int(float(match.group(1)) * 0.84))
                _emit(pct, "Downloading")
            p = Path(line.strip('"'))
            if p.suffix.lower() == ".mp4":
                latest_candidate = p
        code = proc.wait()
    except Exception as exc:
        raise RuntimeError(f"yt-dlp launch failed: {exc}") from exc
    if code != 0:
        tail = "\n".join(lines[-12:]) or f"exit code {code}"
        raise RuntimeError(f"yt-dlp failed:\n{tail}")

    _emit(96, "Finalizing")
    final_path = _existing_final_mp4(out_root, {}, latest_candidate)
    if final_path is None:
        raise RuntimeError("Download finished, but no MP4 output was found.")
    _emit(100, "Imported")
    return final_path
