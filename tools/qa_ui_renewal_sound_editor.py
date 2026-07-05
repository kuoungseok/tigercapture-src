from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tools.qa_workbench_node_action_flow import (  # noqa: E402
    _default_media,
    _force_viewer_frame,
    _save_widget,
    _wait,
)


def _audio_clip_by_id(editor: Any, track_id: int, clip_id: int) -> tuple[Any, Any]:
    for track in getattr(editor, "_audio_tracks", []) or []:
        if int(getattr(track, "id", -1)) != int(track_id):
            continue
        for clip in getattr(track, "clips", []) or []:
            if int(getattr(clip, "id", -1)) == int(clip_id):
                return track, clip
    return None, None


def _image_nonblank(path: Path) -> bool:
    try:
        from PySide6.QtGui import QImage

        image = QImage(str(path)).convertToFormat(QImage.Format.Format_RGB888)
        if image.isNull():
            return False
        import numpy as np

        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        data = bytes(image.constBits())
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, bytes_per_line))[:, : width * 3]
        rgb = arr.reshape((height, width, 3))
        return float(rgb.std()) > 2.0 and float(rgb.mean()) > 3.0
    except Exception:
        return False


def _ascii_media_label(path: Path) -> str:
    text = path.name
    safe = text.encode("ascii", errors="ignore").decode("ascii", errors="ignore")
    safe = " ".join(safe.replace("|", "-").split())
    return safe or path.stem.encode("ascii", errors="ignore").decode("ascii", errors="ignore") or "youtube_import_media"


def _wait_for_waveform(app: Any, clip: Any, timeout_ms: int = 7000) -> bool:
    deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
    while time.monotonic() < deadline:
        waveform = getattr(clip, "waveform", None) if clip is not None else None
        if waveform is not None and int(getattr(waveform, "size", 0) or 0) > 0:
            return True
        _wait(app, 80)
    waveform = getattr(clip, "waveform", None) if clip is not None else None
    return bool(waveform is not None and int(getattr(waveform, "size", 0) or 0) > 0)


