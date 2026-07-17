"""Owner-only render window for the Action Sequencer bridge."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size, unreal_engine_icon
from app.action_sequencer_ar_pbr_proxy import (
    default_owner_ar_pbr_proxy_path,
    write_owner_ar_pbr_proxy_asset,
)
from app.unreal_link_reference_paths import unreal_link_reference_roots


ACTION_SEQUENCER_PROJECT_ENV = "TIGERSTUDIO_ACTION_SEQUENCER_PROJECT"
DEFAULT_ACTION_SEQUENCER_PROJECT = Path("E:/ue5example/ActionSequencer/ActionSequencer.uproject")


@dataclass(frozen=True)
class OwnerRenderDescriptor:
    project_path: Path
    owner_name: str
    owner_asset_path: Path | None
    owner_class_name: str
    render_asset_path: Path | None
    animation_blueprint_path: Path | None
    idle_animation_path: Path | None
    action_candidate_path: Path | None
    stage_position: tuple[float, float, float] = (-120.0, 0.0, 0.0)
    stage_forward: str = "+X / screen right"
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def can_render(self) -> bool:
        return self.render_asset_path is not None and self.render_asset_path.exists()

    def summary_rows(self) -> list[tuple[str, str]]:
        return [
            ("Project", _display_path(self.project_path)),
            ("Owner", self.owner_name),
            ("Owner class", self.owner_class_name),
            ("Owner asset", _display_path(self.owner_asset_path)),
            ("Render mesh", _display_path(self.render_asset_path)),
            ("Idle pose", _display_path(self.idle_animation_path)),
            ("Action candidate", _display_path(self.action_candidate_path)),
            ("Stage", f"left {self.stage_position}, facing {self.stage_forward}"),
        ]

    def to_result(self) -> dict[str, Any]:
        return {
            "project_path": str(self.project_path),
            "owner_name": self.owner_name,
            "owner_asset_path": str(self.owner_asset_path) if self.owner_asset_path else None,
            "owner_class_name": self.owner_class_name,
            "render_asset_path": str(self.render_asset_path) if self.render_asset_path else None,
            "animation_blueprint_path": str(self.animation_blueprint_path) if self.animation_blueprint_path else None,
            "idle_animation_path": str(self.idle_animation_path) if self.idle_animation_path else None,
            "action_candidate_path": str(self.action_candidate_path) if self.action_candidate_path else None,
            "stage_position": list(self.stage_position),
            "stage_forward": self.stage_forward,
            "diagnostics": list(self.diagnostics),
            "can_render": self.can_render,
        }


def default_action_sequencer_project_path() -> Path:
    configured = os.environ.get(ACTION_SEQUENCER_PROJECT_ENV, "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_ACTION_SEQUENCER_PROJECT


def discover_owner_render_descriptor(project_path: Path | str | None = None) -> OwnerRenderDescriptor:
    project = Path(project_path) if project_path is not None else default_action_sequencer_project_path()
    diagnostics: list[str] = []
    content_root = project.parent / "Content"
    if not project.exists():
        diagnostics.append(f"Project file not found: {project}")
    if not content_root.exists():
        diagnostics.append(f"Content folder not found: {content_root}")

    owner_asset = _first_existing(
        content_root / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset",
        *_safe_rglob(content_root, "BP_CombatCharacter.uasset"),
    )
    if owner_asset is None:
        diagnostics.append("BP_CombatCharacter was not found; falling back to mesh-only owner preview.")

    render_asset = _first_existing(
        content_root / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset",
        content_root / "Characters" / "Mannequins" / "Meshes" / "SK_Mannequin.uasset",
        *_safe_rglob(content_root / "Characters" / "Mannequins" / "Meshes", "SK*.uasset"),
    )
    if render_asset is None:
        diagnostics.append("No mannequin skeletal mesh was found for Owner rendering.")

    anim_bp = _first_existing(
        content_root / "Variant_Combat" / "Anims" / "ABP_Manny_Combat.uasset",
        content_root / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "ABP_Unarmed.uasset",
    )
    idle_anim = _first_existing(
        content_root / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset",
    )
    action_candidate = _first_existing(
        content_root / "Variant_Combat" / "Anims" / "AM_ComboAttack.uasset",
        content_root / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "Attack" / "MM_Attack_01.uasset",
    )

    references = unreal_link_reference_roots()
    inspector_root = references["uasset_inspector"]
    if not inspector_root.exists or inspector_root.missing_children:
        diagnostics.append("UAssetInspector reference root is missing or incomplete.")
    engine_root = references["ue_58"]
    if not engine_root.exists or engine_root.missing_children:
        diagnostics.append("UE 5.8 reference root is missing or incomplete.")

    return OwnerRenderDescriptor(
        project_path=project,
        owner_name="BP_CombatCharacter",
        owner_asset_path=owner_asset,
        owner_class_name="ACombatCharacter",
        render_asset_path=render_asset,
        animation_blueprint_path=anim_bp,
        idle_animation_path=idle_anim,
        action_candidate_path=action_candidate,
        diagnostics=tuple(diagnostics),
    )


def default_owner_render_capture_path(descriptor: OwnerRenderDescriptor) -> Path:
    root = Path(__file__).resolve().parents[1] / "debugCapture"
    project_stem = descriptor.project_path.stem or "ActionSequencer"
    owner = descriptor.owner_name or "Owner"
    return root / f"action_sequencer_{project_stem}_{owner}_owner_render.png"


def uasset_inspector_executable() -> Path:
    root = unreal_link_reference_roots()["uasset_inspector"].path
    return root / "src" / "UAssetInspector.App" / "bin" / "Debug" / "net8.0-windows" / "UAssetInspector.App.exe"


def render_owner_preview_frame(
    descriptor: OwnerRenderDescriptor,
    output_path: Path | str | None = None,
    *,
    timeout_s: float = 18.0,
) -> Path:
    if descriptor.render_asset_path is None:
        raise RuntimeError("Owner render mesh is not available.")
    asset_path = descriptor.render_asset_path
    if not asset_path.exists():
        raise RuntimeError(f"Owner render mesh does not exist: {asset_path}")

    exe = uasset_inspector_executable()
    if not exe.exists():
        raise RuntimeError(f"UAssetInspector executable was not found: {exe}")

    target = Path(output_path) if output_path is not None else default_owner_render_capture_path(descriptor)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.unlink()
    except FileNotFoundError:
        pass

    env = os.environ.copy()
    env["UASSETINSPECTOR_CAPTURE_FRAME"] = str(target)

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    process = subprocess.Popen(
        [str(exe), "--file", str(asset_path)],
        cwd=str(exe.parent),
        env=env,
        startupinfo=startupinfo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + max(2.0, float(timeout_s))
    try:
        while time.monotonic() < deadline:
            if target.exists() and target.stat().st_size > 0:
                return target
            if process.poll() is not None:
                break
            time.sleep(0.25)
        raise RuntimeError(f"Owner render capture was not produced: {target}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()


def open_uasset_inspector_for_owner(descriptor: OwnerRenderDescriptor) -> None:
    if descriptor.render_asset_path is None:
        raise RuntimeError("Owner render mesh is not available.")
    exe = uasset_inspector_executable()
    if not exe.exists():
        raise RuntimeError(f"UAssetInspector executable was not found: {exe}")
    subprocess.Popen(
        [str(exe), "--file", str(descriptor.render_asset_path)],
        cwd=str(exe.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class _OwnerRenderWorker(QThread):
    rendered = Signal(str)
    failed = Signal(str)

    def __init__(self, descriptor: OwnerRenderDescriptor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._descriptor = descriptor

    def run(self) -> None:
        try:
            path = render_owner_preview_frame(self._descriptor)
        except Exception as exc:  # pragma: no cover - exercised through UI smoke/manual QA
            self.failed.emit(str(exc))
            return
        self.rendered.emit(str(path))


class _OwnerRenderCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._message = "Rendering Owner..."
        self.setMinimumSize(680, 430)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_render(self, path: Path | str) -> None:
        pixmap = QPixmap(str(path))
        self._pixmap = pixmap if not pixmap.isNull() else QPixmap()
        self._message = "" if not self._pixmap.isNull() else "Render image could not be loaded."
        self.update()

    def set_message(self, message: str) -> None:
        self._message = message
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg.setColorAt(0.0, QColor("#0B0F16"))
        bg.setColorAt(0.55, QColor("#121923"))
        bg.setColorAt(1.0, QColor("#080A0E"))
        painter.fillRect(rect, bg)

        painter.setPen(QPen(QColor(255, 255, 255, 16), 1))
        horizon = rect.height() * 0.66
        for i in range(15):
            y = horizon + i * rect.height() * 0.035
            painter.drawLine(QPointF(0, y), QPointF(rect.width(), y))
        for i in range(-8, 16):
            x = rect.width() * 0.18 + i * rect.width() * 0.065
            painter.drawLine(QPointF(x, horizon), QPointF(x + rect.width() * 0.20, rect.height()))

        owner_x = rect.width() * 0.22
        owner_y = rect.height() * 0.81
        painter.setPen(QPen(QColor("#72F7A7"), 2))
        painter.drawLine(QPointF(owner_x, owner_y - 60), QPointF(owner_x, owner_y + 22))
        painter.drawEllipse(QPointF(owner_x, owner_y), 9, 9)
        painter.drawLine(QPointF(owner_x + 16, owner_y - 42), QPointF(owner_x + 120, owner_y - 42))
        painter.drawLine(QPointF(owner_x + 120, owner_y - 42), QPointF(owner_x + 102, owner_y - 52))
        painter.drawLine(QPointF(owner_x + 120, owner_y - 42), QPointF(owner_x + 102, owner_y - 32))
        painter.setFont(_font(10, bold=True))
        painter.drawText(QRectF(owner_x - 52, owner_y + 18, 150, 24), Qt.AlignmentFlag.AlignLeft, "OWNER LEFT")

        if not self._pixmap.isNull():
            max_w = rect.width() * 0.74
            max_h = rect.height() * 0.78
            scale = min(max_w / self._pixmap.width(), max_h / self._pixmap.height())
            draw_w = self._pixmap.width() * scale
            draw_h = self._pixmap.height() * scale
            x = rect.width() * 0.11
            y = (rect.height() - draw_h) * 0.43
            image_rect = QRectF(x, y, draw_w, draw_h)
            painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
            painter.drawRoundedRect(image_rect.adjusted(-8, -8, 8, 8), 8, 8)
            painter.drawPixmap(image_rect, self._pixmap, QRectF(self._pixmap.rect()))
        else:
            painter.setFont(_font(17, bold=True))
            painter.setPen(QColor("#EEF4FF"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._message)

        painter.setFont(_font(10))
        painter.setPen(QColor("#A8B2C1"))
        painter.drawText(
            QRectF(18, 16, rect.width() - 36, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Owner-only render pass - no sequence menu, no target actor",
        )
        painter.end()


class ActionSequencerOwnerRenderWindow(QWidget):
    def __init__(self, project_path: Path | str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.descriptor = discover_owner_render_descriptor(project_path)
        self._worker: _OwnerRenderWorker | None = None
        self.setWindowTitle("Action Sequencer - Owner Render")
        self.resize(1160, 720)
        self.setObjectName("ActionSequencerOwnerRenderWindow")
        self.setStyleSheet(_window_qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("ACTION SEQUENCER / OWNER RENDER", self)
        title.setObjectName("OwnerRenderTitle")
        header.addWidget(title, stretch=1)
        self._render_btn = QPushButton("Render Owner", self)
        self._render_btn.setIcon(app_icon("play", size=13))
        self._render_btn.setIconSize(icon_size(13))
        self._render_btn.clicked.connect(self.render_owner)
        header.addWidget(self._render_btn)
        self._inspector_btn = QPushButton("Open Inspector", self)
        self._inspector_btn.setIcon(unreal_engine_icon(14))
        self._inspector_btn.setIconSize(icon_size(14))
        self._inspector_btn.clicked.connect(self._open_inspector)
        header.addWidget(self._inspector_btn)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(10)
        self._canvas = _OwnerRenderCanvas(self)
        body.addWidget(self._canvas, stretch=1)
        body.addWidget(self._build_side_panel(), stretch=0)
        root.addLayout(body, stretch=1)

        self._status = QLabel("Ready.", self)
        self._status.setObjectName("OwnerRenderStatus")
        root.addWidget(self._status)

        QTimer.singleShot(120, self.render_owner)

    def render_owner(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not self.descriptor.can_render:
            self._status.setText("Owner mesh is not available. Check the connected project path.")
            self._canvas.set_message("Owner mesh was not found.")
            return
        self._render_btn.setEnabled(False)
        self._canvas.set_message("Rendering Owner...")
        self._status.setText("Rendering BP_CombatCharacter owner mesh with UAssetInspector...")
        worker = _OwnerRenderWorker(self.descriptor, self)
        worker.rendered.connect(self._on_rendered)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self._render_btn.setEnabled(True))
        self._worker = worker
        worker.start()

    def _on_rendered(self, path: str) -> None:
        self._canvas.set_render(path)
        self._status.setText(f"Rendered Owner preview: {path}")

    def _on_failed(self, message: str) -> None:
        self._canvas.set_message("Owner render failed.")
        self._status.setText(message)

    def _open_inspector(self) -> None:
        try:
            open_uasset_inspector_for_owner(self.descriptor)
            self._status.setText("Opened UAssetInspector on the Owner render mesh.")
        except Exception as exc:
            self._status.setText(str(exc))

    def _build_side_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("OwnerRenderSidePanel")
        panel.setFixedWidth(345)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        heading = QLabel("Owner Target", panel)
        heading.setObjectName("OwnerRenderSideHeading")
        layout.addWidget(heading)

        for label, value in self.descriptor.summary_rows():
            layout.addWidget(_info_row(panel, label, value))

        if self.descriptor.diagnostics:
            diag = QLabel("\n".join(f"- {item}" for item in self.descriptor.diagnostics), panel)
            diag.setObjectName("OwnerRenderDiagnostics")
            diag.setWordWrap(True)
            layout.addWidget(diag)

        layout.addStretch(1)
        return panel


def open_action_sequencer_owner_render_window(owner: object, project_path: Path | str | None = None) -> QWidget:
    descriptor = discover_owner_render_descriptor(project_path)
    proxy_asset = write_owner_ar_pbr_proxy_asset(descriptor)
    from app.ar_pbr.preview_window import ArPbrAssetPreviewWindow
    from app.ar_pbr.render_profile import PROFILE_MARMOSET_PBR

    window = ArPbrAssetPreviewWindow(
        proxy_asset,
        parent=None,
        initial_lighting={
            "render_profile": PROFILE_MARMOSET_PBR,
            "hdri_id": "studio_small_09",
            "show_environment_background": True,
            "ibl_exposure": 1.35,
            "ibl_rotation": 0.08,
            "light_azimuth": 38.0,
            "light_elevation": 48.0,
            "direct_strength": 0.62,
            "shadow_strength": 0.78,
            "shadow_pcf_radius": 1.8,
            "self_shadow_strength": 0.58,
            "ground_height": -0.52,
            "shadow_catcher_opacity": 0.68,
            "reflection_catcher_opacity": 0.16,
            "surface_override_strength": 0.18,
            "surface_roughness": 0.36,
            "surface_reflectance": 0.62,
            "tone_mapping": "aces",
            "tone_exposure": 0.10,
            "tone_white_balance": 6800.0,
            "ambient_occlusion_mode": "screen",
            "ao_strength": 0.55,
        },
        track_label=f"{descriptor.owner_name} Owner",
        max_triangles=180_000,
        texture_max_size=1024,
    )
    window.setWindowTitle("Action Sequencer - CombatCharacter AR/PBR Owner")
    setattr(window, "owner_render_descriptor", descriptor)
    setattr(window, "owner_ar_pbr_proxy_asset", proxy_asset)
    setattr(owner, "_action_sequencer_owner_render_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def _safe_rglob(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    try:
        return sorted(root.rglob(pattern))
    except OSError:
        return []


def _first_existing(*paths: Path | None) -> Path | None:
    for path in paths:
        if path is not None and path.exists():
            return path
    return None


def _display_path(path: Path | None) -> str:
    if path is None:
        return "not found"
    return path.as_posix()


def _font(size: int, *, bold: bool = False) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def _info_row(parent: QWidget, label: str, value: str) -> QWidget:
    row = QFrame(parent)
    row.setObjectName("OwnerRenderInfoRow")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(2)
    key = QLabel(label, row)
    key.setObjectName("OwnerRenderInfoKey")
    val = QLabel(value, row)
    val.setObjectName("OwnerRenderInfoValue")
    val.setWordWrap(True)
    layout.addWidget(key)
    layout.addWidget(val)
    return row


def _window_qss() -> str:
    return """
    QWidget#ActionSequencerOwnerRenderWindow {
        background: #090C11;
        color: #EAF0FA;
    }
    QLabel#OwnerRenderTitle {
        color: #F2F7FF;
        font-size: 13px;
        font-weight: 820;
        letter-spacing: 2px;
    }
    QLabel#OwnerRenderStatus {
        color: #9FAAB8;
        font-size: 10px;
        padding: 4px 2px;
    }
    QPushButton {
        color: #EAF0FA;
        background: #151A22;
        border: 1px solid #2D3542;
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 10px;
        font-weight: 720;
    }
    QPushButton:hover {
        background: #202837;
        border-color: #5B6A7E;
    }
    QPushButton:disabled {
        color: #687180;
        background: #10141A;
        border-color: #202631;
    }
    QFrame#OwnerRenderSidePanel {
        background: #10141B;
        border: 1px solid #28303B;
        border-radius: 8px;
    }
    QLabel#OwnerRenderSideHeading {
        color: #72F7A7;
        font-size: 12px;
        font-weight: 840;
        letter-spacing: 1px;
    }
    QFrame#OwnerRenderInfoRow {
        background: #0C1016;
        border: 1px solid #222A35;
        border-radius: 5px;
    }
    QLabel#OwnerRenderInfoKey {
        color: #7F8A99;
        font-size: 9px;
        font-weight: 760;
        text-transform: uppercase;
    }
    QLabel#OwnerRenderInfoValue {
        color: #D8E0EC;
        font-size: 10px;
    }
    QLabel#OwnerRenderDiagnostics {
        color: #E5B45D;
        background: #19150B;
        border: 1px solid #463C22;
        border-radius: 5px;
        padding: 8px;
        font-size: 10px;
    }
    """


__all__ = [
    "ACTION_SEQUENCER_PROJECT_ENV",
    "DEFAULT_ACTION_SEQUENCER_PROJECT",
    "ActionSequencerOwnerRenderWindow",
    "OwnerRenderDescriptor",
    "default_action_sequencer_project_path",
    "default_owner_ar_pbr_proxy_path",
    "default_owner_render_capture_path",
    "discover_owner_render_descriptor",
    "open_action_sequencer_owner_render_window",
    "open_uasset_inspector_for_owner",
    "render_owner_preview_frame",
    "uasset_inspector_executable",
    "write_owner_ar_pbr_proxy_asset",
]
