"""Standalone MMD player window backed by the editor OpenGL preview widget."""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from pathlib import Path
import time
from typing import Any

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.mmd.animation import evaluate_model_pose
from app.mmd.diagnostics import format_mmd_performance_line
from app.mmd.framing import auto_frame_bounds, bounds_from_positions
from app.mmd.gpu_preview import MMD_GPU_MORPH_SLOTS, MMD_RENDER_TOON, build_mmd_render_item
from app.mmd.lighting import MMD_LIGHTING_PRESETS, resolve_mmd_lighting
from app.mmd.loader import load_mmd_model
from app.mmd.physics import (
    SECONDARY_ROTATION_HINT_SCALE,
    SPRING_PHYSICS_RESPONSE,
    DecimatedPhysicsBackend,
    configure_mmd_physics_backend,
    create_mmd_physics_backend,
    mmd_physics_backend_diagnostics,
)
from app.mmd.pmx import MMDModel
from app.mmd.vmd import VMDMotion, camera_at, camera_to_view_controls, load_vmd
from app.opengl_preview import OpenGLPreviewWidget
from app.style import studio_chrome_qss


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = (
    ROOT
    / "local_resources"
    / "mmd"
    / "model_pool"
    / "playable"
    / "vmd_validated"
    / "vocaloid_default"
    / "miku_m.pmd"
)
DEFAULT_MOTION = (
    ROOT
    / "local_resources"
    / "mmd"
    / "model_pool"
    / "motions"
    / "validated"
    / "wavefile_v2_arora_14.vmd"
)
FLASHY_MODEL_POOL = ROOT / "local_resources" / "mmd" / "model_pool" / "playable" / "flashy_girls" / "manifest.json"
PREFERRED_FLASHY_MODEL_ID = "ww_cantarella"
DEFAULT_FRONT_YAW = 0.0
DEFAULT_FRONT_PITCH = -4.0
DEFAULT_FRONT_ZOOM = 1.0
DEFAULT_FRONT_OFFSET_X = 0.0
DEFAULT_FRONT_OFFSET_Y = -0.02
DEFAULT_TURNTABLE_DURATION_MS = 10000
DEFAULT_BLOOM_STRENGTH = 0.30
PREVIEW_TIMER_MS = 33
PREVIEW_MAX_IK_ITERATIONS = 12
PLAYBACK_MAX_IK_ITERATIONS = 2
PLAYBACK_MIN_IK_ITERATIONS = 1
PLAYBACK_ADAPTIVE_IK_LIMIT = 4
FOOT_IK_REACH_LIMIT = 0.985
POSE_CACHE_LIMIT = 48
PLAYBACK_PHYSICS_INTERVAL_FRAMES = 2.0
PLAYBACK_PHYSICS_SMOOTHING_RESPONSE = 0.88
PLAYBACK_SECONDARY_ROTATION_HINT_SCALE = SECONDARY_ROTATION_HINT_SCALE
PLAYBACK_SPRING_PHYSICS_RESPONSE = SPRING_PHYSICS_RESPONSE
MMD_PLAYER_DEFAULT_WIDTH = 960
MMD_PLAYER_DEFAULT_HEIGHT = 540
MMD_PLAYER_MIN_WIDTH = 820
MMD_PLAYER_MIN_HEIGHT = 480
MMD_PREVIEW_MIN_WIDTH = 470
MMD_PREVIEW_MIN_HEIGHT = 264
MMD_CONTROL_PANEL_WIDTH = 292

MMD_PLAYER_COMPACT_QSS = """
QMainWindow#mmdPlayerWindow {
    background-color: #101114;
}
QScrollArea#mmdControlScroll {
    background: transparent;
    border: none;
    border-radius: 0px;
}
QFrame#mmdControls {
    background-color: #15161B;
    border: 1px solid #2A2F3A;
    border-radius: 8px;
}
QFrame#mmdControls QLabel[class="fieldLabel"] {
    background: transparent;
    border: none;
    border-radius: 0px;
    color: #9EA7B5;
    font-size: 10px;
    font-weight: 700;
    min-height: 12px;
    padding: 0px;
}
QFrame#mmdControls QLabel#mmdStatus {
    background-color: #101319;
    border: 1px solid #2A2F3A;
    border-radius: 6px;
    color: #AEB6C5;
    font-size: 10px;
    padding: 7px;
}
QFrame#mmdControls QPushButton {
    border-radius: 7px;
    min-height: 22px;
    padding: 3px 8px;
}
QFrame#mmdControls QPushButton#mmdIconButton {
    min-width: 28px;
    max-width: 28px;
    min-height: 26px;
    max-height: 26px;
    padding: 0px;
}
QFrame#mmdControls QPushButton#mmdTransportButton {
    min-height: 26px;
    max-height: 26px;
    padding: 2px 8px;
}
QFrame#mmdControls QComboBox {
    border-radius: 7px;
    min-height: 22px;
    padding: 3px 8px;
}
QFrame#mmdControls QCheckBox {
    color: #B9C2D0;
    font-size: 11px;
    font-weight: 650;
    spacing: 7px;
}
QFrame#mmdControls QCheckBox::indicator {
    width: 14px;
    height: 14px;
}
QFrame#mmdControls QSlider {
    min-height: 16px;
    max-height: 18px;
}
QFrame#mmdControls QSlider::groove:horizontal {
    height: 3px;
}
QFrame#mmdControls QSlider::handle:horizontal {
    width: 12px;
    height: 12px;
    margin: -5px 0px;
    border-radius: 6px;
}
"""


def _safe_resolve(base: Path, value: str) -> Path:
    return (base / str(value or "")).resolve()


def _model_pool_entries(manifest_path: Path = FLASHY_MODEL_POOL) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    root = manifest_path.parent
    entries: list[dict[str, Any]] = []
    for raw in data.get("entries", []):
        if not isinstance(raw, dict):
            continue
        model = _safe_resolve(root, str(raw.get("model") or ""))
        motion_raw = str(data.get("default_motion") or raw.get("default_motion") or "")
        motion = _safe_resolve(root, motion_raw) if motion_raw else None
        try:
            motion_start_ms = int(raw.get("default_motion_start_ms", data.get("default_motion_start_ms", 0)) or 0)
        except Exception:
            motion_start_ms = 0
        if not model.is_file():
            continue
        entries.append(
            {
                "id": str(raw.get("id") or model.stem),
                "display_name": str(raw.get("display_name") or model.stem),
                "group": str(raw.get("group") or ""),
                "model": model,
                "motion": motion if motion is not None and motion.is_file() else None,
                "motion_start_ms": max(0, motion_start_ms),
            }
        )
    return entries


def _default_model_from_pool() -> Path:
    entries = _model_pool_entries()
    if entries:
        preferred = next((entry for entry in entries if entry.get("id") == PREFERRED_FLASHY_MODEL_ID), None)
        return Path((preferred or entries[0])["model"])
    return DEFAULT_MODEL


