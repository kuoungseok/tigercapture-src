"""Qt window for the AR/PBR image texture-map lab."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import importlib
import math
import os
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any

from PySide6.QtCore import QElapsedTimer, QProcess, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import editor_scrollbar_qss, studio_chrome_qss
from app.ar_pbr.texture_map_lab import (
    DEFAULT_SEPARATE_MAPS,
    PACKED_LAYOUTS,
    PREVIEW_MODES,
    PREVIEW_SHAPES,
    TextureMapGpuRequiredError,
    default_texture_map_settings,
    export_texture_maps,
    generate_texture_maps,
    normalize_texture_map_settings,
    pack_texture_channels,
    render_plane_preview_from_generated,
    render_source_preview_image,
    select_texture_map_backend,
    texture_lab_cpu_fallback_allowed,
    texture_lab_gpu_install_plan,
    texture_map_settings_fingerprint,
    texture_map_to_image,
)


_WM_ENTERSIZEMOVE = 0x0231
_WM_EXITSIZEMOVE = 0x0232


_TEXTURE_THUMBNAILS: tuple[tuple[str, str], ...] = (
    ("Raw", "base_color_source"),
    ("Base", "base_color"),
    ("Normal", "normal"),
    ("AO", "ao"),
    ("Rough", "roughness"),
    ("Irrad", "irradiance"),
    ("Shade", "delight_shading"),
    ("Height", "height"),
    ("Cavity", "cavity"),
    ("Curv", "curvature"),
    ("F0", "f0"),
    ("F90", "f90_mask"),
    ("ORM", "unreal_orm"),
)


class _TextureLabSlider(QWidget):
    def __init__(
        self,
        label: str,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
        value: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.step = float(step)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(3)
        self.label = QLabel(label, self)
        self.label.setObjectName("TextureLabControlLabel")
        self.value_label = QLabel("", self)
        self.value_label.setObjectName("TextureLabValueLabel")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider = StudioSlider("accent", self)
        self.slider.setRange(0, max(1, int(round((self.maximum - self.minimum) / self.step))))
        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.value_label, 0, 1)
        layout.addWidget(self.slider, 1, 0, 1, 2)
        self.set_value(value)

    def value(self) -> float:
        return self.minimum + float(self.slider.value()) * self.step

    def set_value(self, value: float) -> None:
        ratio = (float(value) - self.minimum) / self.step
        self.slider.setValue(max(self.slider.minimum(), min(self.slider.maximum(), int(round(ratio)))))
        self._sync_label()

    def connect_changed(self, callback) -> None:
        self.slider.valueChanged.connect(lambda _value: (self._sync_label(), callback()))

    def _sync_label(self) -> None:
        value = self.value()
        if self.maximum <= 3.0:
            text = f"{value:.2f}"
        else:
            text = f"{value:.1f}"
        self.value_label.setText(text)


class _TextureLabPreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_pixmap = QPixmap()
        self._thumbnails: list[tuple[str, QPixmap, bool]] = []
        self._scaled_pixmap_cache: dict[tuple[str, int, int, int], QPixmap] = {}
        self._interactive_paint = False
        self.setObjectName("TextureLabPreview")
        self.setMinimumSize(620, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_interactive_paint(self, enabled: bool) -> None:
        value = bool(enabled)
        if self._interactive_paint == value:
            return
        self._interactive_paint = value
        self.update()

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self._preview_pixmap = QPixmap(pixmap) if pixmap is not None else QPixmap()
        self._scaled_pixmap_cache.clear()
        self.update()

    def preview_pixmap(self) -> QPixmap:
        return QPixmap(self._preview_pixmap)

    def set_thumbnail_pixmaps(self, thumbnails: list[tuple[str, QPixmap, bool]]) -> None:
        self._thumbnails = [
            (str(label), QPixmap(pixmap), bool(active))
            for label, pixmap, active in thumbnails
            if pixmap is not None and not pixmap.isNull()
        ]
        self._scaled_pixmap_cache.clear()
        self.update()

    def thumbnail_count(self) -> int:
        return len(self._thumbnails)

    def paintEvent(self, _event) -> None:  # pragma: no cover - visual paint path
        painter = QPainter(self)
        if not self._interactive_paint:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillRect(self.rect(), QColor("#08090C"))

        content = frame.adjusted(12, 12, -12, -12)
        if self._preview_pixmap.isNull():
            painter.setPen(QColor("#8F98A7"))
            painter.drawText(content, Qt.AlignmentFlag.AlignCenter, "No preview")
            painter.end()
            return

        preview_rect = self._scaled_rect(self._preview_pixmap, content)
        self._draw_cached_pixmap(painter, preview_rect, self._preview_pixmap, "preview")
        if self._interactive_paint:
            painter.end()
            return
        painter.setPen(QPen(QColor("#252A34"), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(frame, 6, 6)
        self._draw_thumbnails(painter, content, preview_rect)
        painter.end()

    def _scaled_rect(self, pixmap: QPixmap, content: QRectF) -> QRectF:
        scale = min(
            content.width() / max(1, pixmap.width()),
            content.height() / max(1, pixmap.height()),
        )
        width = max(1.0, pixmap.width() * scale)
        height = max(1.0, pixmap.height() * scale)
        x = content.left() + (content.width() - width) * 0.5
        y = content.top() + (content.height() - height) * 0.5
        return QRectF(x, y, width, height)

    def _draw_thumbnails(self, painter: QPainter, content: QRectF, preview_rect: QRectF) -> None:
        if not self._thumbnails:
            return
        left_width = max(0.0, preview_rect.left() - content.left())
        right_width = max(0.0, content.right() - preview_rect.right())
        min_side_width = 104.0
        if left_width >= min_side_width and right_width >= min_side_width:
            split = (len(self._thumbnails) + 1) // 2
            self._draw_thumbnail_column(painter, content, content.left(), left_width, self._thumbnails[:split])
            self._draw_thumbnail_column(
                painter,
                content,
                preview_rect.right(),
                right_width,
                self._thumbnails[split:],
            )
            return
        if right_width >= min_side_width:
            self._draw_thumbnail_column(painter, content, preview_rect.right(), right_width, self._thumbnails[:7])
            return
        if left_width >= min_side_width:
            self._draw_thumbnail_column(painter, content, content.left(), left_width, self._thumbnails[:7])
            return
        self._draw_thumbnail_strip(painter, content, preview_rect)

    def _draw_thumbnail_column(
        self,
        painter: QPainter,
        content: QRectF,
        x_start: float,
        gutter_width: float,
        thumbnails: list[tuple[str, QPixmap, bool]],
    ) -> None:
        if not thumbnails:
            return
        gap = 7.0
        side_pad = 8.0
        width = max(90.0, min(168.0, gutter_width - side_pad * 2.0))
        x = x_start + (gutter_width - width) * 0.5
        usable_height = content.height()
        item_height = min(104.0, max(64.0, (usable_height - gap * (len(thumbnails) - 1)) / len(thumbnails)))
        visible_count = min(len(thumbnails), max(1, int((usable_height + gap) / max(1.0, item_height + gap))))
        rows = thumbnails[:visible_count]
        total_height = item_height * len(rows) + gap * max(0, len(rows) - 1)
        y = content.top() + max(0.0, (usable_height - total_height) * 0.5)
        for label, pixmap, active in rows:
            self._draw_thumbnail_card(painter, QRectF(x, y, width, item_height), label, pixmap, active)
            y += item_height + gap

    def _draw_thumbnail_strip(self, painter: QPainter, content: QRectF, preview_rect: QRectF) -> None:
        gap = 6.0
        rows = self._thumbnails[:6]
        if not rows:
            return
        width = min(124.0, max(84.0, (content.width() - gap * (len(rows) - 1)) / len(rows)))
        height = 72.0
        total_width = width * len(rows) + gap * max(0, len(rows) - 1)
        x = content.left() + (content.width() - total_width) * 0.5
        y = min(content.bottom() - height, preview_rect.bottom() + 8.0)
        for label, pixmap, active in rows:
            self._draw_thumbnail_card(painter, QRectF(x, y, width, height), label, pixmap, active)
            x += width + gap

    def _draw_thumbnail_card(
        self,
        painter: QPainter,
        rect: QRectF,
        label: str,
        pixmap: QPixmap,
        active: bool,
    ) -> None:
        painter.setPen(QPen(QColor("#58D38A" if active else "#303746"), 1.0))
        painter.setBrush(QColor(18, 21, 27, 226))
        painter.drawRoundedRect(rect, 5, 5)
        label_rect = QRectF(rect.left() + 6, rect.top() + 4, rect.width() - 12, 20)
        font = QFont("Cascadia Mono")
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#F2F5FB" if active else "#B8C2D2"))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
        image_rect = rect.adjusted(6, 28, -6, -6)
        if image_rect.width() < 8 or image_rect.height() < 8:
            return
        scaled = self._scaled_rect(pixmap, image_rect)
        self._draw_cached_pixmap(painter, scaled, pixmap, f"thumb:{label}")

    def _draw_cached_pixmap(
        self,
        painter: QPainter,
        rect: QRectF,
        pixmap: QPixmap,
        role: str,
    ) -> None:
        target = rect.toAlignedRect()
        width = max(1, int(target.width()))
        height = max(1, int(target.height()))
        key = (role, int(pixmap.cacheKey()), width, height)
        scaled = self._scaled_pixmap_cache.get(key)
        if scaled is None or scaled.isNull():
            scaled = pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_pixmap_cache[key] = scaled
        x = target.x() + max(0, (width - scaled.width()) // 2)
        y = target.y() + max(0, (height - scaled.height()) // 2)
        painter.drawPixmap(x, y, scaled)


class _TextureLabGpuInstallDialog(QDialog):
    installed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Texture Lab GPU 자동 설치")
        self.setObjectName("TextureLabGpuInstallDialog")
        self.setMinimumSize(760, 470)
        self._plan = texture_lab_gpu_install_plan()
        self._process: QProcess | None = None
        self._phase = "idle"
        self._cancel_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Texture Lab GPU backend를 설치하고 연결합니다.", self)
        title.setObjectName("TextureLabInstallTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        explain = QLabel(
            "RTX/OpenGL 프리뷰와 별개로, Texture Lab의 PBR 맵 생성은 이 가상환경에 "
            "PyTorch CUDA가 설치되어 있어야 합니다. 설치 후 자동으로 검증하고 torch_cuda를 선택합니다.",
            self,
        )
        explain.setObjectName("TextureLabInstallExplain")
        explain.setWordWrap(True)
        layout.addWidget(explain)

        self._state = QLabel("설치 준비 완료. 시작 버튼을 누르면 콘솔 창 없이 설치합니다.", self)
        self._state.setObjectName("TextureLabInstallState")
        self._state.setWordWrap(True)
        layout.addWidget(self._state)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)

        self._console = QPlainTextEdit(self)
        self._console.setReadOnly(True)
        self._console.setObjectName("TextureLabInstallConsole")
        self._console.setMinimumHeight(230)
        self._console.setPlaceholderText("설치 로그가 여기에 표시됩니다.")
        layout.addWidget(self._console, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._start_button = QPushButton("설치 시작", self)
        self._start_button.setObjectName("TextureLabInstallPrimary")
        self._cancel_button = QPushButton("취소", self)
        self._close_button = QPushButton("닫기", self)
        self._close_button.setEnabled(False)
        self._close_button.setDefault(True)
        self._start_button.clicked.connect(self.start_install)
        self._cancel_button.clicked.connect(self.cancel_install)
        self._close_button.clicked.connect(self.close)
        buttons.addWidget(self._start_button)
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._close_button)
        layout.addLayout(buttons)

        self._log("Install:")
        self._log(str(self._plan.get("install_command") or ""))
        self._log("")
        self._log("Verify:")
        self._log(str(self._plan.get("verify_command") or ""))

    def start_install(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._cancel_requested = False
        self._start_button.setEnabled(False)
        self._close_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._progress.setRange(0, 0)
        self._set_state("PyTorch CUDA 패키지를 설치하는 중입니다. 다운로드가 커서 시간이 걸릴 수 있습니다.", value=10, busy=True)
        self._start_process(
            "install",
            str(self._plan["install_program"]),
            [str(arg) for arg in self._plan["install_args"]],
        )

    def cancel_install(self) -> None:
        proc = self._process
        if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
            self._log("사용자가 설치를 취소했습니다.")
            self._cancel_requested = True
            self._start_button.setEnabled(False)
            self._cancel_button.setEnabled(False)
            self._set_state("설치를 취소하는 중입니다.", busy=True)
            proc.terminate()
            QTimer.singleShot(1200, lambda p=proc: p.kill() if p.state() != QProcess.ProcessState.NotRunning else None)
            return
        self._finish(False, "설치가 취소되었습니다. 다시 시작할 수 있습니다.", allow_retry=True)

    def _start_process(self, phase: str, program: str, args: list[str]) -> None:
        from app.subprocess_utils import configure_hidden_qprocess

        self._phase = phase
        self._log("")
        self._log(f"$ {program} {' '.join(args)}")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        configure_hidden_qprocess(proc)
        proc.readyReadStandardOutput.connect(lambda p=proc: self._read_output(p))
        proc.errorOccurred.connect(lambda _err, p=proc: self._process_error(p))
        proc.finished.connect(lambda code, _status, p=proc: self._process_finished(p, code))
        self._process = proc
        proc.start(program, args)

    def _read_output(self, proc: QProcess) -> None:
        try:
            text = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        except Exception:
            text = ""
        if text:
            self._log(text)

    def _process_error(self, proc: QProcess) -> None:
        try:
            message = proc.errorString()
        except Exception:
            message = "process error"
        self._log(f"프로세스 오류: {message}")

    def _process_finished(self, proc: QProcess, exit_code: int) -> None:
        self._read_output(proc)
        if self._process is proc:
            self._process = None
        if self._cancel_requested:
            self._cancel_requested = False
            self._finish(False, "설치가 취소되었습니다. 다시 시작할 수 있습니다.", allow_retry=True)
            return
        if self._phase == "install":
            if int(exit_code) != 0:
                self._finish(False, f"설치가 완료되지 않았습니다. exit code: {exit_code}", allow_retry=True)
                return
            self._set_state("설치 완료. CUDA 사용 가능 여부를 검증하는 중입니다.", value=75, busy=True)
            importlib.invalidate_caches()
            self._start_process(
                "verify",
                str(self._plan["verify_program"]),
                [str(arg) for arg in self._plan["verify_args"]],
            )
            return
        if self._phase == "verify":
            if int(exit_code) != 0:
                self._finish(
                    False,
                    "설치는 끝났지만 torch.cuda.is_available() 검증에 실패했습니다. 로그를 확인하세요.",
                    allow_retry=True,
                )
                return
            os.environ["TIGERCAPTURE_TEXTURE_LAB_BACKEND"] = "torch_cuda"
            importlib.invalidate_caches()
            payload = select_texture_map_backend("torch_cuda", allow_cpu=False)
            if payload.get("active") != "torch_cuda":
                self._finish(
                    False,
                    "검증 출력은 성공했지만 Texture Lab backend 선택이 아직 torch_cuda가 아닙니다. 앱을 재시작해 주세요.",
                    allow_retry=True,
                )
                return
            self._finish(True, "완료: Texture Lab GPU backend가 연결되었습니다.", allow_retry=False)
            self.installed.emit(payload)

    def _set_state(self, text: str, *, value: int | None = None, busy: bool = False) -> None:
        self._state.setText(text)
        if busy:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 100)
            if value is not None:
                self._progress.setValue(max(0, min(100, int(value))))

    def _finish(self, success: bool, message: str, *, allow_retry: bool) -> None:
        self._set_state(message, value=100 if success else 0, busy=False)
        self._start_button.setEnabled(bool(allow_retry))
        self._start_button.setText("다시 설치" if allow_retry else "설치 완료")
        self._cancel_button.setEnabled(False)
        self._close_button.setEnabled(True)
        if success:
            self._close_button.setText("완료 / 닫기")
            self._close_button.setObjectName("TextureLabInstallDone")
            self._close_button.setDefault(True)
        self._log(message)

    def _log(self, text: str) -> None:
        clean = str(text or "").replace("\r", "\n")
        if not clean:
            self._console.appendPlainText("")
        else:
            for line in clean.splitlines():
                self._console.appendPlainText(line.rstrip())
        try:
            self._console.verticalScrollBar().setValue(self._console.verticalScrollBar().maximum())
        except Exception:
            pass


class ArPbrTextureMapLabWindow(QMainWindow):
    """Image-to-material plane preview and export controls."""

    def __init__(
        self,
        image_path: str | Path,
        parent: QWidget | None = None,
        *,
        allow_cpu: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self.image_path = Path(image_path).expanduser()
        self._allow_cpu_fallback = (
            texture_lab_cpu_fallback_allowed(False)
            if allow_cpu is None
            else bool(allow_cpu)
        )
        self._settings = normalize_texture_map_settings(default_texture_map_settings())
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.refresh_preview)
        self._light_animation_timer = QTimer(self)
        self._light_animation_timer.setInterval(16)
        self._light_animation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._light_animation_timer.timeout.connect(self._advance_light_animation)
        self._light_animation_clock = QElapsedTimer()
        self._window_motion_timer = QTimer(self)
        self._window_motion_timer.setSingleShot(True)
        self._window_motion_timer.setInterval(120)
        self._window_motion_timer.timeout.connect(self._end_interactive_window_motion)
        self._window_motion_active = False
        self._window_updates_frozen = False
        self._preview_refresh_deferred = False
        self._resume_light_animation_after_motion = False
        self._sliders: dict[str, _TextureLabSlider] = {}
        self._last_preview_path: Path | None = None
        self._clipboard_shortcuts: list[QShortcut] = []
        self._advanced_map_checks: dict[str, QCheckBox] = {}
        self._preview_heading: QLabel | None = None
        self._substrate_mode_check: QCheckBox | None = None
        self._animate_light_check: QCheckBox | None = None
        self._delight_check: QCheckBox | None = None
        self._animated_light_azimuth = float(self._settings["preview_light_azimuth"])
        self._generated_maps_cache: dict[str, Any] | None = None
        self._backend_selection = select_texture_map_backend(allow_cpu=self._allow_cpu_fallback)
        self.setObjectName("ArPbrTextureMapLabWindow")
        self.setWindowTitle(f"AR/PBR Texture Lab - {self.image_path.name}")
        self.resize(1120, 720)
        self.setStyleSheet(studio_chrome_qss(_TEXTURE_LAB_QSS))
        self._build_ui()
        self.refresh_preview()

    def settings(self) -> dict[str, Any]:
        values = dict(self._settings)
        for key, slider in self._sliders.items():
            values[key] = slider.value()
        values["normal_format"] = str(self._normal_format_combo.currentData() or "unreal_directx")
        delight_checked = (
            bool(self._delight_check.isChecked())
            if self._delight_check is not None
            else bool(self._settings.get("delight_enabled", False))
        )
        values["delight_enabled"] = delight_checked
        animate_light_checked = (
            bool(self._animate_light_check.isChecked())
            if self._animate_light_check is not None
            else bool(self._settings.get("preview_animate_light", False))
        )
        if animate_light_checked:
            values["preview_light_azimuth"] = self._animated_light_azimuth
        values["preview_animate_light"] = animate_light_checked
        values["substrate_enabled"] = bool(
            self._substrate_mode_check.isChecked()
            if self._substrate_mode_check is not None
            else self._settings.get("substrate_enabled", False)
        )
        values["substrate_mode"] = "slab" if values["substrate_enabled"] else "off"
        return normalize_texture_map_settings(values)

    def copy_preview_to_clipboard(self) -> dict[str, Any]:
        pix = QPixmap()
        preview_path = getattr(self, "_last_preview_path", None)
        if preview_path is not None and Path(preview_path).exists():
            pix = QPixmap(str(preview_path))
        if pix.isNull():
            pix = self._preview.preview_pixmap()
        if pix.isNull():
            raise ValueError("no Texture Lab preview image is available to copy")
        QApplication.clipboard().setImage(pix.toImage())
        payload = {
            "copied": True,
            "preview_path": str(preview_path or ""),
            "width": int(pix.width()),
            "height": int(pix.height()),
        }
        self._status.setText(f"Copied preview to clipboard | {pix.width()} x {pix.height()}")
        return payload

    def paste_image_from_clipboard(self) -> dict[str, Any]:
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        image = clipboard.image()
        if image is not None and not image.isNull():
            root = Path(tempfile.gettempdir()) / "tiger_ar_pbr_texture_lab"
            root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = root / f"clipboard_source_{stamp}.png"
            if not image.save(str(path), "PNG"):
                raise ValueError("clipboard image could not be saved")
            source_kind = "clipboard_image"
        else:
            path = self._clipboard_path(mime)
            if path is None:
                raise ValueError("clipboard does not contain an image or image file path")
            source_kind = "clipboard_path"
        self._set_source_image_path(path)
        self._show_source_fallback_preview(
            "Pasted image. GPU texture generation is unavailable, so showing source preview."
        )
        self.refresh_preview()
        return {
            "pasted": True,
            "source_kind": source_kind,
            "source_path": str(self.image_path),
        }

    def _clipboard_path(self, mime) -> Path | None:
        candidates: list[str] = []
        if mime is not None and mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    candidates.append(url.toLocalFile())
        if mime is not None and mime.hasText():
            text = mime.text().strip().strip('"')
            if text:
                candidates.append(text)
        for candidate in candidates:
            path = Path(candidate).expanduser()
            if path.exists() and path.is_file():
                return path
        return None

    def _set_source_image_path(self, path: str | Path) -> None:
        self.image_path = Path(path).expanduser()
        self._last_preview_path = None
        self._generated_maps_cache = None
        self.setWindowTitle(f"AR/PBR Texture Lab - {self.image_path.name}")
        if hasattr(self, "_subtitle"):
            self._subtitle.setText(str(self.image_path))
            self._subtitle.setToolTip(str(self.image_path))

    def _show_source_fallback_preview(self, message: str) -> None:
        pix = QPixmap()
        shape = "plane"
        try:
            shape = str(self._preview_shape_combo.currentData() or "plane")
            mode = str(self._preview_mode_combo.currentData() or "material")
            if mode == "material":
                out = (
                    Path(tempfile.gettempdir())
                    / "tiger_ar_pbr_texture_lab"
                    / f"{self.image_path.stem}_source_{shape}_fallback.png"
                )
                payload = render_source_preview_image(
                    self.image_path,
                    preview_shape=shape,
                    output_path=out,
                    width=960,
                    settings=self.settings(),
                )
                pix = QPixmap(str(payload["preview_path"]))
        except Exception:
            pix = QPixmap()
        if pix.isNull():
            shape = "plane"
            pix = QPixmap(str(self.image_path))
        if pix.isNull():
            return
        self._preview.set_preview_pixmap(pix)
        self._preview.set_thumbnail_pixmaps([])
        self._last_preview_path = None
        if hasattr(self, "_preview_heading") and self._preview_heading is not None:
            self._preview_heading.setText("Sphere Source Preview" if shape == "sphere" else "Source Preview")
        if hasattr(self, "_status"):
            self._status.setText(message)

    def _copy_preview_to_clipboard_from_ui(self) -> None:
        try:
            self.copy_preview_to_clipboard()
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab Clipboard", f"Copy failed.\n\n{type(exc).__name__}: {exc}")

    def _paste_image_from_clipboard_from_ui(self) -> None:
        try:
            self.paste_image_from_clipboard()
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab Clipboard", f"Paste failed.\n\n{type(exc).__name__}: {exc}")

    def _select_preview_mode(self, mode: str) -> bool:
        index = self._preview_mode_combo.findData(mode)
        if index < 0:
            return False
        self._preview_mode_combo.setCurrentIndex(index)
        return True

    def _show_albedo_preview(self) -> None:
        if self._delight_check is not None and not self._delight_check.isChecked():
            self._delight_check.blockSignals(True)
            self._delight_check.setChecked(True)
            self._delight_check.blockSignals(False)
            self._sync_delight_controls()
        if not self._select_preview_mode("albedo"):
            self.queue_preview()

    def _show_intrinsic_channels_preview(self) -> None:
        if self._delight_check is not None and not self._delight_check.isChecked():
            self._delight_check.blockSignals(True)
            self._delight_check.setChecked(True)
            self._delight_check.blockSignals(False)
            self._sync_delight_controls()
        if not self._select_preview_mode("intrinsic_channels"):
            self.queue_preview()

    def _show_delight_compare_preview(self) -> None:
        if self._delight_check is not None and not self._delight_check.isChecked():
            self._delight_check.blockSignals(True)
            self._delight_check.setChecked(True)
            self._delight_check.blockSignals(False)
            self._sync_delight_controls()
        if not self._select_preview_mode("delight_compare"):
            self.queue_preview()

    def _preview_mode_label(self, mode: str) -> str:
        labels = {
            "material": "Material",
            "intrinsic_channels": "Intrinsic Channels",
            "albedo": "Albedo",
            "delight_compare": "De-Light Compare",
            "base_color_source": "Input BaseColor",
            "base_color": "BaseColor / Albedo",
            "normal": "Normal",
            "ao": "Ambient Occlusion",
            "roughness": "Roughness",
            "metallic": "Metallic",
            "irradiance": "Irradiance",
            "delight_shading": "De-light Shading Field",
            "height": "Height",
            "cavity": "Cavity",
            "curvature": "Curvature",
            "f0": "Substrate F0",
            "f90_mask": "Substrate F90 Mask",
            "unreal_orm": "Unreal ORM",
            "arm": "ARM Packed",
            "gltf_mr": "glTF MR",
        }
        return labels.get(mode, mode.replace("_", " ").title())

    def _backend_status_text(self) -> str:
        selection = select_texture_map_backend(allow_cpu=self._allow_cpu_fallback)
        self._backend_selection = selection
        active = str(selection.get("active", "cpu"))
        status = selection.get("status", {})
        torch_status = dict(status.get("backends", {}).get("torch_cuda", {}))
        if active == "torch_cuda":
            device = str(torch_status.get("device") or "CUDA GPU")
            return f"GPU acceleration: torch_cuda | {device}"
        if active == "unavailable":
            reason = str(selection.get("reason") or "gpu_backend_required")
            if not torch_status.get("module_installed"):
                return "GPU install needed: RTX/OpenGL detected separately; PyTorch CUDA is missing in this venv"
            if not torch_status.get("available"):
                return "GPU install needed: PyTorch is installed, but CUDA is unavailable to this venv"
            return f"GPU backend required: {reason}"
        if not torch_status.get("module_installed"):
            return "CPU diagnostics only | Install PyTorch CUDA to enable Texture Lab GPU maps"
        if not torch_status.get("available"):
            return "CPU diagnostics only | PyTorch exists, but CUDA is unavailable"
        return f"CPU diagnostics only | {selection.get('reason', 'gpu backend unavailable')}"

    def _show_gpu_setup_help(self) -> None:
        dialog = getattr(self, "_gpu_install_dialog", None)
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog = _TextureLabGpuInstallDialog(self)
        dialog.setStyleSheet(studio_chrome_qss(_TEXTURE_LAB_QSS))
        dialog.installed.connect(self._on_gpu_backend_installed)
        self._gpu_install_dialog = dialog
        dialog.show()

    def _on_gpu_backend_installed(self, payload: object) -> None:
        self._backend_selection = dict(payload or {})
        if hasattr(self, "_backend_status"):
            self._backend_status.setText(self._backend_status_text())
        self._generated_maps_cache = None
        self.queue_preview()

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("TextureLabCentral")
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        top = QVBoxLayout()
        top.setSpacing(6)
        title = QLabel("AR/PBR Texture Lab", central)
        title.setObjectName("TextureLabTitle")
        subtitle = QLabel(str(self.image_path), central)
        subtitle.setObjectName("TextureLabSubtitle")
        subtitle.setToolTip(str(self.image_path))
        subtitle.setMinimumWidth(0)
        subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._subtitle = subtitle
        self._backend_status = QLabel(self._backend_status_text(), central)
        self._backend_status.setObjectName("TextureLabBackendStatus")
        self._backend_status.setMinimumWidth(0)
        self._backend_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_block.addWidget(self._backend_status)
        top.addLayout(title_block)
        self._preview_mode_combo = QComboBox(central)
        self._preview_mode_combo.setObjectName("TextureLabCombo")
        for mode in PREVIEW_MODES:
            self._preview_mode_combo.addItem(mode.replace("_", " ").title(), mode)
        self._preview_mode_combo.currentIndexChanged.connect(self.queue_preview)
        self._preview_shape_combo = QComboBox(central)
        self._preview_shape_combo.setObjectName("TextureLabShapeCombo")
        for shape in PREVIEW_SHAPES:
            self._preview_shape_combo.addItem(shape.title(), shape)
        self._preview_shape_combo.setToolTip("Material preview shape. Texture-map channels still display as flat maps.")
        self._preview_shape_combo.currentIndexChanged.connect(self.queue_preview)
        show_intrinsic = QPushButton("Intrinsic", central)
        show_intrinsic.setObjectName("TextureLabModeButton")
        show_intrinsic.setToolTip("Show Input, Albedo, Normal, Roughness, and Irradiance together")
        show_intrinsic.clicked.connect(self._show_intrinsic_channels_preview)
        show_albedo = QPushButton("Albedo", central)
        show_albedo.setObjectName("TextureLabModeButton")
        show_albedo.setToolTip("Show the de-lighted albedo/BaseColor result in the main preview")
        show_albedo.clicked.connect(self._show_albedo_preview)
        show_compare = QPushButton("Compare", central)
        show_compare.setObjectName("TextureLabModeButton")
        show_compare.setToolTip("Compare source BaseColor, de-lighted albedo, and amplified difference")
        show_compare.clicked.connect(self._show_delight_compare_preview)
        paste_image = QPushButton("Paste Image", central)
        paste_image.setIcon(app_icon("paste", size=16))
        paste_image.setIconSize(icon_size(16))
        paste_image.setToolTip("Paste an image or image file path from the clipboard as the source (Ctrl+V)")
        paste_image.clicked.connect(self._paste_image_from_clipboard_from_ui)
        copy_preview = QPushButton("Copy Preview", central)
        copy_preview.setIcon(app_icon("copy", size=16))
        copy_preview.setIconSize(icon_size(16))
        copy_preview.setToolTip("Copy the current Texture Lab preview image to the clipboard (Ctrl+C)")
        copy_preview.clicked.connect(self._copy_preview_to_clipboard_from_ui)
        gpu_setup = QPushButton("Install GPU", central)
        gpu_setup.setIcon(app_icon("settings", size=16))
        gpu_setup.setIconSize(icon_size(16))
        gpu_setup.setToolTip("Install and verify the Texture Lab PyTorch CUDA backend")
        gpu_setup.clicked.connect(self._show_gpu_setup_help)
        self._gpu_setup_button = gpu_setup
        export_maps = QPushButton("Export Maps", central)
        export_maps.setIcon(app_icon("export", size=16))
        export_maps.setIconSize(icon_size(16))
        export_maps.clicked.connect(self.export_maps)
        export_packed = QPushButton("Export Packed", central)
        export_packed.setIcon(app_icon("save", size=16))
        export_packed.setIconSize(icon_size(16))
        export_packed.clicked.connect(self.export_packed)
        toolbar = QWidget(central)
        toolbar.setObjectName("TextureLabTopToolbar")
        toolbar_layout = QGridLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setHorizontalSpacing(6)
        toolbar_layout.setVerticalSpacing(6)
        toolbar_layout.addWidget(self._preview_mode_combo, 0, 0, 1, 2)
        toolbar_layout.addWidget(self._preview_shape_combo, 0, 2)
        toolbar_layout.addWidget(show_intrinsic, 0, 3)
        toolbar_layout.addWidget(show_albedo, 0, 4)
        toolbar_layout.addWidget(show_compare, 0, 5)
        toolbar_layout.addWidget(paste_image, 1, 0)
        toolbar_layout.addWidget(copy_preview, 1, 1)
        toolbar_layout.addWidget(gpu_setup, 1, 2)
        toolbar_layout.addWidget(export_maps, 1, 3)
        toolbar_layout.addWidget(export_packed, 1, 4, 1, 2)
        top.addWidget(toolbar, 0, Qt.AlignmentFlag.AlignLeft)
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy_shortcut.activated.connect(self._copy_preview_to_clipboard_from_ui)
        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self._paste_image_from_clipboard_from_ui)
        self._clipboard_shortcuts.extend([copy_shortcut, paste_shortcut])
        root.addLayout(top)

        content = QHBoxLayout()
        content.setSpacing(12)
        preview_panel = QFrame(central)
        preview_panel.setObjectName("TextureLabPreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        preview_layout.setSpacing(8)
        preview_label = QLabel("Plane Preview", preview_panel)
        preview_label.setObjectName("TextureLabSection")
        self._preview_heading = preview_label
        self._preview = _TextureLabPreviewCanvas(preview_panel)
        self._status = QLabel("", preview_panel)
        self._status.setObjectName("TextureLabStatus")
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self._preview, 1)
        preview_layout.addWidget(self._status)
        content.addWidget(preview_panel, 1)

        scroll = QScrollArea(central)
        scroll.setObjectName("TextureLabScroll")
        scroll.setWidgetResizable(True)
        controls = QWidget(scroll)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(9)
        self._normal_format_combo = QComboBox(controls)
        self._normal_format_combo.setObjectName("TextureLabCombo")
        self._normal_format_combo.addItem("Unreal / DirectX Normal", "unreal_directx")
        self._normal_format_combo.addItem("OpenGL Normal", "opengl")
        self._normal_format_combo.currentIndexChanged.connect(self.queue_preview)
        controls_layout.addWidget(_section_label("Base Color / Albedo", controls))
        self._delight_check = QCheckBox("De-light Albedo", controls)
        self._delight_check.setObjectName("TextureLabCheck")
        self._delight_check.setChecked(bool(self._settings.get("delight_enabled", False)))
        self._delight_check.setToolTip("Remove broad photographic lighting and shadow from BaseColor.")
        self._delight_check.toggled.connect(self._on_delight_toggled)
        controls_layout.addWidget(self._delight_check)
        self._add_slider(controls_layout, "De-light Strength", "delight_strength", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Shading Radius", "delight_radius_px", 1.0, 256.0, 1.0)
        self._add_slider(controls_layout, "Detail Preserve", "delight_contrast_preservation", 0.0, 1.0, 0.01)
        controls_layout.addWidget(_section_label("Normal", controls))
        controls_layout.addWidget(self._normal_format_combo)
        self._add_slider(controls_layout, "Strength", "normal_strength", 0.0, 12.0, 0.1)
        self._add_slider(controls_layout, "Radius", "normal_radius_px", 0.0, 24.0, 0.1)
        controls_layout.addWidget(_section_label("Height / AO", controls))
        self._add_slider(controls_layout, "Height Contrast", "height_contrast", 0.1, 4.0, 0.01)
        self._add_slider(controls_layout, "Height Blur", "height_blur_px", 0.0, 8.0, 0.05)
        self._add_slider(controls_layout, "AO Strength", "ao_strength", 0.0, 3.0, 0.01)
        self._add_slider(controls_layout, "AO Radius", "ao_radius_px", 0.0, 64.0, 0.5)
        self._add_slider(controls_layout, "AO Height Scale", "ao_height_scale", 0.1, 64.0, 0.1)
        self._add_slider(controls_layout, "Cavity", "cavity_strength", 0.0, 2.0, 0.01)
        self._add_slider(controls_layout, "Cavity Radius", "cavity_radius_px", 0.2, 32.0, 0.1)
        self._add_slider(controls_layout, "Curvature", "curvature_strength", 0.0, 8.0, 0.01)
        controls_layout.addWidget(_section_label("Surface", controls))
        self._add_slider(controls_layout, "Roughness Bias", "roughness_bias", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Roughness Contrast", "roughness_contrast", 0.1, 3.0, 0.01)
        self._add_slider(controls_layout, "Roughness Detail", "roughness_detail", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Metallic", "metallic_value", 0.0, 1.0, 0.01)
        controls_layout.addWidget(_section_label("Substrate", controls))
        self._substrate_mode_check = QCheckBox("Substrate Slab", controls)
        self._substrate_mode_check.setObjectName("TextureLabCheck")
        self._substrate_mode_check.setChecked(bool(self._settings.get("substrate_enabled", False)))
        self._substrate_mode_check.setToolTip(
            "Use Unreal Substrate Slab output contract. Metallic is converted through DiffuseAlbedo/F0."
        )
        self._substrate_mode_check.toggled.connect(self._on_substrate_mode_toggled)
        controls_layout.addWidget(self._substrate_mode_check)
        self._add_advanced_map_check(controls_layout, controls, "Export F0 Map", "f0")
        self._add_advanced_map_check(controls_layout, controls, "Export F90 Mask", "f90_mask")
        self._add_slider(controls_layout, "F0 Reflectance", "substrate_reflectance", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "F90 Mask", "f90_mask_strength", 0.0, 1.0, 0.01)
        controls_layout.addWidget(_section_label("Preview Light", controls))
        self._animate_light_check = QCheckBox("Animate Light", controls)
        self._animate_light_check.setObjectName("TextureLabCheck")
        self._animate_light_check.setChecked(bool(self._settings.get("preview_animate_light", False)))
        self._animate_light_check.setToolTip("Orbit the preview point light around the plane to inspect shading.")
        self._animate_light_check.toggled.connect(self._on_animate_light_toggled)
        controls_layout.addWidget(self._animate_light_check)
        self._add_slider(controls_layout, "Azimuth", "preview_light_azimuth", -180.0, 180.0, 1.0)
        self._add_slider(controls_layout, "Elevation", "preview_light_elevation", 3.0, 89.0, 1.0)
        self._add_slider(controls_layout, "Environment", "preview_environment", 0.0, 1.5, 0.01)
        controls_layout.addStretch(1)
        scroll.setWidget(controls)
        content.addWidget(scroll, 0)
        root.addLayout(content, 1)
        self.setCentralWidget(central)
        self._sync_substrate_controls()
        self._sync_delight_controls()
        self._on_animate_light_toggled(bool(self._animate_light_check.isChecked()) if self._animate_light_check else False)

    def _add_slider(
        self,
        layout: QVBoxLayout,
        label: str,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        slider = _TextureLabSlider(label, key, minimum, maximum, step, float(self._settings[key]), self)
        slider.connect_changed(self.queue_preview)
        self._sliders[key] = slider
        layout.addWidget(slider)

    def _add_advanced_map_check(self, layout: QVBoxLayout, parent: QWidget, label: str, map_name: str) -> None:
        check = QCheckBox(label, parent)
        check.setObjectName("TextureLabCheck")
        check.setChecked(False)
        check.setToolTip(f"Include {map_name} when exporting separate maps")
        self._advanced_map_checks[map_name] = check
        layout.addWidget(check)

    def _on_substrate_mode_toggled(self, _checked: bool) -> None:
        self._sync_substrate_controls()
        self.queue_preview()

    def _on_delight_toggled(self, checked: bool) -> None:
        self._sync_delight_controls()
        if checked and self._preview_mode_combo is not None:
            current = str(self._preview_mode_combo.currentData() or "")
            if current in {"material", "base_color", "base_color_source"}:
                if self._select_preview_mode("albedo"):
                    return
        self.queue_preview()

    def _on_animate_light_toggled(self, checked: bool) -> None:
        if checked:
            slider = self._sliders.get("preview_light_azimuth")
            if slider is not None:
                self._animated_light_azimuth = slider.value()
                slider.setEnabled(False)
                slider.setToolTip("Animate Light is driving the preview azimuth.")
            self._light_animation_clock.restart()
            self._light_animation_timer.start()
        else:
            self._light_animation_timer.stop()
            slider = self._sliders.get("preview_light_azimuth")
            if slider is not None:
                slider.setEnabled(True)
                slider.setToolTip("")
                slider.set_value(self._animated_light_azimuth)
        self.queue_preview()

    def _advance_light_animation(self) -> None:
        elapsed = max(0, int(self._light_animation_clock.elapsed()))
        phase = (elapsed / 4800.0) * (2.0 * math.pi)
        self._animated_light_azimuth = -60.0 + (1.0 - math.cos(phase)) * 60.0
        self.refresh_preview()

    def _sync_substrate_controls(self) -> None:
        substrate_enabled = bool(self._substrate_mode_check.isChecked()) if self._substrate_mode_check else False
        metallic_slider = self._sliders.get("metallic_value")
        if metallic_slider is not None:
            metallic_slider.setEnabled(not substrate_enabled)
            metallic_slider.setToolTip(
                "Substrate Slab has no direct Metallic input; the value is used only by the DiffuseAlbedo/F0 helper."
                if substrate_enabled
                else ""
            )
        for name in ("f0", "f90_mask"):
            check = self._advanced_map_checks.get(name)
            if check is not None and substrate_enabled:
                check.setChecked(True)

    def _sync_delight_controls(self) -> None:
        enabled = bool(self._delight_check.isChecked()) if self._delight_check else False
        for key in ("delight_strength", "delight_radius_px", "delight_contrast_preservation"):
            slider = self._sliders.get(key)
            if slider is not None:
                slider.setEnabled(enabled)
                slider.setToolTip(
                    "Controls estimated illumination removal for de-lighted BaseColor."
                    if enabled
                    else "Enable De-light Albedo to edit this value."
                )

    def queue_preview(self) -> None:
        if self._window_motion_active or self._window_updates_frozen:
            self._preview_refresh_deferred = True
            return
        self._preview_timer.start(120)

    def _source_cache_identity(self) -> str:
        try:
            stat = self.image_path.stat()
            return f"{self.image_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
        except Exception:
            return str(self.image_path)

    def _cached_generated_maps(self, *, max_size: int = 960) -> tuple[dict[str, Any], bool]:
        settings = self.settings()
        key = {
            "source": self._source_cache_identity(),
            "settings": texture_map_settings_fingerprint(settings),
            "max_size": int(max_size),
        }
        cached = self._generated_maps_cache
        if isinstance(cached, dict) and cached.get("key") == key:
            return cached["generated"], True
        generated = generate_texture_maps(
            self.image_path,
            settings,
            max_size=max_size,
            allow_cpu=self._allow_cpu_fallback,
        )
        self._generated_maps_cache = {"key": key, "generated": generated}
        return generated, False

    def refresh_preview(self) -> None:
        if self._window_motion_active or self._window_updates_frozen:
            self._preview_refresh_deferred = True
            return
        if not self.image_path.exists():
            self._status.setText(f"Missing source image: {self.image_path}")
            return
        selection = select_texture_map_backend(allow_cpu=self._allow_cpu_fallback)
        self._backend_selection = selection
        if not self._allow_cpu_fallback and str(selection.get("active", "")) == "unavailable":
            if hasattr(self, "_backend_status"):
                self._backend_status.setText(self._backend_status_text())
            self._show_source_fallback_preview(
                "Source preview ready. Install the Texture Lab GPU backend to generate PBR maps."
            )
            return
        try:
            mode = str(self._preview_mode_combo.currentData() or "material")
            requested_shape = str(self._preview_shape_combo.currentData() or "plane")
            effective_shape = (
                requested_shape
                if mode not in {"intrinsic_channels", "delight_compare"}
                else "plane"
            )
            animating_light = bool(
                self._animate_light_check is not None
                and self._animate_light_check.isChecked()
                and self._light_animation_timer.isActive()
            )
            preview_size = 256 if animating_light else 960
            if self._preview_heading is not None:
                self._preview_heading.setText(
                    f"{effective_shape.title()} Preview - {self._preview_mode_label(mode)}"
                )
            out = (
                Path(tempfile.gettempdir())
                / "tiger_ar_pbr_texture_lab"
                / f"{self.image_path.stem}_{effective_shape}_{mode}.png"
            )
            generated, cache_hit = self._cached_generated_maps(max_size=preview_size)
            payload = render_plane_preview_from_generated(
                generated,
                self.settings(),
                preview_mode=mode,
                preview_shape=requested_shape,
                output_path=out,
                width=preview_size,
                source_path=self.image_path,
                allow_cpu_preview=self._allow_cpu_fallback,
            )
            if hasattr(self, "_backend_status"):
                self._backend_status.setText(self._backend_status_text())
            self._last_preview_path = Path(payload["preview_path"])
            pix = QPixmap(str(payload["preview_path"]))
            self._preview.set_preview_pixmap(pix)
            if not animating_light:
                self._preview.set_thumbnail_pixmaps(self._thumbnail_pixmaps(active_mode=mode, generated=generated))
            backend = str(payload.get("backend", {}).get("active", "cpu"))
            cache = "cached" if cache_hit else "rendered"
            shape = str(payload.get("preview_shape", effective_shape))
            cadence = " | live light" if animating_light else ""
            self._status.setText(
                f"{shape}/{mode} | {payload['size'][0]} x {payload['size'][1]} | {backend} | {cache}{cadence}"
            )
        except TextureMapGpuRequiredError as exc:
            if hasattr(self, "_backend_status"):
                self._backend_status.setText(self._backend_status_text())
            self._last_preview_path = None
            self._show_source_fallback_preview(
                "GPU required for PBR maps. Showing source image; install Texture Lab GPU backend to generate maps."
            )
            self._status.setText(
                "GPU required for PBR maps. Showing source image; "
                "install/enable torch_cuda or set TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU=1 for diagnostics."
            )
        except Exception as exc:
            self._status.setText(f"Preview failed: {type(exc).__name__}: {exc}")

    def _thumbnail_pixmaps(
        self,
        *,
        active_mode: str,
        generated: dict[str, Any] | None = None,
    ) -> list[tuple[str, QPixmap, bool]]:
        if generated is None:
            generated, _cache_hit = self._cached_generated_maps(max_size=192)
        maps = generated["maps"]
        root = Path(tempfile.gettempdir()) / "tiger_ar_pbr_texture_lab"
        root.mkdir(parents=True, exist_ok=True)
        thumbnails: list[tuple[str, QPixmap, bool]] = []
        for label, mode in _TEXTURE_THUMBNAILS:
            if mode in maps:
                image = texture_map_to_image(mode, maps[mode])
            elif mode in PACKED_LAYOUTS:
                image = texture_map_to_image(mode, pack_texture_channels(maps, mode))
            else:
                continue
            path = root / f"{self.image_path.stem}_thumb_{mode}.png"
            image.save(path)
            pix = QPixmap(str(path))
            if not pix.isNull():
                thumbnails.append((label, pix, active_mode == mode))
        return thumbnails

    def resizeEvent(self, event) -> None:  # pragma: no cover - visual resize sync
        super().resizeEvent(event)
        if hasattr(self, "_preview"):
            self._preview.update()

    def nativeEvent(self, event_type, message):  # pragma: no cover - Windows native drag performance
        if os.name == "nt":
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if int(msg.message) == _WM_ENTERSIZEMOVE:
                    self._begin_interactive_window_motion()
                elif int(msg.message) == _WM_EXITSIZEMOVE:
                    self._window_motion_timer.stop()
                    self._end_interactive_window_motion()
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def moveEvent(self, event) -> None:  # pragma: no cover - non-Windows fallback
        super().moveEvent(event)
        if os.name != "nt":
            self._begin_interactive_window_motion()

    def _begin_interactive_window_motion(self) -> None:
        if not self.isVisible() or not hasattr(self, "_preview"):
            return
        if not self._window_motion_active:
            self._window_motion_active = True
            if self._preview_timer.isActive():
                self._preview_timer.stop()
                self._preview_refresh_deferred = True
            self._resume_light_animation_after_motion = bool(self._light_animation_timer.isActive())
            if self._resume_light_animation_after_motion:
                self._light_animation_timer.stop()
        self._preview.set_interactive_paint(True)
        self._window_motion_timer.start()

    def _end_interactive_window_motion(self) -> None:
        self._window_updates_frozen = False
        self._window_motion_active = False
        if hasattr(self, "_preview"):
            self._preview.set_interactive_paint(False)
            self._preview.update()
        if self._resume_light_animation_after_motion:
            self._resume_light_animation_after_motion = False
            if self._animate_light_check is not None and self._animate_light_check.isChecked():
                self._light_animation_timer.start()
        if self._preview_refresh_deferred:
            self._preview_refresh_deferred = False
            self._preview_timer.start(30)

    def export_maps(self) -> None:
        self._export_with_layouts([])

    def export_packed(self) -> None:
        self._export_with_layouts(list(PACKED_LAYOUTS))

    def _export_with_layouts(self, packed_layouts: list[str]) -> None:
        default_dir = self.image_path.with_name(f"{self.image_path.stem}_pbr_maps")
        selected = QFileDialog.getExistingDirectory(self, "Export AR/PBR textures", str(default_dir.parent))
        if not selected:
            return
        try:
            map_names = self._selected_export_maps()
            payload = export_texture_maps(
                self.image_path,
                selected,
                self.settings(),
                maps=map_names,
                packed_layouts=packed_layouts,
                allow_cpu=self._allow_cpu_fallback,
            )
        except TextureMapGpuRequiredError as exc:
            QMessageBox.warning(
                self,
                "Texture Lab",
                "GPU required. Texture Lab CPU fallback is disabled.\n\n"
                f"{exc}\n\nInstall/enable torch_cuda or use TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU=1 "
                "only for diagnostics.",
            )
            return
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab", f"Export failed.\n\n{type(exc).__name__}: {exc}")
            return
        self._status.setText(f"Exported: {payload['output_dir']}")

    def _selected_export_maps(self) -> list[str]:
        names = list(DEFAULT_SEPARATE_MAPS)
        if bool(self.settings().get("substrate_enabled", False)):
            names = [name for name in names if name != "metallic"]
            for substrate_map in ("f0", "f90_mask"):
                if substrate_map not in names:
                    names.append(substrate_map)
        for name, check in self._advanced_map_checks.items():
            if check.isChecked() and name not in names:
                names.append(name)
        return names


def _section_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("TextureLabSection")
    return label


_TEXTURE_LAB_QSS = (
    """
