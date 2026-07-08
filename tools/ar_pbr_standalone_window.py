"""Standalone AR/PBR render preview window."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ar_pbr.compositor import composite_preview_frame
from app.ar_pbr.importer import import_asset
from app.ar_pbr.sample_scene import write_pbr_fbx_scene
from app.ar_pbr.sample_assets import default_ar_pbr_preview_asset


DEFAULT_EXTERNAL_ASSET = default_ar_pbr_preview_asset()
DEFAULT_OUTPUT_DIR = ROOT / "debugCapture" / "ar_pbr_standalone_window"
DEFAULT_MAX_TRIANGLES_PER_GEOMETRY = 48000


@dataclass
class RenderState:
    pitch: float = -18.0
    yaw: float = 90.0
    roll: float = 0.0
    zoom: float = 1.35
    camera_z: float = 3.0


def _base_frame(width: int, height: int) -> np.ndarray:
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.clip(20 + 38 * (1 - y), 0, 255).astype(np.uint8)
    frame[:, :, 1] = np.clip(26 + 50 * (1 - y), 0, 255).astype(np.uint8)
    frame[:, :, 2] = np.clip(34 + 70 * (1 - y) + 14 * x, 0, 255).astype(np.uint8)
    road_start = int(height * 0.58)
    frame[road_start:, :, :] = np.array([38, 39, 36], dtype=np.uint8)
    return frame


def _depth_frame(width: int, height: int) -> np.ndarray:
    y = np.linspace(0.25, 1.0, height, dtype=np.float32)[:, None]
    return np.repeat(y, width, axis=1)


def _resolve_asset(asset_arg: str) -> Path:
    if asset_arg:
        return Path(asset_arg)
    if DEFAULT_EXTERNAL_ASSET.exists():
        return DEFAULT_EXTERNAL_ASSET
    return DEFAULT_OUTPUT_DIR / "generated_pbr_scene.fbx"


def _render_frame(
    asset_path: Path,
    descriptor: dict,
    import_diag: dict,
    *,
    width: int,
    height: int,
    state: RenderState,
) -> tuple[np.ndarray, dict]:
    scale = max(0.05, float(state.zoom))
    frame, render_diag = composite_preview_frame(
        _base_frame(width, height),
        time_ms=0,
        ar_tracks=[
            {
                "id": "standalone_render",
                "asset_path": str(asset_path),
                "start_ms": 0,
                "end_ms": 1000,
                "transform": {
                    "position": [0.0, -0.08, 0.0],
                    "rotation": [state.pitch, state.yaw, state.roll],
                    "scale": [scale, scale, scale],
                },
                "occlusion": False,
                "shadow_catcher": True,
                "reflection_catcher": True,
            }
        ],
        camera_solution={
            "id": "standalone_cam",
            "frame_size": [width, height],
            "intrinsics": {
                "fx": float(width) * 0.92,
                "fy": float(width) * 0.92,
                "cx": float(width) * 0.5,
                "cy": float(height) * 0.54,
            },
        },
        depth_frame=_depth_frame(width, height),
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {str(asset_path): descriptor},
            "light_direction": [-0.35, -0.85, -0.4],
            "camera_z": state.camera_z,
            "shadow_blur": 4.0,
            "preserve_scene_layout": True,
        },
    )
    payload = {
        "asset": str(asset_path),
        "image": str(DEFAULT_OUTPUT_DIR / "render_window.png"),
        "controls": {
            "pitch": state.pitch,
            "yaw": state.yaw,
            "roll": state.roll,
            "zoom": state.zoom,
            "camera_z": state.camera_z,
        },
        "import": import_diag,
        "render": render_diag,
    }
    return frame, payload


def render_scene(
    asset_path: Path,
    *,
    width: int,
    height: int,
    generated: bool,
    state: RenderState | None = None,
) -> tuple[Path, Path, dict]:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if generated or not asset_path.exists():
        asset_path = write_pbr_fbx_scene(asset_path)

    descriptor, import_diag = import_asset(
        asset_path,
        settings={"max_triangles_per_geometry": DEFAULT_MAX_TRIANGLES_PER_GEOMETRY},
    )
    frame, payload = _render_frame(
        asset_path,
        descriptor,
        import_diag,
        width=width,
        height=height,
        state=state or RenderState(),
    )

    image_path = DEFAULT_OUTPUT_DIR / "render_window.png"
    diag_path = DEFAULT_OUTPUT_DIR / "render_window.json"
    Image.fromarray(frame).save(image_path)
    diag_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return image_path, diag_path, payload


class RenderImage(QLabel):
    def __init__(self, parent_window: "RenderWindow") -> None:
        super().__init__()
        self.parent_window = parent_window
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 420)
        self.setMouseTracking(True)
        self._last_pos = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.position()
            delta = pos - self._last_pos
            self.parent_window.adjust_rotation(float(delta.y()) * 0.35, float(delta.x()) * 0.35)
            self._last_pos = pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y() / 120.0
        self.parent_window.adjust_zoom(steps * 0.12)
        event.accept()


class RenderWindow(QMainWindow):
    def __init__(
        self,
        asset_path: Path,
        descriptor: dict,
        import_diag: dict,
        *,
        width: int,
        height: int,
        state: RenderState | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("AR/PBR Standalone Render")
        self.resize(1180, 720)
        self.asset_path = asset_path
        self.descriptor = descriptor
        self.import_diag = import_diag
        self.render_width = int(width)
        self.render_height = int(height)
        self.state = state or RenderState()
        self.image_path = DEFAULT_OUTPUT_DIR / "render_window.png"
        self.diag_path = DEFAULT_OUTPUT_DIR / "render_window.json"
        self._syncing_controls = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self.render_now)

        self.image = RenderImage(self)

        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumWidth(360)

        self.pitch_slider = self._angle_slider()
        self.yaw_slider = self._angle_slider()
        self.roll_slider = self._angle_slider()
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(0.1, 8.0)
        self.zoom_spin.setSingleStep(0.1)
        self.zoom_spin.setDecimals(2)
        self.camera_z_spin = QDoubleSpinBox()
        self.camera_z_spin.setRange(0.2, 12.0)
        self.camera_z_spin.setSingleStep(0.1)
        self.camera_z_spin.setDecimals(2)

        self.pitch_slider.valueChanged.connect(lambda value: self.set_pitch(float(value)))
        self.yaw_slider.valueChanged.connect(lambda value: self.set_yaw(float(value)))
        self.roll_slider.valueChanged.connect(lambda value: self.set_roll(float(value)))
        self.zoom_spin.valueChanged.connect(lambda value: self.set_zoom(float(value)))
        self.camera_z_spin.valueChanged.connect(lambda value: self.set_camera_z(float(value)))

        controls = QGroupBox("Controls")
        form = QFormLayout(controls)
        form.addRow("Pitch", self.pitch_slider)
        form.addRow("Yaw", self.yaw_slider)
        form.addRow("Roll", self.roll_slider)
        form.addRow("Zoom", self.zoom_spin)
        form.addRow("Camera Z", self.camera_z_spin)

        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset_controls)
        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        form.addRow(buttons)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(QLabel(f"Asset: {asset_path}"))
        left_layout.addWidget(self.image, stretch=1)
        left_layout.addWidget(controls)
        left_layout.addWidget(QLabel(f"Image: {self.image_path}"))
        left_layout.addWidget(QLabel(f"Diagnostics: {self.diag_path}"))

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.info)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.sync_controls()
        self.render_now()

    def _angle_slider(self) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-180, 180)
        slider.setSingleStep(1)
        slider.setPageStep(15)
        return slider

    def sync_controls(self) -> None:
        self._syncing_controls = True
        self.pitch_slider.setValue(int(round(self.state.pitch)))
        self.yaw_slider.setValue(int(round(self.state.yaw)))
        self.roll_slider.setValue(int(round(self.state.roll)))
        self.zoom_spin.setValue(float(self.state.zoom))
        self.camera_z_spin.setValue(float(self.state.camera_z))
        self._syncing_controls = False

    def schedule_render(self) -> None:
        if not self._syncing_controls:
            self._render_timer.start(20)

    def set_pitch(self, value: float) -> None:
        self.state.pitch = value
        self.schedule_render()

    def set_yaw(self, value: float) -> None:
        self.state.yaw = value
        self.schedule_render()

    def set_roll(self, value: float) -> None:
        self.state.roll = value
        self.schedule_render()

    def set_zoom(self, value: float) -> None:
        self.state.zoom = max(0.1, min(8.0, value))
        self.schedule_render()

    def set_camera_z(self, value: float) -> None:
        self.state.camera_z = max(0.2, min(12.0, value))
        self.schedule_render()

    def adjust_rotation(self, pitch_delta: float, yaw_delta: float) -> None:
        self.state.pitch = max(-180.0, min(180.0, self.state.pitch + pitch_delta))
        self.state.yaw = max(-180.0, min(180.0, self.state.yaw + yaw_delta))
        self.sync_controls()
        self.schedule_render()

    def adjust_zoom(self, delta: float) -> None:
        self.state.zoom = max(0.1, min(8.0, self.state.zoom + delta))
        self.sync_controls()
        self.schedule_render()

    def reset_controls(self) -> None:
        self.state = RenderState()
        self.sync_controls()
        self.schedule_render()

    def render_now(self) -> None:
        frame, diagnostics = _render_frame(
            self.asset_path,
            self.descriptor,
            self.import_diag,
            width=self.render_width,
            height=self.render_height,
            state=self.state,
        )
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        Image.fromarray(frame).save(self.image_path)
        self.diag_path.write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        qimage = QImage(
            frame.data,
            frame.shape[1],
            frame.shape[0],
            int(frame.strides[0]),
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(qimage).scaled(
            self.image.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image.setPixmap(pixmap)
        self.info.setPlainText(json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="", help="FBX asset path. Defaults to copied desktop es_fbx/es.fbx when present.")
    parser.add_argument("--generated", action="store_true", help="Use generated local PBR-ish ASCII FBX scene.")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--max-triangles", type=int, default=DEFAULT_MAX_TRIANGLES_PER_GEOMETRY)
    parser.add_argument("--render-only", action="store_true", help="Render once and exit without opening the Qt window.")
    args = parser.parse_args()

    asset = DEFAULT_OUTPUT_DIR / "generated_pbr_scene.fbx" if args.generated else _resolve_asset(args.asset)
    if args.generated or not asset.exists():
        asset = write_pbr_fbx_scene(asset)
    descriptor, import_diag = import_asset(
        asset,
        settings={"max_triangles_per_geometry": max(100, int(args.max_triangles))},
    )
    if args.render_only:
        render_scene(asset, width=args.width, height=args.height, generated=False)
        return 0
    app = QApplication(sys.argv)
    window = RenderWindow(
        asset,
        descriptor,
        import_diag,
        width=args.width,
        height=args.height,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
