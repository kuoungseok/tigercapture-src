from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QSlider


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEMO_DIR = ROOT / "external" / "assets" / "ai_edit_demo"
MANIFEST_PATH = DEMO_DIR / "manifest.json"
PROCESS_PROJECT_PATH = DEMO_DIR / "TigerStudio_AI_Full_Process_Demo.tgp"
CAPTURE_DIR = ROOT / "debugCapture" / "ai_edit_demo"
CAPTURE_PATH = CAPTURE_DIR / "tigerstudio_ai_full_process_demo.mp4"
REPORT_PATH = CAPTURE_DIR / "tigerstudio_ai_full_process_demo_report.json"


def _ensure_assets() -> None:
    if MANIFEST_PATH.is_file():
        return
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "prepare_ai_edit_demo.py")],
        cwd=str(ROOT),
        check=True,
    )


def _load_manifest_rows() -> list[dict[str, Any]]:
    _ensure_assets()
    doc = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = [dict(row) for row in doc.get("clips", []) if isinstance(row, dict)]
    if not rows:
        raise RuntimeError(f"demo manifest has no clips: {MANIFEST_PATH}")
    return rows


def _write_process_project(rows: list[dict[str, Any]]) -> None:
    PROCESS_PROJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": "1.1",
        "app": "TigerCapture",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "px_per_sec": 46.0,
        "playhead_ms": 0,
        "global_in_ms": 0,
        "global_out_ms": 34000,
        "project_settings": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "aspect": "16:9",
            "title": "Tiger Studio AI Full Process Demo",
            "demo_mode": "ai_full_process",
        },
        "video_tracks": [],
        "audio_tracks": [],
        "subtitles": [],
        "media_pool": [str(Path(row["path"]).resolve()) for row in rows],
        "media_pool_metadata": [
            {
                "path": str(Path(row["path"]).resolve()),
                "kind": "video",
                "name": Path(row["path"]).name,
                "badge": str(row.get("role") or "demo"),
                "source": str(Path(row.get("source") or row["path"]).resolve()),
            }
            for row in rows
        ],
        "ai_edit_demo": {
            "schema": "tigerstudio.demo.ai_edit_full_process.v1",
            "intent": "show process, not just final timeline",
            "prompt": (
                "Build a creator promo edit. Assemble clips, cut the timeline, add typography, "
                "open the node graph, tune effect parameters, and show Viewer Compare split."
            ),
        },
    }
    PROCESS_PROJECT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _install_app_defaults(app: QApplication) -> None:
    os.environ["TIGERCAPTURE_CAPTURE_TO_STUDIO"] = "1"
    try:
        from app.preview_acceleration import configure_preview_acceleration_defaults

        configure_preview_acceleration_defaults()
    except Exception:
        pass
    try:
        from app.qt_opengl_policy import configure_qt_opengl_application_attributes

        configure_qt_opengl_application_attributes()
    except Exception:
        pass
    QCoreApplication.setApplicationName("Tiger Studio")
    QCoreApplication.setOrganizationName("TigerCapture")
    app.setApplicationName("Tiger Studio")
    app.setOrganizationName("TigerCapture")
    app.setStyle("Fusion")
    try:
        from app.font_fallback import apply_ui_font

        apply_ui_font(app)
    except Exception:
        pass
    try:
        from app.i18n import initialize as init_i18n
        from app.style import APP_QSS

        app.setStyleSheet(APP_QSS)
        init_i18n()
    except Exception:
        pass
    icon_path = ROOT / "resources" / "tigercapture.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))


def _action_label_style() -> str:
    return """
        QLabel {
            background: rgba(10, 14, 22, 222);
            color: #F6F8FF;
            border: 1px solid rgba(130, 170, 255, 145);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 15px;
            font-weight: 700;
        }
    """


def _caption_style(position_y: float = 0.84) -> dict[str, Any]:
    return {
        "font_size": 48,
        "font_weight": 800,
        "color": "#FFFFFF",
        "position_x": 0.5,
        "position_y": position_y,
        "outline_color": "#05070D",
        "outline_width": 5,
        "shadow_color": "#000000",
        "shadow_offset_x": 0,
        "shadow_offset_y": 4,
        "shadow_blur": 8,
        "background_color": "#101625",
        "background_padding": 14,
        "background_radius": 8,
    }