QWidget#TextureLabCentral {
    background: #101114;
}
QLabel#TextureLabTitle {
    color: #F2F5FB;
    font-size: 18px;
    font-weight: 700;
}
QLabel#TextureLabSubtitle,
QLabel#TextureLabBackendStatus,
QLabel#TextureLabStatus {
    color: #8F98A7;
    font-size: 12px;
}
QLabel#TextureLabBackendStatus {
    color: #B9C3D2;
}
QLabel#TextureLabInstallTitle {
    color: #F3F6FE;
    font-size: 18px;
    font-weight: 800;
}
QLabel#TextureLabInstallExplain,
QLabel#TextureLabInstallState {
    color: #C8D3E5;
    font-size: 13px;
    line-height: 150%;
}
QFrame#TextureLabPreviewPanel {
    background: #15171D;
    border: 1px solid #2B303B;
    border-radius: 8px;
}
QWidget#TextureLabPreview {
    background: #08090C;
    border: 1px solid #252A34;
    border-radius: 6px;
}
QLabel#TextureLabSection {
    color: #C9D2E1;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0px;
    padding-top: 6px;
}
QLabel#TextureLabControlLabel {
    color: #A9B4C5;
    font-size: 12px;
}
QLabel#TextureLabValueLabel {
    color: #D9E0EA;
    font-size: 12px;
    font-family: "Cascadia Mono", "Consolas";
}
QLabel#TextureLabControlLabel:disabled,
QLabel#TextureLabValueLabel:disabled {
    color: #596273;
}
QComboBox#TextureLabCombo {
    background: #1A1D25;
    color: #E8ECF5;
    border: 1px solid #303746;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    min-width: 180px;
}
QComboBox#TextureLabShapeCombo {
    background: #1A1D25;
    color: #E8ECF5;
    border: 1px solid #303746;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    min-width: 92px;
    max-width: 112px;
}
QComboBox#TextureLabCombo::drop-down {
    border: 0px;
    width: 22px;
}
QComboBox#TextureLabShapeCombo::drop-down {
    border: 0px;
    width: 20px;
}
QComboBox#TextureLabCombo QAbstractItemView,
QComboBox#TextureLabShapeCombo QAbstractItemView {
    background: #141720;
    color: #E8ECF5;
    border: 1px solid #303746;
    selection-background-color: #273245;
}
QScrollArea#TextureLabScroll {
    background: #15171D;
    border: 1px solid #2B303B;
    border-radius: 8px;
    min-width: 300px;
    max-width: 360px;
}
QPushButton {
    background: #20242D;
    color: #F1F4FA;
    border: 1px solid #343B49;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton:hover {
    background: #29303D;
}
QPushButton:pressed {
    background: #D85A30;
    color: #FFFFFF;
}
QPushButton#TextureLabModeButton {
    background: #17251E;
    color: #DDF7E8;
    border: 1px solid #3D7758;
    padding: 8px 14px;
}
QPushButton#TextureLabModeButton:hover {
    background: #1D3428;
    border-color: #58D38A;
}
QPushButton#TextureLabInstallPrimary,
QPushButton#TextureLabInstallDone {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF6A3D, stop:1 #7B61FF);
    color: #FFFFFF;
    border: 1px solid #F7A36D;
}
QPlainTextEdit#TextureLabInstallConsole {
    background: #10131A;
    color: #DDE7F7;
    border: 1px solid #303746;
    border-radius: 8px;
    padding: 8px;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 12px;
}
QProgressBar {
    background: #151923;
    color: #FFFFFF;
    border: 1px solid #343B49;
    border-radius: 7px;
    min-height: 16px;
    text-align: center;
    font-weight: 800;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6A3D, stop:0.48 #FF4D98, stop:1 #6F63FF);
}
QCheckBox#TextureLabCheck {
    color: #C9D2E1;
    font-size: 12px;
    font-weight: 700;
    spacing: 8px;
    padding: 3px 0px;
}
QCheckBox#TextureLabCheck::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3A4353;
    border-radius: 3px;
    background: #11141B;
}
QCheckBox#TextureLabCheck::indicator:checked {
    background: #58D38A;
    border-color: #77E5A0;
}
QCheckBox#TextureLabCheck:disabled {
    color: #596273;
}
"""
    + editor_scrollbar_qss()
)
