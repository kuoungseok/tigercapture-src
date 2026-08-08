"""Capture real Tiger Studio feature surfaces for brand collage assets.

The brand splash should not rely on generated fake UI inside the tiger mark.
This utility renders actual project widgets and render outputs into durable
PNG sources under resources/branding/captures.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from app.qt_opengl_policy import configure_qt_opengl_application_attributes

        configure_qt_opengl_application_attributes()
    except Exception:
        pass
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _process_events(app, count: int = 6) -> None:
    for _ in range(max(1, int(count))):
        app.processEvents()


def _save_widget(widget, path: Path) -> bool:
    pixmap = widget.grab()
    if pixmap.isNull():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(pixmap.save(str(path), "PNG"))


def _capture_sound_editor(out_dir: Path) -> list[Path]:
    from app.audio_tracks import AudioClip
    from app.sound_editor_panel import SoundEditorPanel

    app = _ensure_qt()
    audio_path = out_dir / "_branding_audio_source.wav"
    audio_path.write_bytes(b"branding-audio-source")
    clip = AudioClip(id=9101, source_path=audio_path, duration_ms=126000, trim_end_ms=126000)

    panel = SoundEditorPanel()
    panel.resize(1500, 620)
    panel.set_clip(clip, track="Brand Audio Track", context_label="Timeline Audio", context_key="branding:audio")
    panel._set_advanced_lab_expanded(True)
    panel._apply_ai_preset("Suno v3")
    panel._set_advanced_lab_tab("ai")
    panel.show()
    _process_events(app, 12)

    paths = []
    full = out_dir / "sound_editor_sound_lab_actual.png"
    if _save_widget(panel, full):
        paths.append(full)

    advanced = getattr(panel, "_advanced_lab_panel", None)
    if advanced is not None:
        crop = out_dir / "sound_editor_advanced_lab_actual.png"
        if _save_widget(advanced, crop):
            paths.append(crop)

    try:
        panel.close()
    except Exception:
        pass
    try:
        audio_path.unlink(missing_ok=True)
    except Exception:
        pass
    return paths


def _capture_composer(out_dir: Path) -> list[Path]:
    from app.composer_panel import ComposerPanel
    from app.music_composer import compose_music

    app = _ensure_qt()
    composition = compose_music(
        prompt="subculture broadcast intro with cinematic synths and tight percussion",
        duration_ms=45000,
        genre="electronic",
        mood="confident",
        key="C minor",
        bpm=124,
    ).to_dict()

    panel = ComposerPanel()
    panel.resize(1260, 760)
    panel.set_music_composition(composition)
    panel.show()
    _process_events(app, 12)

    paths = []
    full = out_dir / "composer_music_lab_actual.png"
    if _save_widget(panel, full):
        paths.append(full)

    arrangement = panel.findChild(type(panel), "ComposerArrangementView")
    if arrangement is None:
        from PySide6.QtWidgets import QWidget

        arrangement = panel.findChild(QWidget, "ComposerArrangementView")
    if arrangement is not None:
        crop = out_dir / "composer_arrangement_actual.png"
        if _save_widget(arrangement, crop):
            paths.append(crop)

    try:
        panel.close()
    except Exception:
        pass
    return paths


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _capture_live2d(out_dir: Path) -> list[Path]:
    from PIL import Image, ImageEnhance

    from app.live2d.actor_track import Live2DActorClip

    _ensure_qt()
    model = _first_existing(
        [
            ROOT / "resources" / "live2d_samples" / "ProjectSekai_21miku_normal" / "21miku_normal.model3.json",
            ROOT / "resources" / "live2d_samples" / "HoshinoAi" / "Hoshino_Ai.model3.json",
            ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Hiyori" / "Hiyori.model3.json",
            ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Haru" / "Haru.model3.json",
        ]
    )
    if model is None:
        return []

    clip = Live2DActorClip(model_path=str(model), scale=1.28, pos_x=0.5, pos_y=0.56)
    frames = []
    for idx, pos_ms in enumerate((0, 480, 980), start=1):
        img = clip.render_frame(920, 920, pos_ms)
        if img is None:
            continue
        bg = Image.new("RGBA", img.size, (11, 14, 20, 255))
        grid = Image.new("RGBA", img.size, (0, 0, 0, 0))
        # A quiet studio-grid background makes the character read as an editor
        # capture rather than a loose transparent render.
        pixels = grid.load()
        for x in range(0, grid.size[0], 46):
            for y in range(grid.size[1]):
                pixels[x, y] = (64, 92, 130, 42)
        for y in range(0, grid.size[1], 46):
            for x in range(grid.size[0]):
                pixels[x, y] = (64, 92, 130, 34)
        composed = Image.alpha_composite(bg, grid)
        composed = Image.alpha_composite(composed, img.convert("RGBA"))
        composed = ImageEnhance.Contrast(composed.convert("RGB")).enhance(1.05)
        path = out_dir / f"live2d_actual_{idx}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        composed.save(path)
        frames.append(path)
    return frames


def _default_branding_videos() -> list[Path]:
    video_dir = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports")
    if not video_dir.exists():
        return []
    preferred_tokens = ("lamborghini", "bugatti", "drone", "tokyo", "seoul", "hdr")
    all_videos = [
        path
        for path in video_dir.iterdir()
        if path.is_file()
        and path.suffix.casefold() in {".mp4", ".mov", ".mkv", ".webm"}
        and "trump" not in path.name.casefold()
    ]
    ranked = sorted(
        all_videos,
        key=lambda path: (
            0 if any(token in path.name.casefold() for token in preferred_tokens) else 1,
            -path.stat().st_mtime,
        ),
    )
    return ranked[:3]


def _capture_editor_timeline(out_dir: Path) -> list[Path]:
    from PySide6.QtCore import QTimer

    from app.video_editor_window import VideoEditorWindow

    app = _ensure_qt()
    videos = _default_branding_videos()
    if not videos:
        return []

    os.environ.setdefault("TIGERCAPTURE_SUPPRESS_INTERACTIVE_PROMPTS", "1")
    editor = VideoEditorWindow(source_path=videos[0])
    editor.setWindowTitle("Tiger Studio - branding timeline capture")
    editor.resize(1540, 980)
    editor.show()
    _process_events(app, 20)

    # Let the deferred startup import land, then add a second real video track
    # so the capture clearly shows both preview media and timeline tracks.
    deadline = 0
    while deadline < 80 and not getattr(editor, "_tracks", []):
        _process_events(app, 4)
        deadline += 1
    if len(videos) > 1:
        try:
            editor._add_track_with_source(videos[1])
        except Exception:
            pass
    try:
        editor._set_timeline_zoom_px(38.0)
    except Exception:
        pass
    try:
        splitter = getattr(editor, "_editor_vertical_splitter", None)
        if splitter is not None:
            splitter.setSizes([640, 340])
    except Exception:
        pass
    try:
        editor._player.set_position(1800)
        editor._player.refresh_current_frame()
    except Exception:
        pass
    QTimer.singleShot(1, lambda: None)
    _process_events(app, 40)

    paths = []
    full = out_dir / "editor_video_timeline_actual.png"
    if _save_widget(editor, full):
        paths.append(full)
    preview = getattr(editor, "_preview_frame", None)
    if preview is not None:
        crop = out_dir / "editor_video_preview_actual.png"
        if _save_widget(preview, crop):
            paths.append(crop)
    timeline = getattr(editor, "_timeline_section_host", None)
    if timeline is not None:
        crop = out_dir / "editor_timeline_tracks_actual.png"
        if _save_widget(timeline, crop):
            paths.append(crop)

    try:
        editor.close()
    except Exception:
        pass
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture actual Tiger Studio feature screenshots for branding.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "resources" / "branding" / "captures",
    )
    parser.add_argument(
        "--platform",
        default="offscreen",
        help="Qt platform plugin to use. Use 'windows' for real Windows font fallback captures.",
    )
    args = parser.parse_args()
    if args.platform:
        os.environ["QT_QPA_PLATFORM"] = str(args.platform)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    captured: list[Path] = []
    captured.extend(_capture_editor_timeline(out_dir))
    captured.extend(_capture_sound_editor(out_dir))
    captured.extend(_capture_composer(out_dir))
    captured.extend(_capture_live2d(out_dir))

    manifest = out_dir / "branding_feature_captures.txt"
    manifest.write_text("\n".join(str(path) for path in captured) + "\n", encoding="utf-8")
    for path in captured:
        print(path)
    if not captured:
        raise SystemExit("No captures were generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
