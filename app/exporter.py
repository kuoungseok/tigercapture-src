from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

from app.i18n import tr
from app.subprocess_utils import hidden_subprocess_kwargs


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


def lossy_to_tolerance(lossy: int) -> int:
    """Map the gifsicle ``--lossy`` scale onto a pixel-difference tolerance.

    gifsicle spends its lossy budget on palette error. The built-in encoder
    has no external optimiser to hand that budget to, so it spends it on the
    "did this pixel actually change?" test instead: a higher tolerance keeps
    more of the frame transparent and therefore out of the file. For screen
    recordings — static background, small moving region — that is the same
    trade in practice.
    """
    return max(0, min(48, int(round(int(lossy) / 5.0))))


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
        max_colors: int = 256,
        lossy: int = 60,
    ) -> None:
        super().__init__()
        self._frames = frames
        self._out = Path(out_path)
        self._fps = max(1, int(fps))
        self._scale = float(scale)
        # GIF palette size — clamped to a 2..256 range; standard GIF
        # frames cap at 256 colours per palette anyway.
        self._max_colors = max(2, min(256, int(max_colors)))
        # gifsicle --lossy level. 0 disables lossy entirely (still runs
        # ``-O3`` lossless optimisation when gifsicle is present).
        # Typical useful range is 30..120.
        self._lossy = max(0, int(lossy))

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
        with tempfile.TemporaryDirectory(prefix="tigercapture_") as td:
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
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                **hidden_subprocess_kwargs(),
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    tr(
                        "editor.error.gifski_failed",
                        code=proc.returncode,
                        stderr=proc.stderr.strip()[:200],
                    )
                )
            self.progress.emit(total_steps, total_steps)

    def _build_global_palette(
        self, frames: list[Image.Image], colors: int
    ) -> Image.Image:
        """Derive one shared palette from a downscaled montage of sampled frames.

        The delta encoder needs every frame to index the same palette, so a
        per-frame adaptive palette is not usable. Sampling a dozen frames
        keeps the palette representative without quantizing the whole clip.
        """
        step = max(1, len(frames) // 12)
        picks = frames[::step][:12] or [frames[0]]

        thumbs: list[Image.Image] = []
        for f in picks:
            if f.width > 480:
                ratio = 480 / f.width
                f = f.resize(
                    (480, max(1, int(f.height * ratio))),
                    Image.Resampling.NEAREST,
                )
            thumbs.append(f)

        w = max(t.width for t in thumbs)
        montage = Image.new("RGB", (w, sum(t.height for t in thumbs)))
        y = 0
        for t in thumbs:
            montage.paste(t, (0, y))
            y += t.height
        return montage.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)

    def _encode_with_pillow(
        self, frames: list[Image.Image], total_steps: int
    ) -> None:
        """Encode with inter-frame delta transparency.

        Every pixel that has not changed since the last frame the viewer
        actually saw is written as the transparent index and left in place
        (``disposal=1``), so only the moving region costs bytes. On screen
        recordings this is worth roughly an order of magnitude versus
        writing every frame whole.

        Falls back to whole-frame encoding if anything here fails — a larger
        file is a much better outcome than a broken one.
        """
        if not self._delta_is_worth_it(frames):
            self._encode_whole_frames(frames, total_steps)
            return
        try:
            self._encode_delta(frames, total_steps)
        except Exception:  # noqa: BLE001
            self._encode_whole_frames(frames, total_steps)

    def _delta_is_worth_it(self, frames: list[Image.Image]) -> bool:
        """Cheap pre-check on sampled frames before committing to delta.

        Sensor/compression noise makes almost every pixel differ slightly, and
        at a low tolerance that leaves nothing transparent. The delta encoder
        would then pay for a shared palette (worse than a per-frame adaptive
        one) and get nothing back, producing a *larger* file than whole-frame
        encoding. When there is little to hold still, don't take that trade.
        """
        if len(frames) < 2:
            return False

        tolerance = lossy_to_tolerance(self._lossy)
        n = len(frames)
        # Sample *adjacent* pairs spread across the clip. Comparing frames far
        # apart in time would overstate motion and bail out on clips the delta
        # encoder actually handles well.
        step = max(1, (n - 1) // 8)
        starts = list(range(0, n - 1, step))[:8]

        ratios: list[float] = []
        for i in starts:
            prev = np.asarray(frames[i].convert("RGB"), dtype=np.int16)
            cur = np.asarray(frames[i + 1].convert("RGB"), dtype=np.int16)
            if cur.shape != prev.shape:
                return False
            unchanged = np.abs(cur - prev).max(axis=2) <= tolerance
            ratios.append(float(unchanged.mean()))

        # Below this, the shared palette costs more than the transparency saves.
        return bool(ratios) and (sum(ratios) / len(ratios)) >= 0.15

    def _encode_delta(
        self, frames: list[Image.Image], total_steps: int
    ) -> None:
        n = len(frames)
        duration_ms = max(10, int(round(1000 / self._fps)))

        # One index has to be reserved for transparency, so the palette
        # itself gets one fewer colour than the user asked for.
        pal_colors = max(2, min(255, self._max_colors - 1))
        transparent_idx = pal_colors
        tolerance = lossy_to_tolerance(self._lossy)

        pal_img = self._build_global_palette(frames, pal_colors)
        palette = pal_img.getpalette() or []
        # Give the reserved index a defined entry; the colour is never shown.
        palette = palette[: pal_colors * 3] + [0, 0, 0]

        emitted: list[Image.Image] = []
        # ``shown`` tracks the source colour behind each pixel currently on
        # screen, not the previous source frame. Comparing against it bounds
        # drift to the tolerance in total rather than per frame.
        shown: np.ndarray | None = None

        for i, frame in enumerate(frames):
            rgb = np.asarray(frame.convert("RGB"), dtype=np.int16)
            indexed = np.asarray(
                frame.quantize(palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG),
                dtype=np.uint8,
            ).copy()

            if shown is None:
                shown = rgb.copy()
            else:
                unchanged = np.abs(rgb - shown).max(axis=2) <= tolerance
                indexed[unchanged] = transparent_idx
                shown = np.where(unchanged[..., None], shown, rgb)

            out_img = Image.fromarray(indexed, mode="P")
            out_img.putpalette(palette)
            emitted.append(out_img)
            self.progress.emit(n + i + 1, total_steps)

        self.stage.emit(tr("editor.stage.gif_write"))
        emitted[0].save(
            self._out,
            save_all=True,
            append_images=emitted[1:],
            duration=duration_ms,
            loop=0,
            disposal=1,
            transparency=transparent_idx,
            optimize=False,
        )
        for i in range(n):
            self.progress.emit(n * 2 + i + 1, total_steps)

    def _encode_whole_frames(
        self, frames: list[Image.Image], total_steps: int
    ) -> None:
        n = len(frames)
        duration_ms = max(10, int(round(1000 / self._fps)))

        paletted: list[Image.Image] = []
        for i, f in enumerate(frames):
            q = f.quantize(
                colors=self._max_colors,
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
        cmd = [str(gifsicle_path), "-O3"]
        if self._lossy > 0:
            cmd.append(f"--lossy={self._lossy}")
        # gifski produces a 256-colour GIF regardless of intent — apply
        # the palette cap here so the user-chosen colour count holds for
        # both encoder paths.
        if self._max_colors < 256:
            cmd.append(f"--colors={self._max_colors}")
        cmd.extend(["-o", str(self._out), str(self._out)])
        try:
            subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                timeout=120,
                **hidden_subprocess_kwargs(),
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