def _make_contact_sheet(images: list[tuple[str, Path]], out_path: Path) -> bool:
    try:
        from PySide6.QtCore import QRect, Qt
        from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

        thumbs: list[tuple[str, QPixmap]] = []
        for label, path in images:
            pix = QPixmap(str(path))
            if pix.isNull():
                continue
            thumbs.append((label, pix))
        if not thumbs:
            return False

        cols = 2
        rows = (len(thumbs) + cols - 1) // cols
        cell_w = 480
        cell_h = 330
        pad = 22
        title_h = 34
        sheet = QPixmap(cols * cell_w + pad * 2, rows * cell_h + pad * 2)
        sheet.fill(QColor("#101112"))
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        title_font = QFont("Segoe UI Variable", 10)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        for index, (label, pix) in enumerate(thumbs):
            col = index % cols
            row = index // cols
            x = pad + col * cell_w
            y = pad + row * cell_h
            painter.setPen(QColor("#C8CDD8"))
            painter.drawText(QRect(x, y, cell_w, title_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            target = pix.scaled(
                cell_w,
                cell_h - title_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image_x = x + (cell_w - target.width()) // 2
            image_y = y + title_h + (cell_h - title_h - target.height()) // 2
            painter.drawPixmap(image_x, image_y, target)
        painter.end()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return bool(sheet.save(str(out_path), "PNG"))
    except Exception:
        return False


def _capture_sound_graph_tabs(app: Any, sound_panel: Any, out: Path) -> dict[str, Any]:
    captures: list[tuple[str, Path]] = []
    checks: dict[str, bool] = {}

    tab_plan = [
        (
            "eq",
            "EQ tonal curve",
            lambda panel: (
                panel._set_eq_gain_from_graph(0, -3.0),
                panel._set_eq_gain_from_graph(1, 4.8),
                panel._set_eq_gain_from_graph(2, 2.2),
            ),
        ),
        (
            "dyn",
            "Dynamics threshold and ratio",
            lambda panel: panel._set_dynamics_from_graph(-31.5, 7.4),
        ),
        (
            "fx",
            "FX reverb delay de-esser",
            lambda panel: (
                panel._set_fx_value_from_graph(0, 44.0),
                panel._set_fx_value_from_graph(1, 28.0),
                panel._set_fx_value_from_graph(2, 63.0),
            ),
        ),
        (
            "ai",
            "AI master macros",
            lambda panel: (
                panel._set_ai_value_from_graph(0, 3.8),
                panel._set_ai_value_from_graph(1, 58.0),
                panel._set_ai_value_from_graph(2, 24.0),
                panel._set_ai_value_from_graph(3, 132.0),
                panel._set_ai_value_from_graph(4, 47.0),
                panel._set_ai_value_from_graph(5, 31.0),
            ),
        ),
    ]

    for tab_id, label, apply_state in tab_plan:
        try:
            if hasattr(sound_panel, "refresh_waveform"):
                sound_panel.refresh_waveform()
            sound_panel._set_tab(tab_id)
            apply_state(sound_panel)
            _wait(app, 140)
            png = out / f"sound_editor_graph_{tab_id}.png"
            ok = _save_widget(sound_panel, png)
            checks[f"{tab_id}_capture"] = bool(ok)
            checks[f"{tab_id}_capture_nonblank"] = _image_nonblank(png)
            if ok:
                captures.append((label, png))
        except Exception:
            checks[f"{tab_id}_capture"] = False
            checks[f"{tab_id}_capture_nonblank"] = False

    contact = out / "sound_editor_graphs_contact_sheet.png"
    checks["graph_contact_sheet"] = _make_contact_sheet(captures, contact)
    checks["graph_contact_sheet_nonblank"] = _image_nonblank(contact)
    return {
        "checks": checks,
        "captures": {tab_id: str((out / f"sound_editor_graph_{tab_id}.png").resolve()) for tab_id, *_rest in tab_plan},
        "contact_sheet": str(contact.resolve()),
    }


def run_sound_editor_capture(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_sound_editor",
    language: str = "ko",
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

    media_path = Path(media).expanduser() if media else _default_media()
    if not media_path.is_absolute():
        media_path = ROOT / media_path
    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)
    active_language = initialize()
    if language:
        set_language(language)
        active_language = language

    editor = VideoEditorWindow()
    steps: list[dict[str, Any]] = []
    checks: dict[str, bool] = {}
    artifacts: dict[str, str] = {}
    metrics: dict[str, Any] = {"media": str(media_path), "media_display": _ascii_media_label(media_path)}
    dock_window = None
    try:
        try:
            editor._autosave_timer.stop()
            editor._do_autosave = lambda *_args, **_kwargs: None
        except Exception:
            pass
        editor.resize(1480, 920)
        editor.show()
        _wait(app, 240)

        registry = editor._ensure_python_action_registry()
        imported = registry.execute(
            "media.import_to_timeline",
            {"path": str(media_path), "kind": "video", "at_ms": 0},
        ).to_dict()
        steps.append({"action": "media.import_to_timeline", **imported})
        track_id = int((imported.get("result") or {}).get("track_id") or 0)
        clip_id = int((imported.get("result") or {}).get("clip_id") or 0)
        duration_ms = int((imported.get("result") or {}).get("duration_ms") or 0)
        checks["media_imported"] = bool(imported.get("ok") and track_id and clip_id)
        _wait(app, 360)

        seek_ms = min(max(1200, duration_ms // 4), max(1200, duration_ms - 1000)) if duration_ms else 1200
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, seek_ms, out)

        extracted = registry.execute(
            "audio.extract_from_video",
            {
                "track_id": track_id,
                "clip_id": clip_id,
                "link": True,
                "name": "Extracted Audio",
            },
        ).to_dict()
        steps.append({"action": "audio.extract_from_video", **extracted})
        result = extracted.get("result") or {}
        audio_track_id = int(result.get("audio_track_id") or 0)
        audio_clip_id = int(result.get("audio_clip_id") or 0)
        checks["audio_extracted"] = bool(extracted.get("ok") and audio_track_id and audio_clip_id)
        _wait(app, 900)

        gain = registry.execute(
            "audio.clip.set_gain",
            {"track_id": audio_track_id, "clip_id": audio_clip_id, "gain": 0.78},
        ).to_dict()
        steps.append({"action": "audio.clip.set_gain", **gain})
        checks["audio_gain_set"] = bool(gain.get("ok"))

        audio_track, audio_clip = _audio_clip_by_id(editor, audio_track_id, audio_clip_id)
        checks["audio_clip_found"] = bool(audio_track is not None and audio_clip is not None)
        if audio_clip is not None:
            audio_clip.fade_in_ms = 1200
            audio_clip.fade_out_ms = 1800
            audio_clip.effects.setdefault("eq", {})
            audio_clip.effects["eq"].setdefault("low", {})["gain"] = 2.4
            audio_clip.effects["eq"].setdefault("mid", {})["gain"] = -1.8
            audio_clip.effects["eq"].setdefault("high", {})["gain"] = 3.2
            audio_clip.effects["eq"]["enabled"] = True
            audio_clip.effects.setdefault("comp", {})
            audio_clip.effects["comp"]["enabled"] = True
            audio_clip.effects["comp"]["threshold"] = -24.0
            audio_clip.effects["comp"]["ratio"] = 4.8
            try:
                editor._start_waveform_extraction(audio_clip)
            except Exception:
                pass
        checks["waveform_ready_before_graph_capture"] = _wait_for_waveform(app, audio_clip, 7000) if audio_clip is not None else False

        jog_position_ms = max(0, int(getattr(audio_clip, "effective_length_ms", 0) or 0) // 3) if audio_clip is not None else 0
        if audio_clip is not None:
            jog_action = registry.execute(
                "audio.sound_editor.jog_shuttle.set",
                {
                    "track_id": audio_track_id,
                    "clip_id": audio_clip_id,
                    "position_ms": jog_position_ms,
                    "playing": True,
                    "focus_workbench": True,
                },
            ).to_dict()
            steps.append({"action": "audio.sound_editor.jog_shuttle.set", **jog_action})
            jog_result = jog_action.get("result") or {}
            checks["reference_05_jog_shuttle_action"] = bool(
                jog_action.get("ok")
                and int(jog_result.get("position_ms") or -1) == jog_position_ms
                and bool(jog_result.get("playing")) is True
            )
        try:
            editor._active_audio_track_id = audio_track_id
        except Exception:
            pass
        _wait(app, 360)

        panel = getattr(editor, "_workbench_panel", None)
        embedded = panel.findChild(QWidget, "EmbeddedSoundEditor") if panel is not None else None
        if embedded is not None:
            spectrum_strip = embedded.findChild(QWidget, "SoundSpectrumStrip")
            checks["spectrum_strip_visible"] = bool(spectrum_strip is not None and spectrum_strip.isVisible())
            jog_shuttle = embedded.findChild(QWidget, "SoundJogShuttle05")
            checks["reference_05_jog_shuttle_visible"] = bool(
                jog_shuttle is not None and jog_shuttle.isVisible()
            )
            checks["advanced_sound_lab_button_visible"] = any(
                bool(child.isVisible() and child.property("role") == "advanced_audio_lab")
                for child in embedded.findChildren(QWidget)
            )
            jog_state = registry.execute(
                "audio.sound_editor.jog_shuttle.state",
                {"track_id": audio_track_id, "clip_id": audio_clip_id},
            ).to_dict()
            steps.append({"action": "audio.sound_editor.jog_shuttle.state", **jog_state})
            checks["reference_05_jog_shuttle_action_state"] = bool(
                jog_state.get("ok") and (jog_state.get("result") or {}).get("reference_design") == "05"
            )
            getattr(embedded, "_set_tab")("eq")
            graph_report = _capture_sound_graph_tabs(app, embedded, out)
            checks.update({f"graph_{key}": value for key, value in (graph_report.get("checks") or {}).items()})
            artifacts.update({f"graph_{key}": value for key, value in (graph_report.get("captures") or {}).items()})
            artifacts["sound_editor_graphs_contact_sheet"] = str(graph_report.get("contact_sheet") or "")
            getattr(embedded, "_set_tab")("eq")
            advanced_button = next(
                (
                    child for child in embedded.findChildren(QWidget)
                    if bool(child.property("role") == "advanced_audio_lab")
                ),
                None,
            )
            if advanced_button is not None or hasattr(embedded, "_set_advanced_lab_expanded"):
                legacy_labs_before = len(getattr(editor, "_advanced_sound_labs", []) or [])
                advanced_action = registry.execute(
                    "audio.sound_editor.advanced_lab.set",
                    {
                        "track_id": audio_track_id,
                        "clip_id": audio_clip_id,
                        "expanded": True,
                        "focus_workbench": True,
                    },
                ).to_dict()
                steps.append({"action": "audio.sound_editor.advanced_lab.set", **advanced_action})
                try:
                    embedded._dialogue_strength._slider.setValue(58)
                    embedded._noise_reduction._slider.setValue(95)
                    embedded._de_reverb._slider.setValue(36)
                    embedded._time_ratio._slider.setValue(126)
                    embedded._target_lufs._slider.setValue(-180)
                except Exception:
                    pass
                _wait(app, 160)
                legacy_labs_after = len(getattr(editor, "_advanced_sound_labs", []) or [])
                advanced_panel = embedded.findChild(QWidget, "SoundAdvancedLab")
                checks["advanced_sound_lab_inline_visible"] = bool(
                    advanced_panel is not None and advanced_panel.isVisible()
                )
                macro_jog_bank = embedded.findChild(QWidget, "SoundMacroJogBank")
                checks["advanced_sound_lab_macro_jog_bank_visible"] = bool(
                    macro_jog_bank is not None and macro_jog_bank.isVisible()
                )
                ai_preset_buttons = [
                    button for button in embedded.findChildren(QPushButton)
                    if button.objectName() == "SoundPresetButton"
                    and str(button.property("preset") or "") in {"Suno v3", "Suno v4", "Udio", "ACE-Step", "Generic AI", "Custom"}
                ]
                checks["advanced_sound_lab_ai_presets_visible"] = len(ai_preset_buttons) >= 6
                try:
                    apply_ai_preset = getattr(embedded, "_apply_ai_preset")
                    apply_ai_preset("Suno v3")
                    ai_state = getattr(audio_clip, "effects", {}).get("ai_master", {}) if audio_clip is not None else {}
                    checks["advanced_sound_lab_ai_preset_applied"] = bool(
                        ai_state.get("enabled")
                        and ai_state.get("preset") == "Suno v3"
                        and float(ai_state.get("air", 0.0) or 0.0) == 5.0
                    )
                except Exception:
                    checks["advanced_sound_lab_ai_preset_applied"] = False
                advanced_jog = embedded.findChild(QWidget, "SoundJogShuttle05")
                advanced_stack = embedded.findChild(QWidget, "SoundStack")
                advanced_tabs = embedded.findChild(QWidget, "SoundTabs")
                advanced_spectrum = embedded.findChild(QWidget, "SoundSpectrumStrip")
                checks["advanced_sound_lab_keeps_jog_visible"] = bool(
                    advanced_jog is not None and advanced_jog.isVisible()
                )
                checks["advanced_sound_lab_keeps_graph_stack_visible"] = bool(
                    advanced_stack is not None and advanced_stack.isVisible()
                )
                checks["advanced_sound_lab_keeps_graph_tabs_visible"] = bool(
                    advanced_tabs is not None and advanced_tabs.isVisible()
                )
                checks["advanced_sound_lab_keeps_spectrum_visible"] = bool(
                    advanced_spectrum is not None and advanced_spectrum.isVisible()
                )
                checks["advanced_sound_lab_no_legacy_window"] = bool(
                    legacy_labs_after == legacy_labs_before
                    and not bool((advanced_action.get("result") or {}).get("opened_legacy_window"))
                )
                advanced_png = out / "workbench_sound_editor_advanced_lab_action.png"
                advanced_target = getattr(editor, "_workbench_section_host", None) or panel or embedded
                checks["advanced_sound_lab_screenshot"] = _save_widget(advanced_target, advanced_png)
                checks["advanced_sound_lab_screenshot_nonblank"] = _image_nonblank(advanced_png)
                artifacts["workbench_sound_editor_advanced_lab"] = str(advanced_png.resolve())
                collapse_action = registry.execute(
                    "audio.sound_editor.advanced_lab.set",
                    {
                        "track_id": audio_track_id,
                        "clip_id": audio_clip_id,
                        "expanded": False,
                        "focus_workbench": True,
                    },
                ).to_dict()
                steps.append({"action": "audio.sound_editor.advanced_lab.set", **collapse_action})
                _wait(app, 120)
        _wait(app, 160)
        checks["viewer_frame_visible_final"] = _force_viewer_frame(editor, media_path, seek_ms, out)
        _wait(app, 80)

        workbench_widget = getattr(editor, "_workbench_section_host", None) or panel or editor
        workbench_png = out / "workbench_sound_editor_action.png"
        editor_png = out / "editor_sound_editor_action.png"
        checks["workbench_screenshot"] = _save_widget(workbench_widget, workbench_png)
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        checks["workbench_screenshot_nonblank"] = _image_nonblank(workbench_png)
        artifacts["workbench_sound_editor"] = str(workbench_png.resolve())
        artifacts["editor_sound_editor"] = str(editor_png.resolve())

        if audio_clip is not None:
            editor._open_sound_editor(audio_track_id, audio_clip_id)
            _wait(app, 360)
            editors = list(getattr(editor, "_sound_editors", []) or [])
            dock_window = editors[-1] if editors else None
            if dock_window is not None:
                embedded_dock = dock_window.findChild(QWidget, "EmbeddedSoundEditor")
                if embedded_dock is not None:
                    getattr(embedded_dock, "_set_tab")("basic")
                _wait(app, 160)
                dock_png = out / "dock_sound_editor_action.png"
                checks["dock_screenshot"] = _save_widget(dock_window, dock_png)
                checks["dock_screenshot_nonblank"] = _image_nonblank(dock_png)
                artifacts["dock_sound_editor"] = str(dock_png.resolve())

        waveform = getattr(audio_clip, "waveform", None) if audio_clip is not None else None
        checks["waveform_ready_or_pending_allowed"] = bool(waveform is None or getattr(waveform, "size", 0) >= 0)
        checks["waveform_ready"] = bool(waveform is not None and getattr(waveform, "size", 0) > 0)
        checks["sound_editor_panel_visible"] = bool(embedded is not None and embedded.isVisible())
        metrics["audio_track_id"] = audio_track_id
        metrics["audio_clip_id"] = audio_clip_id
        metrics["waveform_size"] = int(getattr(waveform, "size", 0) or 0) if waveform is not None else 0
    finally:
        try:
            if dock_window is not None:
                dock_window.close()
        except Exception:
            pass
        editor.close()
        app.processEvents()
        time.sleep(0.05)

    report = {
        "scenario": "ui_renewal_sound_editor",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": active_language,
        "steps": steps,
        "checks": checks,
        "artifacts": artifacts,
        "metrics": metrics,
        "ok": all(checks.values()) if checks else False,
    }
    report_path = out / "sound_editor_qa.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture renewed Sound Editor UI with real media.")
    parser.add_argument("--media", default=None, help="Video media path. Defaults to YouTube Imports/sample fallback.")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_sound_editor"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args(argv)

    report = run_sound_editor_capture(media=args.media, out_dir=args.out_dir, language=args.language)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