def _caption_animation() -> dict[str, Any]:
    return {
        "preset_id": "ai-process-pop",
        "in_animation": "fade-in",
        "hold_animation": "none",
        "out_animation": "fade-out",
        "in_duration": 0.2,
        "out_duration": 0.22,
    }


class FullProcessDemoRunner:
    def __init__(self, app: QApplication, rows: list[dict[str, Any]]) -> None:
        self.app = app
        self.rows = rows
        self.editor = None
        self.registry = None
        self.badge: QLabel | None = None
        self.capture_session_id = "ai-full-process-demo"
        self.track_id: int = 0
        self.track_ids: dict[str, int] = {}
        self.clip_ids: dict[str, int] = {}
        self.next_timeline_ms = 0
        self.log: list[dict[str, Any]] = []
        self.finished = False

    def safe_start(self) -> None:
        try:
            self.start()
        except Exception as exc:
            self._fail("start", exc)

    def start(self) -> None:
        from app.project_io import load_project
        from app.video_editor_window_core import VideoEditorWindow
        from app.actions import build_default_action_registry

        self.editor = VideoEditorWindow(source_path=None)
        self.editor.setWindowTitle("Tiger Studio - AI Full Process Demo")
        self.editor.setGeometry(40, 40, 1600, 900)
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()
        self.app.processEvents()

        load_project(self.editor, PROCESS_PROJECT_PATH)
        self.editor._project_path = PROCESS_PROJECT_PATH
        if hasattr(self.editor, "_refresh_window_title"):
            self.editor._refresh_window_title()
        self.editor.setWindowTitle("Tiger Studio - AI Full Process Demo")
        self.registry = build_default_action_registry(self.editor)
        self._make_badge()
        self._badge("AI prompt: build a full edit and show every decision")
        QTimer.singleShot(1200, self._start_capture_and_steps)

    def _fail(self, stage: str, exc: Exception) -> None:
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        self.log.append({"event": "error", "stage": stage, "error": repr(exc)})
        REPORT_PATH.write_text(
            json.dumps({"ok": False, "stage": stage, "error": repr(exc), "log": self.log}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            from app.window_capture import stop_window_video_capture

            stop_window_video_capture(session_id=self.capture_session_id, wait_ms=5000)
        except Exception:
            pass
        QTimer.singleShot(0, self.app.quit)

    def _make_badge(self) -> None:
        if self.editor is None:
            return
        self.badge = QLabel(self.editor)
        self.badge.setStyleSheet(_action_label_style())
        self.badge.setText("")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.badge.setGeometry(250, 80, 620, 54)
        self.badge.show()
        self.badge.raise_()

    def _badge(self, text: str) -> None:
        if self.badge is not None:
            self.badge.setText(f"AI Action  |  {text}")
            self.badge.adjustSize()
            self.badge.setMinimumWidth(620)
            self.badge.move(250, 80)
            self.badge.show()
            self.badge.raise_()
        flash = getattr(self.editor, "_flash_status", None)
        if callable(flash):
            try:
                flash(text)
            except Exception:
                pass
        self.app.processEvents()

    def _start_capture_and_steps(self) -> None:
        try:
            from app.window_capture import start_window_video_capture

            CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
            if CAPTURE_PATH.exists():
                CAPTURE_PATH.unlink()
            hwnd = int(self.editor.winId()) if self.editor is not None else 0
            self._foreground_editor_window(hwnd)
            try:
                start = start_window_video_capture(
                    session_id=self.capture_session_id,
                    path=CAPTURE_PATH,
                    hwnd=hwnd,
                    max_duration_ms=95000,
                    fps=15,
                    backend="wgc_window",
                    activate=True,
                    crf=21,
                )
            except Exception as wgc_exc:
                self.log.append({"event": "capture.backend_fallback", "from": "wgc_window", "to": "visible", "error": str(wgc_exc)})
                self._foreground_editor_window(hwnd)
                start = start_window_video_capture(
                    session_id=self.capture_session_id,
                    path=CAPTURE_PATH,
                    hwnd=hwnd,
                    max_duration_ms=95000,
                    fps=15,
                    backend="visible",
                    activate=True,
                    crf=21,
                )
            self.log.append({"event": "capture.start", "result": start})
            REPORT_PATH.write_text(json.dumps({"ok": None, "log": self.log}, ensure_ascii=False, indent=2), encoding="utf-8")
            self._run_steps()
        except Exception as exc:
            self._fail("capture.start", exc)

    def _foreground_editor_window(self, hwnd: int) -> None:
        if not hwnd:
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 32, 9, 1616, 939, SWP_SHOWWINDOW)
            user32.SetForegroundWindow(hwnd)
            self.app.processEvents()
            time.sleep(0.45)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetForegroundWindow(hwnd)
        except Exception as exc:
            self.log.append({"event": "foreground_error", "error": str(exc)})
        self.app.processEvents()

    def _run_steps(self) -> None:
        steps: list[tuple[int, str, Callable[[], None]]] = [
            (300, "Create edit tracks", self._create_demo_tracks),
            (600, "Import Seoul opener", lambda: self._import_clip_on_lane(0, "main", at_ms=0, caption="AI builds the V1 story spine")),
            (2300, "Import Lamborghini main shot", lambda: self._import_clip_on_lane(1, "main", at_ms=3900, caption="AI cuts from city mood into product energy")),
            (2200, "Import OLED insert", lambda: self._import_clip_on_lane(3, "insert", at_ms=5200, caption="V2 insert: color texture for the hook")),
            (2200, "Import Bugatti detail", lambda: self._import_clip_on_lane(2, "main", at_ms=7600, caption="AI adds a luxury hero insert")),
            (2100, "Layer Tokyo cutaway", lambda: self._import_clip_on_lane(4, "cutaway", at_ms=10100, caption="V3 cutaway: pacing and atmosphere")),
            (2100, "Import Tokyo bridge", lambda: self._import_clip_on_lane(4, "main", at_ms=10700, caption="AI bridges the timeline with a night city beat")),
            (2100, "Import HDR accent", lambda: self._import_clip_on_lane(6, "insert", at_ms=12500, caption="AI layers an HDR accent over the edit")),
            (2100, "Import race rhythm", lambda: self._import_clip_on_lane(5, "main", at_ms=14600, caption="AI chooses a fast rhythm shot")),
            (2100, "Import Seoul close", lambda: self._import_clip_on_lane(7, "main", at_ms=18000, caption="AI closes on an aerial city shot")),
            (2100, "Layer closing cutaway", lambda: self._import_clip_on_lane(7, "cutaway", at_ms=18100, caption="V3 closing texture keeps the timeline alive")),
            (2300, "Cut at the beat", self._split_first_clip),
            (2200, "Apply transition", self._apply_transition),
            (2300, "Add speed ramp", self._set_speed),
            (2200, "Focus insert track", self._focus_insert_track),
            (2600, "Open node graph", self._open_node_graph),
            (2600, "Add color and blur nodes", self._add_node_chain),
            (2600, "Tune color grade and blur", self._tune_color_and_blur),
            (2600, "Enable split compare", self._enable_compare),
            (3200, "Add final typography", self._add_final_typography),
            (7800, "Play the finished sequence to the end", self._play_range),
            (22800, "Show completion frame", self._mark_done),
            (1800, "Stop", self._finish),
        ]

        elapsed = 0
        for delay, label, fn in steps:
            elapsed += delay
            QTimer.singleShot(elapsed, lambda label=label, fn=fn: self._safe_step(label, fn))

    def _safe_step(self, label: str, fn: Callable[[], None]) -> None:
        try:
            self.log.append({"event": "step.start", "label": label, "time": time.time()})
            fn()
            self.log.append({"event": "step.end", "label": label, "time": time.time()})
            if not self.finished:
                REPORT_PATH.write_text(json.dumps({"ok": None, "log": self.log}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self._fail(label, exc)

    def _act(self, action: str, params: dict[str, Any] | None = None, *, destructive: bool = False) -> dict[str, Any]:
        if self.registry is None:
            raise RuntimeError("action registry not ready")
        result = self.registry.execute_action(
            action,
            params or {},
            confirm_destructive=bool(destructive),
        ).to_dict()
        self.log.append({"event": "action", "action": action, "params": params or {}, "result": result})
        if not result.get("ok"):
            self._badge(f"{action} failed: {result.get('error')}")
        self.app.processEvents()
        return result

    def _create_demo_tracks(self) -> None:
        self._badge("timeline: create V1/V2/V3 edit lanes")
        specs = [
            ("main", "V1 Main Cut", {}),
            ("insert", "V2 Inserts", {"pip_enabled": True, "pip_x": 0.70, "pip_y": 0.18, "pip_scale": 0.34, "pip_opacity": 0.94}),
            ("cutaway", "V3 Cutaways", {"pip_enabled": True, "pip_x": 0.18, "pip_y": 0.75, "pip_scale": 0.30, "pip_opacity": 0.78}),
        ]
        for lane, name, state in specs:
            result = self._act("track.add", {"kind": "video", "name": name})
            payload = result.get("result") or {}
            track_id = int(payload.get("track_id") or 0)
            if not track_id:
                continue
            self.track_ids[lane] = track_id
            if lane == "main":
                self.track_id = track_id
            self._act("track.rename", {"kind": "video", "track_id": track_id, "name": name})
            if state:
                params = {"kind": "video", "track_id": track_id}
                params.update(state)
                self._act("track.set_state", params)
        if self.track_id:
            self._act("track.select", {"kind": "video", "track_id": self.track_id, "select_first_clip": False})
        self._act("timeline.set_playhead", {"ms": 0})

    def _import_clip(self, row_index: int, *, at_ms: int, caption: str) -> None:
        self._import_clip_on_lane(row_index, "main", at_ms=at_ms, caption=caption)

    def _import_clip_on_lane(self, row_index: int, lane: str, *, at_ms: int, caption: str) -> None:
        row = self.rows[row_index]
        name = Path(str(row["path"])).stem
        lane_name = {"main": "V1", "insert": "V2", "cutaway": "V3"}.get(lane, lane.upper())
        self._badge(f"import to {lane_name}: {name[:34]}")
        target_track = int(self.track_ids.get(lane) or (self.track_id if lane == "main" else 0))
        params: dict[str, Any] = {
            "path": str(Path(row["path"]).resolve()),
            "kind": "video",
            "at_ms": int(at_ms),
            "duration_ms": int(row.get("duration_ms") or 3600),
        }
        if target_track:
            params["track_id"] = target_track
        result = self._act("media.import_to_timeline", params)
        payload = result.get("result") or {}
        target_track = int(payload.get("track_id") or target_track or 0)
        if target_track:
            self.track_ids[lane] = target_track
            if lane == "main":
                self.track_id = target_track
        clip_id = int(payload.get("clip_id") or 0)
        if clip_id:
            self.clip_ids[f"{lane}:{row_index}"] = clip_id
            if lane == "main":
                self.clip_ids[str(row_index)] = clip_id
            self._act("clip.select", {"kind": "video", "track_id": target_track, "clip_id": clip_id})
            self._act(
                "text.add",
                {
                    "track_id": target_track,
                    "clip_id": clip_id,
                    "text": caption,
                    "start_ms": int(at_ms) + 250,
                    "end_ms": int(at_ms) + min(3000, int(row.get("duration_ms") or 3600)),
                    "style": _caption_style(),
                    "animation": _caption_animation(),
                },
            )
        self._act("timeline.set_playhead", {"ms": int(at_ms) + 450})

    def _split_first_clip(self) -> None:
        self._badge("blade cut: split the opener on a visual beat")
        result = self._act("timeline.split", {"track_id": self.track_id, "at_ms": 2100})
        payload = result.get("result") or {}
        right_id = int(payload.get("right_clip_id") or 0)
        left_id = int(payload.get("left_clip_id") or self.clip_ids.get("0", 0))
        if left_id:
            self.clip_ids["0_left"] = left_id
        if right_id:
            self.clip_ids["0_right"] = right_id
            self._act("clip.select", {"kind": "video", "track_id": self.track_id, "clip_id": right_id})
        self._act("timeline.set_playhead", {"ms": 2120})

    def _apply_transition(self) -> None:
        clip_id = self.clip_ids.get("0_left") or self.clip_ids.get("0")
        self._badge("transition: dissolve out of the first shot")
        if clip_id:
            self._act(
                "transition.apply",
                {
                    "track_id": self.track_id,
                    "clip_id": clip_id,
                    "transition_type": "dissolve",
                    "duration_ms": 420,
                    "side": "out",
                },
            )
        self._act("timeline.set_playhead", {"ms": 3820})

    def _set_speed(self) -> None:
        clip_id = self.clip_ids.get("1")
        self._badge("speed: ramp the Lamborghini detail shot")
        if clip_id:
            self._act("clip.set_speed", {"track_id": self.track_id, "clip_id": clip_id, "speed": 1.35})
            self._act(
                "text.add",
                {
                    "track_id": self.track_id,
                    "clip_id": clip_id,
                    "text": "AI changes speed, then checks the cut in context",
                    "start_ms": 4200,
                    "end_ms": 6500,
                    "style": _caption_style(0.78),
                    "animation": _caption_animation(),
                },
            )
        self._act("timeline.set_playhead", {"ms": 4500})

    def _focus_insert_track(self) -> None:
        self._badge("track focus: select V2 insert, then return to the graded V1 track")
        insert_track = int(self.track_ids.get("insert") or 0)
        if insert_track:
            self._act("track.select", {"kind": "video", "track_id": insert_track, "select_first_clip": True})
            self._act("timeline.set_playhead", {"ms": 5400})
        if self.track_id:
            self._act("track.select", {"kind": "video", "track_id": self.track_id, "select_first_clip": True})

    def _open_node_graph(self) -> None:
        self._badge("open node graph: route the active track through effects")
        self._show_embedded_node_graph()

    def _add_node_chain(self) -> None:
        self._badge("node graph: add color grade + strong blur nodes")
        self._act(
            "node.add",
            {
                "track_id": self.track_id,
                "kind": "curves",
                "label": "AI Color Grade",
                "node_id": "AI_COLOR",
                "x": -70,
                "y": -70,
                "params": {
                    "kind": "curves",
                    "master": [[0, 0], [0.28, 0.22], [0.58, 0.70], [1, 1]],
                    "red": [[0, 0], [1, 1]],
                    "green": [[0, 0], [0.55, 0.60], [1, 1]],
                    "blue": [[0, 0], [0.55, 0.68], [1, 1]],
                },
                "auto_connect": True,
            },
        )
        self._act(
            "node.add",
            {
                "track_id": self.track_id,
                "kind": "blur",
                "label": "AI Focus Blur",
                "node_id": "AI_BLUR",
                "x": 170,
                "y": 90,
                "params": {"kind": "blur", "radius": 24, "shape": "gaussian", "strength": 0.55, "enabled": True},
                "auto_connect": True,
            },
        )
        self._show_embedded_node_graph()
        self._select_node("AI_COLOR")
        self._act("timeline.set_playhead", {"ms": 4550})

    def _tune_color_and_blur(self) -> None:
        self._badge("parameters: push contrast, cool shadows, then add heavy blur")
        self._show_embedded_node_graph()
        self._select_node("AI_COLOR")
        self._animate_effect_sliders([74, 68, 62, 58])
        self._act(
            "node.set_param",
            {
                "track_id": self.track_id,
                "node_id": "AI_COLOR",
                "params": {
                    "kind": "curves",
                    "master": [[0, 0], [0.22, 0.14], [0.55, 0.74], [1, 1]],
                    "red": [[0, 0], [0.55, 0.52], [1, 1]],
                    "green": [[0, 0], [0.55, 0.61], [1, 1]],
                    "blue": [[0, 0], [0.50, 0.72], [1, 1]],
                },
                "merge": False,
            },
        )
        self._show_embedded_node_graph()
        self._select_node("AI_BLUR")
        self._act(
            "node.set_param",
            {
                "track_id": self.track_id,
                "node_id": "AI_BLUR",
                "params": {"kind": "blur", "radius": 54, "shape": "gaussian", "strength": 0.82, "enabled": True},
                "merge": True,
            },
        )

    def _enable_compare(self) -> None:
        self._badge("viewer compare: split before / after node processing")
        self._act("ui.viewer.compare.set", {"track_id": self.track_id, "mode": "split", "labels_enabled": True})
        self._act("ui.viewer.fit", {})
        self._act("timeline.set_playhead", {"ms": 4820})

    def _add_final_typography(self) -> None:
        clip_id = self.clip_ids.get("main:5") or self.clip_ids.get("2") or self.clip_ids.get("1")
        self._badge("typography: add a readable AI decision caption")
        if clip_id:
            self._act(
                "text.add",
                {
                    "track_id": self.track_id,
                    "clip_id": clip_id,
                    "text": "Before / After: color grade and blur are visible in split view",
                    "start_ms": 14900,
                    "end_ms": 17700,
                    "style": _caption_style(0.18),
                    "animation": _caption_animation(),
                },
            )
        self._act("timeline.set_playhead", {"ms": 15100})

    def _play_range(self) -> None:
        self._badge("final review: play the finished edit through the closing shot")
        self._act("ui.viewer.compare.set", {"track_id": self.track_id, "mode": "off", "labels_enabled": False})
        self._act("ui.viewer.fit", {})
        self._act("timeline.play_range", {"start_ms": 0, "end_ms": 21800, "restore_playhead": False})

    def _mark_done(self) -> None:
        self._act("timeline.set_playhead", {"ms": 21800})
        self._badge("done: final review reached the closing shot")

    def _finish(self) -> None:
        from app.window_capture import stop_window_video_capture

        stop = stop_window_video_capture(session_id=self.capture_session_id, wait_ms=30000)
        self.log.append({"event": "capture.stop", "result": stop})
        self.finished = True
        REPORT_PATH.write_text(json.dumps({"ok": True, "log": self.log}, ensure_ascii=False, indent=2), encoding="utf-8")
        QTimer.singleShot(500, self.app.quit)

    def _video_track(self) -> Any | None:
        for track in list(getattr(self.editor, "_tracks", []) or []):
            if int(getattr(track, "id", 0) or 0) == int(self.track_id):
                return track
        return None

    def _show_embedded_node_graph(self) -> None:
        track = self._video_track()
        owner = self.editor
        if owner is None or track is None:
            return
        wb = getattr(owner, "_workbench_panel", None)
        if wb is None:
            return
        try:
            set_video_track = getattr(wb, "set_video_track", None)
            if callable(set_video_track):
                set_video_track(track, None)
            set_tab = getattr(wb, "_set_inspector_tab", None)
            if callable(set_tab):
                set_tab("fx")
            ensure = getattr(wb, "_ensure_node_graph_widget", None)
            widget = ensure() if callable(ensure) else getattr(wb, "_node_graph_widget", None)
            if widget is not None:
                widget.set_track(track)
                widget.setVisible(True)
                widget.show()
                fit = getattr(widget, "fit_all", None)
                if callable(fit):
                    fit()
        except Exception as exc:
            self.log.append({"event": "show_node_graph_error", "error": str(exc)})
        self.app.processEvents()

    def _graph_widget(self) -> Any | None:
        owner = self.editor
        if owner is None:
            return None
        panel = getattr(owner, "_workbench_panel", None)
        expose = getattr(panel, "expose_node_graph_widget", None)
        if callable(expose):
            try:
                widget = expose()
                if widget is not None:
                    return widget
            except Exception:
                pass
        pop = getattr(owner, "_node_graph_popout", None)
        graph = getattr(pop, "graph_widget", None)
        return graph

    def _select_node(self, node_id: str) -> None:
        widget = self._graph_widget()
        scene = getattr(widget, "scene", None)
        if widget is None or scene is None:
            return
        try:
            scene.clearSelection()
            target = None
            for item in scene.items():
                if str(getattr(item, "node_id", "")) == str(node_id):
                    target = item
                    break
            if target is not None:
                target.setSelected(True)
                emit = getattr(scene, "_emit_selection_label", None)
                if callable(emit):
                    emit()
                fit = getattr(widget, "fit_all", None)
                if callable(fit):
                    fit()
        except Exception as exc:
            self.log.append({"event": "select_node_error", "node_id": node_id, "error": str(exc)})
        self.app.processEvents()

    def _animate_effect_sliders(self, values: list[int]) -> None:
        widget = self._graph_widget()
        if widget is None:
            return
        panel = getattr(widget, "_effect_params_panel", None)
        if panel is None:
            return
        sliders = panel.findChildren(QSlider)
        for slider, value in zip(sliders, values):
            try:
                slider.setValue(max(slider.minimum(), min(slider.maximum(), int(value))))
                self.app.processEvents()
                time.sleep(0.18)
            except Exception:
                pass


def main() -> int:
    rows = _load_manifest_rows()
    _write_process_project(rows)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    _install_app_defaults(app)
    runner = FullProcessDemoRunner(app, rows)
    QTimer.singleShot(0, runner.safe_start)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
