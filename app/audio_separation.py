"""Audio source separation helpers for the Sound Editor.

The high-quality path uses Demucs when it is available in the current
Python environment. The fallback path uses FFmpeg mid/side extraction so
the feature remains usable without shipping a large ML dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.subprocess_utils import hidden_subprocess_kwargs


@dataclass(frozen=True)
class SeparationResult:
    vocals_path: Path
    instrumental_path: Path
    method: str
    note: str = ""


class SeparationCancelled(RuntimeError):
    """Raised when the user cancels an in-flight source separation."""


def _safe_stem(path: Path) -> str:
    stem = path.stem.strip() or "audio"
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in bad or ord(ch) < 32 else ch for ch in stem)
    return cleaned.strip(" ._") or "audio"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 1000):
        candidate = parent / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem}_new{suffix}"


def _terminate_process(proc) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2.0)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _run_cancellable_command(
    cmd: list[str],
    *,
    is_cancelled=None,
    on_process=None,
):
    import subprocess

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )
    if on_process is not None:
        on_process(proc)
    try:
        while True:
            if is_cancelled is not None and is_cancelled():
                _terminate_process(proc)
                raise SeparationCancelled("cancelled")
            try:
                stdout, stderr = proc.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if on_process is not None:
            on_process(None)
    if is_cancelled is not None and is_cancelled():
        raise SeparationCancelled("cancelled")
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def default_stem_output_dir(source_path: Path, output_root: Path | None = None) -> Path:
    source_path = Path(source_path)
    root = Path(output_root) if output_root is not None else source_path.parent
    return root / f"{_safe_stem(source_path)}_stems"


def _demucs_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("demucs") is not None


def _local_ml_sealed() -> bool:
    try:
        from app.local_ml import local_ml_temporarily_disabled

        return bool(local_ml_temporarily_disabled())
    except Exception:
        return True


def planned_separation_method(*, prefer_demucs: bool = True) -> str:
    if prefer_demucs and not _local_ml_sealed() and _demucs_available():
        return "Demucs"
    return "FFmpeg mid/side"


def validate_audio_source(source_path: Path | str) -> Path:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(str(source))
    if not source.is_file():
        raise ValueError(f"Not a file: {source}")
    try:
        if source.stat().st_size <= 0:
            raise ValueError(f"File is empty: {source}")
    except OSError as exc:
        raise ValueError(f"Could not read file metadata: {source}") from exc
    return source


def _run_demucs(
    source_path: Path,
    output_dir: Path,
    *,
    is_cancelled=None,
    on_process=None,
) -> SeparationResult:
    import shutil
    import sys
    import tempfile

    stem = _safe_stem(source_path)
    vocals_path = _unique_path(output_dir / f"{stem}_vocals.wav")
    instrumental_path = _unique_path(output_dir / f"{stem}_instrumental.wav")

    with tempfile.TemporaryDirectory(prefix="tigercapture_demucs_") as tmp:
        tmp_dir = Path(tmp)
        cmd = [
            sys.executable,
            "-m",
            "demucs",
            "--two-stems=vocals",
            "--out",
            str(tmp_dir),
            str(source_path),
        ]
        proc = _run_cancellable_command(
            cmd,
            is_cancelled=is_cancelled,
            on_process=on_process,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "")[-2000:]
            raise RuntimeError(err or f"demucs exited {proc.returncode}")

        vocals = next(iter(tmp_dir.rglob("vocals.wav")), None)
        no_vocals = next(iter(tmp_dir.rglob("no_vocals.wav")), None)
        if vocals is None or no_vocals is None:
            raise RuntimeError("demucs finished but did not produce vocals/no_vocals stems")

        shutil.copy2(vocals, vocals_path)
        shutil.copy2(no_vocals, instrumental_path)

    return SeparationResult(
        vocals_path=vocals_path,
        instrumental_path=instrumental_path,
        method="Demucs",
        note="AI two-stem separation",
    )


def _run_ffmpeg_mid_side(
    source_path: Path,
    output_dir: Path,
    *,
    is_cancelled=None,
    on_process=None,
) -> SeparationResult:
    from imageio_ffmpeg import get_ffmpeg_exe

    stem = _safe_stem(source_path)
    vocals_path = _unique_path(output_dir / f"{stem}_vocals.wav")
    instrumental_path = _unique_path(output_dir / f"{stem}_instrumental.wav")

    # This is a deterministic fallback, not a neural separator:
    # vocals ~= center/mid channel, instrumental ~= stereo side content.
    filter_graph = (
        "[0:a:0]aformat=channel_layouts=stereo,asplit=2[a][b];"
        "[a]pan=mono|c0=0.5*c0+0.5*c1,highpass=f=120,lowpass=f=12000[vocals];"
        "[b]pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0,volume=2.0[instrumental]"
    )
    cmd = [
        get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-filter_complex",
        filter_graph,
        "-map",
        "[vocals]",
        "-vn",
        "-c:a",
        "pcm_s16le",
        str(vocals_path),
        "-map",
        "[instrumental]",
        "-vn",
        "-c:a",
        "pcm_s16le",
        str(instrumental_path),
    ]
    proc = _run_cancellable_command(
        cmd,
        is_cancelled=is_cancelled,
        on_process=on_process,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2000:]
        raise RuntimeError(err or f"ffmpeg exited {proc.returncode}")

    return SeparationResult(
        vocals_path=vocals_path,
        instrumental_path=instrumental_path,
        method="FFmpeg mid/side",
        note="Fast fallback; best on stereo tracks with centered vocals",
    )


def separate_audio_stems(
    source_path: Path | str,
    output_root: Path | str | None = None,
    *,
    prefer_demucs: bool = True,
    is_cancelled=None,
    on_process=None,
) -> SeparationResult:
    source = validate_audio_source(source_path)

    out_dir = default_stem_output_dir(source, Path(output_root) if output_root else None)
    out_dir.mkdir(parents=True, exist_ok=True)

    if prefer_demucs and not _local_ml_sealed() and _demucs_available():
        try:
            return _run_demucs(
                source,
                out_dir,
                is_cancelled=is_cancelled,
                on_process=on_process,
            )
        except SeparationCancelled:
            raise
        except Exception as exc:
            fallback = _run_ffmpeg_mid_side(
                source,
                out_dir,
                is_cancelled=is_cancelled,
                on_process=on_process,
            )
            return SeparationResult(
                vocals_path=fallback.vocals_path,
                instrumental_path=fallback.instrumental_path,
                method=fallback.method,
                note=f"Demucs failed; used FFmpeg fallback. {exc}",
            )

    return _run_ffmpeg_mid_side(
        source,
        out_dir,
        is_cancelled=is_cancelled,
        on_process=on_process,
    )


class AudioSeparationWorker(QThread):
    """Background worker for SoundEditorWindow source separation."""

    stage = Signal(str)
    done = Signal(str, str, str, str)  # vocals, instrumental, method, note
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        source_path: Path | str,
        output_root: Path | str | None = None,
        parent=None,
        *,
        prefer_demucs: bool = True,
    ) -> None:
        super().__init__(parent)
        self._source_path = Path(source_path)
        self._output_root = Path(output_root) if output_root else None
        self._prefer_demucs = bool(prefer_demucs)
        self._cancel_requested = False
        self._process = None

    def cancel(self) -> None:
        self._cancel_requested = True
        proc = self._process
        if proc is not None:
            _terminate_process(proc)

    def _is_cancelled(self) -> bool:
        return bool(self._cancel_requested)

    def _set_process(self, proc) -> None:
        self._process = proc

    def run(self) -> None:
        try:
            self.stage.emit(f"Using {planned_separation_method(prefer_demucs=self._prefer_demucs)}")
            result = separate_audio_stems(
                self._source_path,
                self._output_root,
                prefer_demucs=self._prefer_demucs,
                is_cancelled=self._is_cancelled,
                on_process=self._set_process,
            )
        except SeparationCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        finally:
            self._process = None
        self.done.emit(
            str(result.vocals_path),
            str(result.instrumental_path),
            result.method,
            result.note,
        )
