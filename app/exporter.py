from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

from app.i18n import tr


APP_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DIR = APP_ROOT / "bundled"


def find_gifski() -> Path | None:
    """Locate gifski: bundled directory first, then PATH. None if not found."""
    candidates = [
        BUNDLED_DIR / "gifski.exe",
        BUNDLED_DIR / "gifski",
        APP_ROOT / "gifski.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    found = shutil.which("gifski")
    return Path(found) if found else None


def find_gifsicle() -> Path | None:
    candidates = [
        BUNDLED_DIR / "gifsicle.exe",
        BUNDLED_DIR / "gifsicle",
    ]
    for c in candidates:
        if c.exists():
            return c
    found = shutil.which("gifsicle")
    return Path(found) if found else None


class GifExportThread(QThread):
    """Encode frames to a GIF file in a background thread.

    Backend priority (automatic):
        1) gifski  — near-video quality (per-frame palette + temporal dither)
        2) Pillow  — per-frame adaptive 256-color palette + Floyd-Steinberg

    Optional post-processing:
        - gifsicle -O3 --lossy=60  to shave additional size when available

    Signals:
        progress(current_step, total_steps) — for progress bar
        stage(str) — human-readable current stage
        finished_success(Path, int) — path and final file size in bytes
        finished_error(str) — error message
    """

    progress = Signal(int, int)
    stage = Signal(str)
    finished_success = Signal(Path, int)
    finished_error = Signal(str)

    def __init__(
        self,
        frames: list[Image.Image],
        out_path: Path,
        fps: int,
        scale: float = 1.0,
    ) -> None:
        super().__init__()
        self._frames = frames
        self._out = Path(out_path)
        self._fps = max(1, int(fps))
        self._scale = float(scale)

    def run(self) -> None:
        try:
            n = len(self._frames)
            if n == 0:
                raise RuntimeError(tr("editor.error.no_frames"))

            total_steps = n * 3

            self.stage.emit(tr("editor.stage.rescale"))
            frames = self._scale_frames(total_steps)

            gifski = find_gifski()
            if gifski is not None:
                self.stage.emit(tr("editor.stage.gifski"))
                self._encode_with_gifski(frames, gifski, total_steps)
            else:
                self.stage.emit(tr("editor.stage.palette"))
                self._encode_with_pillow(frames, total_steps)

            gifsicle = find_gifsicle()
            if gifsicle is not None:
                self.stage.emit(tr("editor.stage.gifsicle"))
                self._post_optimize_gifsicle(gifsicle)

            size = self._out.stat().st_size
            self.finished_success.emit(self._out, size)
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(str(exc))

    def _scale_frames(self, total_steps: int) -> list[Image.Image]:
        n = len(self._frames)
        if self._scale >= 0.999:
            for i in range(n):
                self.progress.emit(i + 1, total_steps)
            return list(self._frames)

        out: list[Image.Image] = []
        for i, f in enumerate(self._frames):
            new_size = (
                max(1, int(f.width * self._scale)),
                max(1, int(f.height * self._scale)),
            )
            out.append(f.resize(new_size, Image.Resampling.LANCZOS))
            self.progress.emit(i + 1, total_steps)
        return out

    def _encode_with_gifski(
        self, frames: list[Image.Image], gifski_path: Path, total_steps: int
    ) -> None:
        n = len(frames)
        with tempfile.TemporaryDirectory(prefix="gifcam_") as td:
            td_path = Path(td)
            for i, f in enumerate(frames):
                f.save(td_path / f"frame_{i:05d}.png", "PNG")
                self.progress.emit(n + i + 1, total_steps)

            pngs = sorted(td_path.glob("frame_*.png"))
            cmd = [
                str(gifski_path),
                "--fps", str(self._fps),
                "-o", str(self._out),
                *[str(p) for p in pngs],
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(
                    tr(
                        "editor.error.gifski_failed",
                        code=proc.returncode,
                        stderr=proc.stderr.strip()[:200],
                    )
                )
            self.progress.emit(total_steps, total_steps)

    def _encode_with_pillow(
        self, frames: list[Image.Image], total_steps: int
    ) -> None:
        n = len(frames)
        duration_ms = max(10, int(round(1000 / self._fps)))

        paletted: list[Image.Image] = []
        for i, f in enumerate(frames):
            q = f.quantize(
                colors=256,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            paletted.append(q)
            self.progress.emit(n + i + 1, total_steps)

        self.stage.emit(tr("editor.stage.gif_write"))
        paletted[0].save(
            self._out,
            save_all=True,
            append_images=paletted[1:],
            duration=duration_ms,
            loop=0,
            disposal=2,
        )
        for i in range(n):
            self.progress.emit(n * 2 + i + 1, total_steps)

    def _post_optimize_gifsicle(self, gifsicle_path: Path) -> None:
        try:
            subprocess.run(
                [
                    str(gifsicle_path),
                    "-O3",
                    "--lossy=60",
                    "-o", str(self._out),
                    str(self._out),
                ],
                check=False,
                capture_output=True,
                timeout=120,
            )
        except Exception:
            pass


class Mp4ExportThread(QThread):
    """Encode frames to MP4 (H.264) using imageio-ffmpeg in the background.

    Uses libx264 with yuv420p pixel format for broad player compatibility.
    Ensures even dimensions (H.264 requires width/height divisible by 2).
    """

    progress = Signal(int, int)
    stage = Signal(str)
    finished_success = Signal(Path, int)
    finished_error = Signal(str)

    def __init__(
        self,
        frames: list[Image.Image],
        out_path: Path,
        fps: int,
        scale: float = 1.0,
        crf: int = 20,
    ) -> None:
        super().__init__()
        self._frames = frames
        self._out = Path(out_path)
        self._fps = max(1, int(fps))
        self._scale = float(scale)
        self._crf = max(0, min(51, int(crf)))

    def run(self) -> None:
        try:
            import imageio.v2 as imageio

            n = len(self._frames)
            if n == 0:
                raise RuntimeError(tr("editor.error.no_frames"))
            total_steps = n * 2

            self.stage.emit(tr("editor.stage.rescale"))
            frames = self._scale_frames(total_steps)

            w, h = frames[0].size
            if w % 2:
                w -= 1
            if h % 2:
                h -= 1
            if w < 2 or h < 2:
                raise RuntimeError(tr("editor.error.too_small"))

            self.stage.emit(tr("editor.stage.mp4"))
            writer = imageio.get_writer(
                str(self._out),
                fps=self._fps,
                codec="libx264",
                pixelformat="yuv420p",
                macro_block_size=1,
                ffmpeg_params=["-crf", str(self._crf), "-preset", "medium"],
            )
            try:
                for i, f in enumerate(frames):
                    if f.size != (w, h):
                        f = f.crop((0, 0, w, h))
                    writer.append_data(np.asarray(f))
                    self.progress.emit(n + i + 1, total_steps)
            finally:
                writer.close()

            size = self._out.stat().st_size
            self.finished_success.emit(self._out, size)
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(str(exc))

    def _scale_frames(self, total_steps: int) -> list[Image.Image]:
        n = len(self._frames)
        if self._scale >= 0.999:
            for i in range(n):
                self.progress.emit(i + 1, total_steps)
            return list(self._frames)

        out: list[Image.Image] = []
        for i, f in enumerate(self._frames):
            new_size = (
                max(2, int(f.width * self._scale)),
                max(2, int(f.height * self._scale)),
            )
            out.append(f.resize(new_size, Image.Resampling.LANCZOS))
            self.progress.emit(i + 1, total_steps)
        return out