def _background_frame(width: int = 1280, height: int = 720) -> np.ndarray:
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.clip(18 + 24 * (1.0 - y) + 8 * x, 0, 255).astype(np.uint8)
    frame[:, :, 1] = np.clip(19 + 25 * (1.0 - y) + 5 * x, 0, 255).astype(np.uint8)
    frame[:, :, 2] = np.clip(22 + 30 * (1.0 - y) + 12 * x, 0, 255).astype(np.uint8)
    floor = int(height * 0.72)
    frame[floor:, :, :] = np.array([24, 25, 28], dtype=np.uint8)
    return np.ascontiguousarray(frame)


class MMDPlayerWindow(QMainWindow):
    def __init__(self, model_path: str | Path | None = None, motion_path: str | Path | None = None) -> None:
        super().__init__()
        self.setObjectName("mmdPlayerWindow")
        self.setWindowTitle("TigerCapture MMD Player")
        self.resize(MMD_PLAYER_DEFAULT_WIDTH, MMD_PLAYER_DEFAULT_HEIGHT)
        self.setMinimumSize(MMD_PLAYER_MIN_WIDTH, MMD_PLAYER_MIN_HEIGHT)
        self.setStyleSheet(studio_chrome_qss() + MMD_PLAYER_COMPACT_QSS)

        self.preview = OpenGLPreviewWidget(self)
        self.preview.setMinimumSize(MMD_PREVIEW_MIN_WIDTH, MMD_PREVIEW_MIN_HEIGHT)
        self.preview.setMouseTracking(True)
        self.preview.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.preview.installEventFilter(self)
        self._base_frame = _background_frame()
        explicit_model = model_path is not None
        self._model_pool_entries = _model_pool_entries()
        self._model_combo_updating = False
        self._model_path = Path(model_path) if model_path else _default_model_from_pool()
        self._startup_motion_path = Path(motion_path) if motion_path else (
            self._motion_for_model(self._model_path)
            if not explicit_model
            else None
        )
        self._startup_motion_start_ms = 0 if explicit_model else self._motion_start_for_model(self._model_path)
        self._model: MMDModel | None = None
        self._motion_path: Path | None = None
        self._motion: VMDMotion | None = None
        self._secondary_rotation_hint_scale = PLAYBACK_SECONDARY_ROTATION_HINT_SCALE
        self._spring_physics_response = PLAYBACK_SPRING_PHYSICS_RESPONSE
        self._physics_backend_preference = "auto"
        self._physics_backend = self._create_physics_backend()
        self._physics_generation = 0
        self._pose_cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._adaptive_playback_ik_iterations = PLAYBACK_MAX_IK_ITERATIONS
        self._last_refresh_seconds = 0.0
        self._last_preview_fps = 0.0
        self._last_pose_eval_seconds = 0.0
        self._last_render_item_seconds = 0.0
        self._last_status_perf_update_time = 0.0
        self._last_item: dict[str, Any] | None = None
        self._playing = True
        self._playhead_ms = 0
        self._last_tick_time = time.perf_counter()
        self._yaw = DEFAULT_FRONT_YAW
        self._pitch = DEFAULT_FRONT_PITCH
        self._roll = 0.0
        self._zoom = DEFAULT_FRONT_ZOOM
        self._offset_x = DEFAULT_FRONT_OFFSET_X
        self._offset_y = DEFAULT_FRONT_OFFSET_Y
        self._manual_view_override = False
        self._view_dragging = False
        self._view_drag_last = QPointF()
        self._bloom_strength = DEFAULT_BLOOM_STRENGTH
        self._lighting_controls_updating = False
        self._key_yaw_deg = 42.0
        self._key_height_deg = 50.0
        self._key_intensity = 1.0
        self._fill_intensity = 0.32
        self._rim_intensity = 0.12
        self._ambient_intensity = 0.40
        self._shadow_strength = 0.64
        self._status = QLabel("")
        self._status.setObjectName("mmdStatus")
        self._status.setWordWrap(True)
        self._status.setMaximumHeight(68)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.model_combo = QComboBox()
        self._populate_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_selected)

        self.lighting_combo = QComboBox()
        for key, preset in MMD_LIGHTING_PRESETS.items():
            self.lighting_combo.addItem(str(preset.get("label") or key), key)
        self.lighting_combo.currentIndexChanged.connect(self._on_lighting_preset_changed)

        self.play_button = QPushButton()
        self.play_button.setObjectName("mmdTransportButton")
        self.play_button.setIcon(app_icon("play"))
        self.play_button.setIconSize(icon_size(16))
        self.play_button.setMinimumWidth(74)
        self.play_button.setToolTip("Play / Pause")
        self.play_button.clicked.connect(self.toggle_play)

        self.stop_button = QPushButton()
        self.stop_button.setObjectName("mmdTransportButton")
        self.stop_button.setIcon(app_icon("stop"))
        self.stop_button.setIconSize(icon_size(16))
        self.stop_button.setText("Stop")
        self.stop_button.setMinimumWidth(62)
        self.stop_button.setToolTip("Stop")
        self.stop_button.clicked.connect(self.stop_playback)

        self.gpu_skinning_checkbox = QCheckBox("GPU Skinning")
        self.gpu_skinning_checkbox.setChecked(True)
        self.gpu_skinning_checkbox.setToolTip("Use GPU vertex skinning when supported. SDEF stays on CPU.")
        self.gpu_skinning_checkbox.toggled.connect(self._on_gpu_skinning_toggled)

        self.physics_backend_combo = QComboBox()
        self.physics_backend_combo.setToolTip("Physics solver. Auto uses PyBullet when available, otherwise Spring.")
        self.physics_backend_combo.addItem("Auto", "auto")
        self.physics_backend_combo.addItem("Spring", "spring")
        self.physics_backend_combo.addItem("PyBullet", "pybullet")
        self.physics_backend_combo.addItem("None", "none")
        self.physics_backend_combo.currentIndexChanged.connect(self._on_physics_backend_changed)

        self.open_button = QPushButton()
        self.open_button.setObjectName("mmdIconButton")
        self.open_button.setIcon(app_icon("folder"))
        self.open_button.setIconSize(icon_size(16))
        self.open_button.setToolTip("Open PMX/PMD")
        self.open_button.clicked.connect(self.open_model)

        self.open_vmd_button = QPushButton()
        self.open_vmd_button.setObjectName("mmdIconButton")
        self.open_vmd_button.setIcon(app_icon("video"))
        self.open_vmd_button.setIconSize(icon_size(16))
        self.open_vmd_button.setToolTip("Open VMD")
        self.open_vmd_button.clicked.connect(self.open_vmd)

        self.reset_button = QPushButton()
        self.reset_button.setObjectName("mmdIconButton")
        self.reset_button.setIcon(app_icon("reset"))
        self.reset_button.setIconSize(icon_size(16))
        self.reset_button.setToolTip("Reset view")
        self.reset_button.clicked.connect(self.reset_view)

        self.yaw_slider = self._angle_slider(-180, 180, int(self._yaw))
        self.pitch_slider = self._angle_slider(-80, 45, int(self._pitch))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(35, 220)
        self.zoom_slider.setValue(int(round(self._zoom * 100.0)))
        self.bloom_slider = QSlider(Qt.Orientation.Horizontal)
        self.bloom_slider.setRange(0, 150)
        self.bloom_slider.setValue(int(round(self._bloom_strength * 100.0)))
        self.bloom_value = QLabel("")
        self.bloom_value.setMinimumWidth(38)
        self.bloom_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.key_yaw_value = QLabel("")
        self.key_height_value = QLabel("")
        self.key_value = QLabel("")
        self.fill_value = QLabel("")
        self.rim_value = QLabel("")
        self.ambient_value = QLabel("")
        self.shadow_value = QLabel("")
        self.cloth_motion_value = QLabel("")
        self.follow_response_value = QLabel("")
        for value_label in (
            self.key_yaw_value,
            self.key_height_value,
            self.key_value,
            self.fill_value,
            self.rim_value,
            self.ambient_value,
            self.shadow_value,
            self.cloth_motion_value,
            self.follow_response_value,
        ):
            value_label.setMinimumWidth(38)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.key_yaw_slider = self._angle_slider(-180, 180, int(self._key_yaw_deg))
        self.key_height_slider = self._angle_slider(5, 85, int(self._key_height_deg))
        self.key_slider = QSlider(Qt.Orientation.Horizontal)
        self.key_slider.setRange(0, 200)
        self.fill_slider = QSlider(Qt.Orientation.Horizontal)
        self.fill_slider.setRange(0, 120)
        self.rim_slider = QSlider(Qt.Orientation.Horizontal)
        self.rim_slider.setRange(0, 120)
        self.ambient_slider = QSlider(Qt.Orientation.Horizontal)
        self.ambient_slider.setRange(0, 100)
        self.shadow_slider = QSlider(Qt.Orientation.Horizontal)
        self.shadow_slider.setRange(0, 100)
        self.cloth_motion_slider = QSlider(Qt.Orientation.Horizontal)
        self.cloth_motion_slider.setRange(0, 30)
        self.cloth_motion_slider.setValue(int(round(self._secondary_rotation_hint_scale * 100.0)))
        self.follow_response_slider = QSlider(Qt.Orientation.Horizontal)
        self.follow_response_slider.setRange(15, 150)
        self.follow_response_slider.setValue(int(round(self._spring_physics_response * 100.0)))
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, DEFAULT_TURNTABLE_DURATION_MS)
        self.time_slider.setValue(0)

        self.yaw_slider.valueChanged.connect(self._set_yaw)
        self.pitch_slider.valueChanged.connect(self._set_pitch)
        self.zoom_slider.valueChanged.connect(self._set_zoom_percent)
        self.bloom_slider.valueChanged.connect(self._set_bloom_percent)
        self.key_yaw_slider.valueChanged.connect(self._set_key_yaw)
        self.key_height_slider.valueChanged.connect(self._set_key_height)
        self.key_slider.valueChanged.connect(self._set_key_intensity)
        self.fill_slider.valueChanged.connect(self._set_fill_intensity)
        self.rim_slider.valueChanged.connect(self._set_rim_intensity)
        self.ambient_slider.valueChanged.connect(self._set_ambient_intensity)
        self.shadow_slider.valueChanged.connect(self._set_shadow_strength)
        self.cloth_motion_slider.valueChanged.connect(self._set_cloth_motion_percent)
        self.follow_response_slider.valueChanged.connect(self._set_follow_response_percent)
        self.time_slider.sliderMoved.connect(self._set_time)
        self._sync_bloom_label()
        self._sync_physics_tuning_labels()

        controls = QFrame()
        controls.setObjectName("mmdControls")
        controls.setFixedWidth(MMD_CONTROL_PANEL_WIDTH)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(7)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addWidget(self.play_button)
        top_row.addWidget(self.stop_button)
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.open_vmd_button)
        top_row.addWidget(self.reset_button)
        top_row.addStretch(1)
        controls_layout.addLayout(top_row)
        controls_layout.addWidget(self._label("Playhead"))
        controls_layout.addWidget(self.time_slider)
        controls_layout.addWidget(self.gpu_skinning_checkbox)
        controls_layout.addWidget(self._label("Physics Backend"))
        controls_layout.addWidget(self.physics_backend_combo)
        controls_layout.addLayout(self._slider_row("Cloth/Hair", self.cloth_motion_value))
        controls_layout.addWidget(self.cloth_motion_slider)
        controls_layout.addLayout(self._slider_row("Follow", self.follow_response_value))
        controls_layout.addWidget(self.follow_response_slider)
        controls_layout.addWidget(self._label("Model"))
        controls_layout.addWidget(self.model_combo)
        controls_layout.addWidget(self._label("Lighting"))
        controls_layout.addWidget(self.lighting_combo)
        controls_layout.addLayout(self._slider_row("Key Dir", self.key_yaw_value))
        controls_layout.addWidget(self.key_yaw_slider)
        controls_layout.addLayout(self._slider_row("Key Height", self.key_height_value))
        controls_layout.addWidget(self.key_height_slider)
        controls_layout.addLayout(self._slider_row("Key", self.key_value))
        controls_layout.addWidget(self.key_slider)
        controls_layout.addLayout(self._slider_row("Fill", self.fill_value))
        controls_layout.addWidget(self.fill_slider)
        controls_layout.addLayout(self._slider_row("Rim", self.rim_value))
        controls_layout.addWidget(self.rim_slider)
        controls_layout.addLayout(self._slider_row("Ambient", self.ambient_value))
        controls_layout.addWidget(self.ambient_slider)
        controls_layout.addLayout(self._slider_row("Shadow", self.shadow_value))
        controls_layout.addWidget(self.shadow_slider)
        bloom_row = QHBoxLayout()
        bloom_row.addWidget(self._label("Bloom"))
        bloom_row.addStretch(1)
        bloom_row.addWidget(self.bloom_value)
        controls_layout.addLayout(bloom_row)
        controls_layout.addWidget(self.bloom_slider)
        controls_layout.addSpacing(8)
        controls_layout.addWidget(self._status)
        controls_layout.addStretch(1)

        control_scroll = QScrollArea()
        control_scroll.setObjectName("mmdControlScroll")
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        control_scroll.setFixedWidth(MMD_CONTROL_PANEL_WIDTH + 10)
        control_scroll.setWidget(controls)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.preview, 1)
        layout.addWidget(control_scroll, 0)
        self.setCentralWidget(root)

        self._timer = QTimer(self)
        self._timer.setInterval(PREVIEW_TIMER_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._sync_play_button()
        self._load_light_controls_from_preset()
        self._playhead_ms = int(self._startup_motion_start_ms)
        self.load_model(self._model_path)
        self._select_model_combo_for_path(self._model_path)
        if self._startup_motion_path is not None and self._model is not None:
            self.load_vmd(self._startup_motion_path)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "fieldLabel")
        return label

    def _slider_row(self, text: str, value_label: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self._label(text))
        row.addStretch(1)
        row.addWidget(value_label)
        return row

    @staticmethod
    def _angle_slider(minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(minimum), int(maximum))
        slider.setValue(int(value))
        return slider

    @staticmethod
    def _key_dir_from_angles(yaw_deg: float, height_deg: float) -> tuple[float, float, float]:
        yaw = math.radians(float(yaw_deg))
        height = math.radians(max(5.0, min(85.0, float(height_deg))))
        horizontal = math.cos(height)
        return (
            math.sin(yaw) * horizontal,
            -math.sin(height),
            -math.cos(yaw) * horizontal,
        )

    @staticmethod
    def _angles_from_key_dir(direction: object) -> tuple[float, float]:
        try:
            x, y, z = (float(direction[0]), float(direction[1]), float(direction[2]))  # type: ignore[index]
        except Exception:
            return 42.0, 50.0
        length = math.sqrt(x * x + y * y + z * z)
        if length <= 0.0001:
            return 42.0, 50.0
        x, y, z = x / length, y / length, z / length
        yaw = math.degrees(math.atan2(x, -z))
        height = math.degrees(math.asin(max(-1.0, min(1.0, -y))))
        return yaw, max(5.0, min(85.0, height))

    @staticmethod
    def _event_position(event: object) -> QPointF:
        try:
            return event.position()  # type: ignore[attr-defined]
        except Exception:
            try:
                return QPointF(event.pos())  # type: ignore[attr-defined]
            except Exception:
                return QPointF()

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(float(minimum), min(float(maximum), float(value)))

    def _reset_pose_cache(self) -> None:
        self._pose_cache.clear()

    def _reset_physics_state(self) -> None:
        self._physics_backend.reset()
        self._physics_generation += 1
        self._reset_pose_cache()

    def _preview_aspect(self) -> float:
        width = max(1, int(self.preview.width() or 0))
        height = max(1, int(self.preview.height() or 0))
        return max(0.25, min(4.0, float(width) / float(height)))

    def _pose_cache_key(
        self,
        frame: float,
        *,
        enable_physics: bool,
        max_ik_iterations: int,
        skin_vertices: bool,
        gpu_morph_slots: int,
    ) -> tuple[Any, ...] | None:
        if self._model is None:
            return None
        motion_key = str(self._motion_path.resolve()) if self._motion_path is not None else ""
        model_key = str(self._model.path.resolve())
        native_frame = int(round(float(frame)))
        return (
            model_key,
            motion_key,
            native_frame,
            bool(enable_physics),
            int(self._physics_generation if enable_physics else 0),
            bool(skin_vertices),
            int(gpu_morph_slots),
            int(max_ik_iterations),
            bool(self._motion is not None),
        )

    def _cached_pose(self, key: tuple[Any, ...] | None):
        if key is None:
            return None
        pose = self._pose_cache.get(key)
        if pose is not None:
            self._pose_cache.move_to_end(key)
        return pose

    def _store_pose_cache(self, key: tuple[Any, ...] | None, pose: Any) -> None:
        if key is None:
            return
        self._pose_cache[key] = pose
        self._pose_cache.move_to_end(key)
        while len(self._pose_cache) > POSE_CACHE_LIMIT:
            self._pose_cache.popitem(last=False)

    def _playback_ik_iterations(self, fast_playback: bool) -> int:
        if not fast_playback:
            return PREVIEW_MAX_IK_ITERATIONS
        return max(
            PLAYBACK_MIN_IK_ITERATIONS,
            min(PLAYBACK_ADAPTIVE_IK_LIMIT, int(self._adaptive_playback_ik_iterations)),
        )

    def _record_refresh_duration(self, seconds: float, fast_playback: bool) -> None:
        self._last_refresh_seconds = max(0.0, float(seconds))
        self._last_preview_fps = 1.0 / self._last_refresh_seconds if self._last_refresh_seconds > 0.000001 else 0.0
        if self._last_item is not None:
            item = dict(self._last_item)
            diagnostics = dict(item.get("diagnostics") or {})
            diagnostics.update(
                {
                    "preview_refresh_ms": self._last_refresh_seconds * 1000.0,
                    "preview_estimated_fps": self._last_preview_fps,
                    "preview_pose_ms": max(0.0, float(self._last_pose_eval_seconds)) * 1000.0,
                    "preview_render_item_ms": max(0.0, float(self._last_render_item_seconds)) * 1000.0,
                    "preview_fast_playback": bool(fast_playback),
                    "pose_cache_size": int(len(self._pose_cache)),
                    "pose_cache_limit": int(POSE_CACHE_LIMIT),
                    "adaptive_ik_iterations": int(self._playback_ik_iterations(fast_playback)),
                }
            )
            item["diagnostics"] = diagnostics
            self._last_item = item
        self._maybe_update_status_for_perf()
        if not fast_playback:
            return
        target = max(0.001, float(PREVIEW_TIMER_MS) / 1000.0)
        if seconds > target * 1.35 and self._adaptive_playback_ik_iterations > PLAYBACK_MIN_IK_ITERATIONS:
            self._adaptive_playback_ik_iterations -= 1
        elif seconds < target * 0.55 and self._adaptive_playback_ik_iterations < PLAYBACK_ADAPTIVE_IK_LIMIT:
            self._adaptive_playback_ik_iterations += 1

    def _maybe_update_status_for_perf(self) -> None:
        now = time.perf_counter()
        if now - self._last_status_perf_update_time < 0.45:
            return
        self._last_status_perf_update_time = now
        self._update_status()

    def latest_render_item(self) -> dict[str, Any] | None:
        """Return the most recent MMD item, including diagnostics added by GL paint."""
        try:
            preview_items = getattr(self.preview, "_mmd_items", None)
            if preview_items and isinstance(preview_items[0], dict):
                self._last_item = preview_items[0]
                return preview_items[0]
        except Exception:
            pass
        return self._last_item

    def _camera_controls_for_pose(self, frame: float, pose_bounds: dict[str, Any]) -> dict[str, float]:
        if self._manual_view_override:
            return {}
        camera = camera_at(self._motion, frame)
        if camera is not None:
            return camera_to_view_controls(
                camera,
                fallback_yaw=self._yaw,
                fallback_pitch=self._pitch,
                fallback_zoom=self._zoom,
                fallback_offset_x=self._offset_x,
                fallback_offset_y=self._offset_y,
            )
        fit = auto_frame_bounds(
            pose_bounds,
            yaw=self._yaw,
            pitch=self._pitch,
            roll=self._roll,
            aspect=self._preview_aspect(),
        )
        return fit.to_camera_controls(yaw=self._yaw, pitch=self._pitch, roll=self._roll)

    def eventFilter(self, watched: object, event: object) -> bool:
        if watched is self.preview:
            event_type = event.type()  # type: ignore[attr-defined]
            if event_type == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
                    self._view_dragging = True
                    self._view_drag_last = self._event_position(event)
                    self.preview.setFocus()
                    event.accept()  # type: ignore[attr-defined]
                    return True
            elif event_type == QEvent.Type.MouseMove:
                if self._view_dragging and event.buttons() & Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
                    pos = self._event_position(event)
                    delta = pos - self._view_drag_last
                    self._view_drag_last = pos
                    self._manual_view_override = True
                    self._yaw += float(delta.x()) * 0.35
                    self._yaw = ((self._yaw + 180.0) % 360.0) - 180.0
                    self._pitch = self._clamp(self._pitch + float(delta.y()) * 0.24, -80.0, 45.0)
                    self._sync_view_controls()
                    self._refresh_view_transform()
                    event.accept()  # type: ignore[attr-defined]
                    return True
            elif event_type == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
                    self._view_dragging = False
                    event.accept()  # type: ignore[attr-defined]
                    return True
            elif event_type == QEvent.Type.Wheel:
                try:
                    steps = float(event.angleDelta().y()) / 120.0  # type: ignore[attr-defined]
                except Exception:
                    steps = 0.0
                if abs(steps) > 0.001:
                    self._manual_view_override = True
                    self._zoom = self._clamp(self._zoom * (1.0 + steps * 0.08), 0.35, 2.20)
                    self._sync_view_controls()
                    self._refresh_view_transform()
                    event.accept()  # type: ignore[attr-defined]
                    return True
        return super().eventFilter(watched, event)

    def _populate_model_combo(self) -> None:
        self._model_combo_updating = True
        self.model_combo.clear()
        for entry in self._model_pool_entries:
            group = str(entry.get("group") or "").strip()
            label = str(entry.get("display_name") or Path(entry["model"]).stem)
            if group:
                label = f"{label} [{group}]"
            self.model_combo.addItem(label, entry)
        self._model_combo_updating = False

    def _motion_for_model(self, model_path: Path) -> Path | None:
        try:
            resolved = Path(model_path).resolve()
        except Exception:
            resolved = Path(model_path)
        for entry in self._model_pool_entries:
            try:
                if Path(entry["model"]).resolve() == resolved:
                    motion = entry.get("motion")
                    return Path(motion) if motion else None
            except Exception:
                continue
        if resolved == DEFAULT_MODEL.resolve() and DEFAULT_MOTION.exists():
            return DEFAULT_MOTION
        return None

    def _motion_start_for_model(self, model_path: Path) -> int:
        try:
            resolved = Path(model_path).resolve()
        except Exception:
            resolved = Path(model_path)
        for entry in self._model_pool_entries:
            try:
                if Path(entry["model"]).resolve() == resolved:
                    return max(0, int(entry.get("motion_start_ms", 0) or 0))
            except Exception:
                continue
        return 0

    def _select_model_combo_for_path(self, model_path: Path) -> None:
        try:
            resolved = Path(model_path).resolve()
        except Exception:
            resolved = Path(model_path)
        self._model_combo_updating = True
        try:
            for index in range(self.model_combo.count()):
                data = self.model_combo.itemData(index)
                if isinstance(data, dict) and Path(data.get("model", "")).resolve() == resolved:
                    self.model_combo.setCurrentIndex(index)
                    return
            if self.model_combo.count() == 0 or self.model_combo.itemData(0) != "custom":
                self.model_combo.insertItem(0, f"Custom: {Path(model_path).name}", "custom")
            else:
                self.model_combo.setItemText(0, f"Custom: {Path(model_path).name}")
            self.model_combo.setCurrentIndex(0)
        finally:
            self._model_combo_updating = False

    def _on_model_selected(self, _index: int) -> None:
        if self._model_combo_updating:
            return
        data = self.model_combo.currentData()
        if not isinstance(data, dict):
            return
        model = Path(data["model"])
        motion = Path(data["motion"]) if data.get("motion") else None
        self._playhead_ms = max(0, int(data.get("motion_start_ms", 0) or 0))
        self.load_model(model)
        if motion is not None and motion.exists():
            self.load_vmd(motion)

    def _render_mode(self) -> str:
        return MMD_RENDER_TOON

    def _lighting_preset(self) -> str:
        return str(self.lighting_combo.currentData() or "studio_soft")

    def _preset_lighting(self) -> dict[str, Any]:
        return resolve_mmd_lighting(self._lighting_preset())

    def _load_light_controls_from_preset(self) -> None:
        preset = self._preset_lighting()
        yaw, height = self._angles_from_key_dir(preset.get("key_dir"))
        self._key_yaw_deg = float(yaw)
        self._key_height_deg = float(height)
        self._key_intensity = max(0.0, min(2.0, float(preset.get("key_intensity", 1.0) or 1.0)))
        self._fill_intensity = max(0.0, min(1.2, float(preset.get("fill_intensity", 0.32) or 0.32)))
        self._rim_intensity = max(0.0, min(1.2, float(preset.get("rim_intensity", 0.12) or 0.12)))
        self._ambient_intensity = max(0.0, min(1.0, float(preset.get("ambient_intensity", 0.40) or 0.40)))
        self._shadow_strength = max(0.0, min(1.0, float(preset.get("shadow_strength", 0.64) or 0.64)))
        self._sync_light_controls()

    def _on_lighting_preset_changed(self, _index: int) -> None:
        self._load_light_controls_from_preset()
        self._refresh_render_settings()

    def _sync_light_controls(self) -> None:
        self._lighting_controls_updating = True
        try:
            self._set_slider_silent(self.key_yaw_slider, int(round(self._key_yaw_deg)))
            self._set_slider_silent(self.key_height_slider, int(round(self._key_height_deg)))
            self._set_slider_silent(self.key_slider, int(round(self._key_intensity * 100.0)))
            self._set_slider_silent(self.fill_slider, int(round(self._fill_intensity * 100.0)))
            self._set_slider_silent(self.rim_slider, int(round(self._rim_intensity * 100.0)))
            self._set_slider_silent(self.ambient_slider, int(round(self._ambient_intensity * 100.0)))
            self._set_slider_silent(self.shadow_slider, int(round(self._shadow_strength * 100.0)))
            self._sync_light_labels()
        finally:
            self._lighting_controls_updating = False

    def _sync_light_labels(self) -> None:
        self.key_yaw_value.setText(f"{self._key_yaw_deg:+.0f}°")
        self.key_height_value.setText(f"{self._key_height_deg:.0f}°")
        self.key_value.setText(f"{self._key_intensity:.2f}")
        self.fill_value.setText(f"{self._fill_intensity:.2f}")
        self.rim_value.setText(f"{self._rim_intensity:.2f}")
        self.ambient_value.setText(f"{self._ambient_intensity:.2f}")
        self.shadow_value.setText(f"{self._shadow_strength:.2f}")

    def _light_controls_changed(self) -> None:
        self._sync_light_labels()
        if not self._lighting_controls_updating:
            self._refresh_render_settings()

    def _create_physics_backend(self) -> DecimatedPhysicsBackend:
        return DecimatedPhysicsBackend(
            create_mmd_physics_backend(
                self._physics_backend_preference,
                spring_response=self._spring_physics_response,
                secondary_rotation_scale=self._secondary_rotation_hint_scale,
            ),
            update_interval_frames=PLAYBACK_PHYSICS_INTERVAL_FRAMES,
            smoothing_response=PLAYBACK_PHYSICS_SMOOTHING_RESPONSE,
        )

    def _on_physics_backend_changed(self, _index: int) -> None:
        self._physics_backend_preference = str(self.physics_backend_combo.currentData() or "auto")
        self._physics_backend = self._create_physics_backend()
        self._last_item = None
        self._reset_pose_cache()
        self._reset_physics_state()
        self._refresh_preview()

    def _on_gpu_skinning_toggled(self, _checked: bool) -> None:
        self._last_item = None
        self._reset_pose_cache()
        self._refresh_preview()

    def load_model(self, path: str | Path) -> None:
        self._model_path = Path(path)
        self._last_item = None
        self._reset_pose_cache()
        try:
            self._model = load_mmd_model(self._model_path)
        except Exception as exc:
            self._model = None
            self.preview.set_mmd_overlay_items([])
            message = f"{type(exc).__name__}: {exc}"
            try:
                from app.actor_loading_cache import record_actor_load
                from app.actor_loading_status import actor_loading_diagnostic_card, format_actor_loading_diagnostic_card

                record_actor_load(
                    "mmd",
                    str(self._model_path),
                    status="error",
                    stage="parse",
                    message=message,
                    metadata={"source": "mmd_player.load_model"},
                )
                card = actor_loading_diagnostic_card(
                    "mmd",
                    str(self._model_path),
                    status="error",
                    stage="parse",
                    message=message,
                )
                self._status.setText(format_actor_loading_diagnostic_card(card).splitlines()[0])
            except Exception:
                self._status.setText(f"Load failed: {message}")
            self.preview.update_frame(self._base_frame, None)
            return
        self._update_status()
        self._reset_physics_state()
        self._apply_default_view()
        self._refresh_preview()

    def open_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MMD model",
            str(self._model_path.parent if self._model_path else ROOT),
            "MMD Model (*.pmx *.pmd)",
        )
        if path:
            self.load_model(path)
            self._select_model_combo_for_path(Path(path))

    def open_vmd(self) -> None:
        start_dir = self._motion_path.parent if self._motion_path else self._model_path.parent
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open VMD motion/camera",
            str(start_dir),
            "MMD VMD (*.vmd)",
        )
        if path:
            self.load_vmd(path)

    def load_vmd(self, path: str | Path) -> None:
        self._motion_path = Path(path)
        self._last_item = None
        self._reset_pose_cache()
        try:
            self._motion = load_vmd(self._motion_path)
        except Exception as exc:
            self._motion = None
            self._reset_physics_state()
            self._status.setText(f"VMD load failed: {type(exc).__name__}: {exc}")
            self._refresh_preview()
            return
        duration_ms = max(1000, int(round((max(1, self._motion.max_frame) / 30.0) * 1000.0)))
        self.time_slider.setRange(0, duration_ms)
        self._playhead_ms = min(self._playhead_ms, duration_ms)
        self._sync_time_slider()
        self._reset_physics_state()
        self._update_status()
        self._refresh_preview()

    def toggle_play(self) -> None:
        self._playing = not self._playing
        self._last_tick_time = time.perf_counter()
        self._sync_play_button()
        if not self._playing:
            self._reset_physics_state()
            self._refresh_preview()

    def stop_playback(self) -> None:
        self._playing = False
        self._playhead_ms = 0
        self._last_tick_time = time.perf_counter()
        self._reset_physics_state()
        self._sync_play_button()
        self._sync_time_slider()
        if self._motion is None and not self._manual_view_override:
            self._yaw = self._turntable_yaw(self._playhead_ms)
            self._sync_yaw_slider()
        self._refresh_preview()

    def reset_view(self) -> None:
        self._playhead_ms = 0
        self._last_tick_time = time.perf_counter()
        self._reset_physics_state()
        self._apply_default_view()
        self._roll = 0.0
        self._sync_view_controls()
        self._refresh_preview()

    def _apply_default_view(self) -> None:
        self._yaw = DEFAULT_FRONT_YAW
        self._pitch = DEFAULT_FRONT_PITCH
        self._zoom = DEFAULT_FRONT_ZOOM
        self._offset_x = DEFAULT_FRONT_OFFSET_X
        self._offset_y = DEFAULT_FRONT_OFFSET_Y
        self._manual_view_override = False
        self._view_dragging = False

    def _update_status(self) -> None:
        if self._model is None:
            self._status.setText("")
            return
        lines = [
            f"{self._model_path.name}",
            f"{self._model.vertex_count:,} verts / {self._model.triangle_count:,} tris",
            f"{len(self._model.materials)} mat / {len(self._model.textures)} tex / "
            f"{len(self._model.bones)} bones / {len(self._model.morphs)} morphs",
            f"{len(self._model.rigid_bodies)} bodies / {len(self._model.joints)} joints",
        ]
        if self._motion is not None and self._motion_path is not None:
            lines.append(
                f"{self._motion_path.name}: {self._motion.max_frame}f / "
                f"{len(self._motion.bone_frames)}B "
                f"{len(self._motion.morph_frames)}M "
                f"{len(self._motion.camera_frames)}C"
            )
        diagnostics = dict((self.latest_render_item() or {}).get("diagnostics") or {})
        if diagnostics:
            lines.append(format_mmd_performance_line(diagnostics))
        self._status.setText("\n".join(lines))

    def _set_yaw(self, value: int) -> None:
        self._yaw = float(value)
        self._manual_view_override = True
        self._refresh_preview()

    def _set_pitch(self, value: int) -> None:
        self._pitch = float(value)
        self._manual_view_override = True
        self._refresh_preview()

    def _set_zoom_percent(self, value: int) -> None:
        self._zoom = max(0.05, float(value) / 100.0)
        self._manual_view_override = True
        self._refresh_preview()

    def _set_bloom_percent(self, value: int) -> None:
        self._bloom_strength = max(0.0, min(1.5, float(value) / 100.0))
        self._sync_bloom_label()
        self._refresh_render_settings()

    def _set_cloth_motion_percent(self, value: int) -> None:
        self._secondary_rotation_hint_scale = max(0.0, min(0.30, float(value) / 100.0))
        self._sync_physics_tuning_labels()
        self._apply_physics_tuning()

    def _set_follow_response_percent(self, value: int) -> None:
        self._spring_physics_response = max(0.15, min(1.50, float(value) / 100.0))
        self._sync_physics_tuning_labels()
        self._apply_physics_tuning()

    def _set_key_yaw(self, value: int) -> None:
        self._key_yaw_deg = float(value)
        self._light_controls_changed()

    def _set_key_height(self, value: int) -> None:
        self._key_height_deg = max(5.0, min(85.0, float(value)))
        self._light_controls_changed()

    def _set_key_intensity(self, value: int) -> None:
        self._key_intensity = max(0.0, min(2.0, float(value) / 100.0))
        self._light_controls_changed()

    def _set_fill_intensity(self, value: int) -> None:
        self._fill_intensity = max(0.0, min(1.2, float(value) / 100.0))
        self._light_controls_changed()

    def _set_rim_intensity(self, value: int) -> None:
        self._rim_intensity = max(0.0, min(1.2, float(value) / 100.0))
        self._light_controls_changed()

    def _set_ambient_intensity(self, value: int) -> None:
        self._ambient_intensity = max(0.0, min(1.0, float(value) / 100.0))
        self._light_controls_changed()

    def _set_shadow_strength(self, value: int) -> None:
        self._shadow_strength = max(0.0, min(1.0, float(value) / 100.0))
        self._light_controls_changed()

    def _set_time(self, value: int) -> None:
        self._playhead_ms = int(value)
        self._last_tick_time = time.perf_counter()
        self._reset_physics_state()
        if self._motion is None and not self._manual_view_override:
            self._yaw = self._turntable_yaw(self._playhead_ms)
            self._sync_yaw_slider()
        self._refresh_preview()

    def _tick(self) -> None:
        now = time.perf_counter()
        if not self._playing:
            self._last_tick_time = now
            return
        if self._playing:
            duration = self._duration_ms()
            elapsed_ms = int(round((now - self._last_tick_time) * 1000.0))
            self._last_tick_time = now
            elapsed_ms = max(1, min(250, elapsed_ms))
            previous_playhead_ms = int(self._playhead_ms)
            self._playhead_ms = (self._playhead_ms + elapsed_ms) % duration
            if self._playhead_ms < previous_playhead_ms:
                self._reset_physics_state()
            self._sync_time_slider()
            if self._motion is None and not self._manual_view_override:
                self._yaw = self._turntable_yaw(self._playhead_ms)
                self._sync_yaw_slider()
        self._refresh_preview()

    def _frame_number(self) -> float:
        return float(self._playhead_ms) / 1000.0 * 30.0

    def _duration_ms(self) -> int:
        return max(1, int(self.time_slider.maximum()))

    def _turntable_yaw(self, playhead_ms: int) -> float:
        return DEFAULT_FRONT_YAW + (float(playhead_ms) / float(self._duration_ms())) * 360.0

    @staticmethod
    def _set_slider_silent(slider: QSlider, value: int) -> None:
        slider.blockSignals(True)
        slider.setValue(int(value))
        slider.blockSignals(False)

    def _sync_play_button(self) -> None:
        self.play_button.setIcon(app_icon("pause" if self._playing else "play"))
        self.play_button.setText("Pause" if self._playing else "Play")

    def _sync_bloom_label(self) -> None:
        self.bloom_value.setText(f"{self._bloom_strength:.2f}")

    def _sync_physics_tuning_labels(self) -> None:
        self.cloth_motion_value.setText(f"{self._secondary_rotation_hint_scale:.2f}")
        self.follow_response_value.setText(f"{self._spring_physics_response:.2f}")

    def _apply_physics_tuning(self) -> None:
        configure_mmd_physics_backend(
            self._physics_backend,
            spring_response=self._spring_physics_response,
            secondary_rotation_scale=self._secondary_rotation_hint_scale,
        )
        self._reset_physics_state()
        self._refresh_preview()

    def _sync_yaw_slider(self) -> None:
        self._set_slider_silent(self.yaw_slider, int(((self._yaw + 180.0) % 360.0) - 180.0))

    def _sync_time_slider(self) -> None:
        self._set_slider_silent(self.time_slider, int(self._playhead_ms))

    def _sync_view_controls(self) -> None:
        self._sync_yaw_slider()
        self._set_slider_silent(self.pitch_slider, int(self._pitch))
        self._set_slider_silent(self.zoom_slider, int(round(self._zoom * 100.0)))
        self._sync_time_slider()

    def _refresh_preview(self) -> None:
        if self._model is None:
            self.preview.update_frame(self._base_frame, None)
            return
        started = time.perf_counter()
        self._last_pose_eval_seconds = 0.0
        self._last_render_item_seconds = 0.0
        frame = self._frame_number()
        fast_playback = self._playing and self._motion is not None
        has_sdef = bool(np.any(np.asarray(self._model.weights.weight_types) == 3))
        gpu_fallback_reason = "sdef_cpu_skinning_required" if self.gpu_skinning_checkbox.isChecked() and has_sdef else ""
        enable_physics = bool(self._model.rigid_bodies) if fast_playback else True
        use_gpu_skinning = bool(
            self.gpu_skinning_checkbox.isChecked()
            and not has_sdef
            and self._motion is not None
        )
        gpu_morph_slots = MMD_GPU_MORPH_SLOTS if use_gpu_skinning else 0
        max_ik_iterations = self._playback_ik_iterations(fast_playback)
        frame_for_pose = float(int(round(frame))) if fast_playback else frame
        cache_key = self._pose_cache_key(
            frame_for_pose,
            enable_physics=enable_physics,
            max_ik_iterations=max_ik_iterations,
            skin_vertices=not use_gpu_skinning,
            gpu_morph_slots=gpu_morph_slots,
        )
        pose = self._cached_pose(cache_key)
        pose_cache_hit = pose is not None
        if pose is None:
            pose_started = time.perf_counter()
            pose = evaluate_model_pose(
                self._model,
                self._motion,
                frame_for_pose,
                physics_backend=self._physics_backend,
                enable_ik=True,
                enable_physics=enable_physics,
                max_ik_iterations=max_ik_iterations,
                foot_ik_reach_limit=FOOT_IK_REACH_LIMIT,
                skin_vertices=not use_gpu_skinning,
                gpu_morph_slots=gpu_morph_slots,
            )
            self._last_pose_eval_seconds = time.perf_counter() - pose_started
            self._store_pose_cache(cache_key, pose)
        pose_bounds = bounds_from_positions(pose.positions)
        camera_bounds = bounds_from_positions(pose.positions, trim_percentile=1.0)
        camera_controls = self._camera_controls_for_pose(frame, camera_bounds)
        gpu_morph_names = tuple(str(name) for name in getattr(pose, "gpu_morph_names", ()))
        gpu_morph_weights = tuple(float(weight) for weight in getattr(pose, "gpu_morph_weights", ()))
        can_reuse_gpu_geometry = bool(use_gpu_skinning and int(pose.active_morph_count) == len(gpu_morph_names))
        if can_reuse_gpu_geometry and self._last_item is not None and bool(self._last_item.get("gpu_skinning")):
            if (
                str(self._last_item.get("path") or "") == str(self._model.path)
                and tuple(str(name) for name in (self._last_item.get("gpu_morph_names") or ())) == gpu_morph_names
            ):
                item = dict(self._last_item)
                item["bounds"] = pose_bounds
                item["bone_matrices"] = pose.bone_matrices
                item["gpu_morph_weights"] = gpu_morph_weights
                item["yaw"] = float(camera_controls.get("yaw", self._yaw))
                item["pitch"] = float(camera_controls.get("pitch", self._pitch))
                item["roll"] = float(camera_controls.get("roll", self._roll))
                item["zoom"] = max(0.05, float(camera_controls.get("zoom", self._zoom)))
                item["offset_x"] = float(camera_controls.get("offset_x", self._offset_x))
                item["offset_y"] = float(camera_controls.get("offset_y", self._offset_y))
                diagnostics = dict(item.get("diagnostics") or {})
                diagnostics.update(
                    {
                        "skinned": bool(pose.skinned),
                        "gpu_skinning": True,
                        "gpu_skinning_requested": bool(self.gpu_skinning_checkbox.isChecked()),
                        "gpu_skinning_fallback_reason": gpu_fallback_reason,
                        "sdef_cpu_skinning_required": bool(has_sdef),
                        "gpu_static_geometry_reused": True,
                        "bone_matrix_count": int(pose.bone_matrices.shape[0]) if pose.bone_matrices is not None else 0,
                        "active_bone_count": int(pose.active_bone_count),
                        "active_morph_count": int(pose.active_morph_count),
                        "gpu_morph_slot_count": int(len(gpu_morph_names)),
                        "gpu_morph_active_count": int(len(gpu_morph_names)),
                        "active_ik_count": int(pose.active_ik_count),
                        "physics_body_count": int(pose.physics_body_count),
                        "active_sdef_count": int(pose.active_sdef_count),
                        "pose_cache_hit": bool(pose_cache_hit),
                        "pose_cache_physics_generation": int(self._physics_generation),
                        "physics_pose_cache_enabled": bool(enable_physics),
                        "adaptive_ik_iterations": int(max_ik_iterations),
                        "physics_decimated": bool(enable_physics and fast_playback),
                        "physics_cpu_skinning_fallback": bool(enable_physics and fast_playback and not use_gpu_skinning),
                        "gpu_physics_bone_matrices": bool(enable_physics and fast_playback and use_gpu_skinning),
                        **mmd_physics_backend_diagnostics(self._physics_backend),
                        "physics_backend_requested": str(self._physics_backend_preference),
                        "physics_rotation_hint_scale": float(self._secondary_rotation_hint_scale),
                        "physics_spring_response": float(self._spring_physics_response),
                        "auto_framing": bool(camera_controls and camera_at(self._motion, frame) is None),
                        "auto_frame_zoom": float(item["zoom"]),
                    }
                )
                item["diagnostics"] = diagnostics
                self._last_item = item
                self.preview.set_mmd_overlay_items([item])
                self.preview.update_frame(self._base_frame, None)
                self._record_refresh_duration(time.perf_counter() - started, fast_playback)
                return
        build_started = time.perf_counter()
        self._last_item = build_mmd_render_item(
            self._model,
            render_mode=self._render_mode(),
            yaw=self._yaw,
            pitch=self._pitch,
            roll=self._roll,
            zoom=self._zoom,
            lighting_preset=self._lighting_preset(),
            lighting=self._current_lighting(),
            bloom_strength=self._bloom_strength,
            pose_geometry=pose,
            camera_controls=camera_controls,
        )
        self._last_render_item_seconds = time.perf_counter() - build_started
        diagnostics = dict(self._last_item.get("diagnostics") or {})
        diagnostics.update(
            {
                "pose_cache_hit": bool(pose_cache_hit),
                "gpu_skinning_requested": bool(self.gpu_skinning_checkbox.isChecked()),
                "gpu_skinning_fallback_reason": gpu_fallback_reason,
                "sdef_cpu_skinning_required": bool(has_sdef),
                "pose_cache_physics_generation": int(self._physics_generation),
                "physics_pose_cache_enabled": bool(enable_physics),
                "adaptive_ik_iterations": int(max_ik_iterations),
                "physics_decimated": bool(enable_physics and fast_playback),
                "physics_cpu_skinning_fallback": bool(enable_physics and fast_playback and not use_gpu_skinning),
                "gpu_physics_bone_matrices": bool(enable_physics and fast_playback and use_gpu_skinning),
                **mmd_physics_backend_diagnostics(self._physics_backend),
                "physics_backend_requested": str(self._physics_backend_preference),
                "physics_rotation_hint_scale": float(self._secondary_rotation_hint_scale),
                "physics_spring_response": float(self._spring_physics_response),
                "gpu_static_geometry_reused": False,
                "gpu_morph_slot_count": int(len(gpu_morph_names)),
                "gpu_morph_active_count": int(len(gpu_morph_names)),
                "auto_framing": bool(camera_controls and camera_at(self._motion, frame) is None),
                "auto_frame_zoom": float(self._last_item.get("zoom", self._zoom) or self._zoom),
            }
        )
        self._last_item["diagnostics"] = diagnostics
        self.preview.set_mmd_overlay_items([self._last_item])
        self.preview.update_frame(self._base_frame, None)
        self._record_refresh_duration(time.perf_counter() - started, fast_playback)

    def _current_lighting(self) -> dict[str, Any]:
        bloom_strength = max(0.0, min(2.0, float(self._bloom_strength)))
        return resolve_mmd_lighting(
            self._lighting_preset(),
            {
                "key_dir": self._key_dir_from_angles(self._key_yaw_deg, self._key_height_deg),
                "key_intensity": max(0.0, min(2.0, float(self._key_intensity))),
                "fill_intensity": max(0.0, min(1.2, float(self._fill_intensity))),
                "rim_intensity": max(0.0, min(1.2, float(self._rim_intensity))),
                "ambient_intensity": max(0.0, min(1.0, float(self._ambient_intensity))),
                "shadow_strength": max(0.0, min(1.0, float(self._shadow_strength))),
                "bloom_enabled": bloom_strength > 0.001,
                "bloom_strength": bloom_strength,
            },
        )

    def _refresh_render_settings(self) -> None:
        if self._last_item is None:
            self._refresh_preview()
            return
        item = dict(self._last_item)
        lighting = self._current_lighting()
        item["lighting"] = lighting
        item["light_dir"] = tuple(float(v) for v in lighting.get("key_dir") or (0.42, -0.76, -0.48))
        diagnostics = dict(item.get("diagnostics") or {})
        diagnostics.update(
            {
                "lighting_preset": str(lighting.get("preset") or self._lighting_preset()),
                "bloom_enabled": bool(lighting.get("bloom_enabled", True)),
                "bloom_strength": float(lighting.get("bloom_strength", self._bloom_strength) or 0.0),
            }
        )
        item["diagnostics"] = diagnostics
        self._last_item = item
        self.preview.set_mmd_overlay_items([item])
        self.preview.update_frame(self._base_frame, None)

    def _refresh_view_transform(self) -> None:
        if self._last_item is None:
            self._refresh_preview()
            return
        item = dict(self._last_item)
        item.update(
            {
                "yaw": float(self._yaw),
                "pitch": float(self._pitch),
                "roll": float(self._roll),
                "zoom": max(0.05, float(self._zoom)),
                "offset_x": float(self._offset_x),
                "offset_y": float(self._offset_y),
            }
        )
        self._last_item = item
        self.preview.set_mmd_overlay_items([item])
        self.preview.update_frame(self._base_frame, None)
