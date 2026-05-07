"""Clip Effects Dialog — edit per-clip video effects (filters, chroma key,
stabilizer, background removal) from a single modal inspector."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QLabel, QScrollArea,
    QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)


def _slider(lo: int, hi: int, val: int, step: int = 1) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    s.setSingleStep(step)
    return s


def _pct_slider(val: float) -> QSlider:
    """0.0–1.0 mapped to 0–100 integer slider."""
    return _slider(0, 100, int(val * 100))


# ──────────────────────────────────────────────────────────────
#  Video Filters tab
# ──────────────────────────────────────────────────────────────

class _FiltersTab(QWidget):
    changed = Signal()

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self._params = params
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._enabled = QCheckBox("활성화")
        self._enabled.setChecked(params.enabled)
        self._enabled.toggled.connect(self._emit)
        form.addRow(self._enabled)

        self._sharpen = _pct_slider(params.sharpen / 2.0)  # 0..2 → 0..100
        self._sharpen.valueChanged.connect(self._emit)
        form.addRow("샤픈:", self._sharpen)

        self._vignette = _pct_slider(params.vignette)
        self._vignette.valueChanged.connect(self._emit)
        form.addRow("비네팅:", self._vignette)

        self._denoise = _pct_slider(params.denoise)
        self._denoise.valueChanged.connect(self._emit)
        form.addRow("노이즈 제거:", self._denoise)

        self._chroma_ab = _slider(0, 20, int(params.chroma_aberration))
        self._chroma_ab.valueChanged.connect(self._emit)
        form.addRow("색수차:", self._chroma_ab)

        self._glitch = _pct_slider(params.glitch)
        self._glitch.valueChanged.connect(self._emit)
        form.addRow("글리치:", self._glitch)

    def _emit(self):
        p = self._params
        p.enabled = self._enabled.isChecked()
        p.sharpen = self._sharpen.value() / 100.0 * 2.0
        p.vignette = self._vignette.value() / 100.0
        p.denoise = self._denoise.value() / 100.0
        p.chroma_aberration = float(self._chroma_ab.value())
        p.glitch = self._glitch.value() / 100.0
        self.changed.emit()


# ──────────────────────────────────────────────────────────────
#  Chroma Key tab
# ──────────────────────────────────────────────────────────────

class _ChromaTab(QWidget):
    changed = Signal()

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self._params = params
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._enabled = QCheckBox("활성화")
        self._enabled.setChecked(params.enabled)
        self._enabled.toggled.connect(self._emit)
        form.addRow(self._enabled)

        self._hue = _slider(0, 179, params.key_hue)
        self._hue.valueChanged.connect(self._emit)
        form.addRow("키 색상(Hue):", self._hue)

        self._hue_range = _slider(5, 60, params.hue_range)
        self._hue_range.valueChanged.connect(self._emit)
        form.addRow("허용 범위:", self._hue_range)

        self._sat_min = _slider(0, 255, params.sat_min)
        self._sat_min.valueChanged.connect(self._emit)
        form.addRow("최소 채도:", self._sat_min)

        self._spill = _pct_slider(params.spill_suppress)
        self._spill.valueChanged.connect(self._emit)
        form.addRow("스필 억제:", self._spill)

        self._bg = QComboBox()
        self._bg.addItems(["검정", "흰색", "녹색"])
        form.addRow("배경색:", self._bg)

        lbl = QLabel("💡 그린스크린: Hue=60  블루스크린: Hue=120")
        lbl.setStyleSheet("color:#888; font-size:10px;")
        form.addRow(lbl)

    def _emit(self):
        p = self._params
        p.enabled = self._enabled.isChecked()
        p.key_hue = self._hue.value()
        p.hue_range = self._hue_range.value()
        p.sat_min = self._sat_min.value()
        p.spill_suppress = self._spill.value() / 100.0
        bg_map = [(0,0,0),(255,255,255),(0,255,0)]
        bg = bg_map[self._bg.currentIndex()]
        p.bg_r, p.bg_g, p.bg_b = bg
        self.changed.emit()


# ──────────────────────────────────────────────────────────────
#  Stabilizer tab
# ──────────────────────────────────────────────────────────────

class _StabTab(QWidget):
    changed = Signal()

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self._params = params
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._enabled = QCheckBox("활성화")
        self._enabled.setChecked(params.enabled)
        self._enabled.toggled.connect(self._emit)
        form.addRow(self._enabled)

        self._radius = _slider(3, 60, params.smoothing_radius)
        self._radius.valueChanged.connect(self._emit)
        form.addRow("스무딩 반경:", self._radius)

        self._crop = _slider(1, 15, int(params.crop_ratio * 100))
        self._crop.valueChanged.connect(self._emit)
        form.addRow("크롭 비율(%):", self._crop)

        lbl = QLabel("⚠ 안정화는 순차 재생 시 적용됩니다 (탐색 시 리셋)")
        lbl.setStyleSheet("color:#f90; font-size:10px;")
        lbl.setWordWrap(True)
        form.addRow(lbl)

    def _emit(self):
        p = self._params
        p.enabled = self._enabled.isChecked()
        p.smoothing_radius = self._radius.value()
        p.crop_ratio = self._crop.value() / 100.0
        self.changed.emit()


# ──────────────────────────────────────────────────────────────
#  Background Removal tab
# ──────────────────────────────────────────────────────────────

class _BgRemovalTab(QWidget):
    changed = Signal()

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self._params = params
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._enabled = QCheckBox("활성화")
        self._enabled.setChecked(params.enabled)
        self._enabled.toggled.connect(self._emit)
        form.addRow(self._enabled)

        self._method = QComboBox()
        self._method.addItems(["MediaPipe (빠름)", "rembg (고품질)", "자동(폴백)"])
        method_map = {"mediapipe": 0, "rembg": 1, "chroma_auto": 2}
        self._method.setCurrentIndex(method_map.get(params.method, 0))
        self._method.currentIndexChanged.connect(self._emit)
        form.addRow("방식:", self._method)

        self._bg_mode = QComboBox()
        self._bg_mode.addItems(["단색 배경", "블러 배경"])
        self._bg_mode.setCurrentIndex(0 if params.bg_mode == "color" else 1)
        self._bg_mode.currentIndexChanged.connect(self._emit)
        form.addRow("배경 유형:", self._bg_mode)

        self._blur_r = _slider(5, 80, params.bg_blur_radius)
        self._blur_r.valueChanged.connect(self._emit)
        form.addRow("블러 강도:", self._blur_r)

        self._threshold = _pct_slider(params.threshold)
        self._threshold.valueChanged.connect(self._emit)
        form.addRow("감지 임계값:", self._threshold)

        self._feather = _slider(0, 20, params.feather)
        self._feather.valueChanged.connect(self._emit)
        form.addRow("가장자리 부드럽게:", self._feather)

        lbl = QLabel("💡 rembg 사용 시 pip install rembg 필요")
        lbl.setStyleSheet("color:#888; font-size:10px;")
        form.addRow(lbl)

    def _emit(self):
        p = self._params
        p.enabled = self._enabled.isChecked()
        method_list = ["mediapipe", "rembg", "chroma_auto"]
        p.method = method_list[self._method.currentIndex()]
        p.bg_mode = "color" if self._bg_mode.currentIndex() == 0 else "blur"
        p.bg_blur_radius = self._blur_r.value()
        p.threshold = self._threshold.value() / 100.0
        p.feather = self._feather.value()
        self.changed.emit()


# ──────────────────────────────────────────────────────────────
#  Main dialog
# ──────────────────────────────────────────────────────────────

class ClipEffectsDialog(QDialog):
    """Modal inspector for all per-clip video effects."""

    effects_changed = Signal()  # emitted live as sliders move

    def __init__(self, clip, refresh_fn=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("클립 이펙트")
        self.setMinimumWidth(400)
        self._clip = clip
        self._refresh_fn = refresh_fn

        # Ensure effect params exist on clip
        self._ensure_params(clip)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Video Filters tab
        self._filters_tab = _FiltersTab(clip.video_filters)
        self._filters_tab.changed.connect(self._on_changed)
        tabs.addTab(self._filters_tab, "🎨 필터")

        # Chroma Key tab
        self._chroma_tab = _ChromaTab(clip.chroma_key)
        self._chroma_tab.changed.connect(self._on_changed)
        tabs.addTab(self._chroma_tab, "🟩 크로마키")

        # Stabilizer tab
        self._stab_tab = _StabTab(clip.stabilizer)
        self._stab_tab.changed.connect(self._on_changed)
        tabs.addTab(self._stab_tab, "📷 안정화")

        # Background Removal tab
        self._bg_tab = _BgRemovalTab(clip.bg_removal)
        self._bg_tab.changed.connect(self._on_changed)
        tabs.addTab(self._bg_tab, "🤖 배경 제거")

        # Close button
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        layout.addWidget(btns)

    @staticmethod
    def _ensure_params(clip) -> None:
        """Create default effect param objects on the clip if missing."""
        if getattr(clip, "video_filters", None) is None:
            try:
                from app.video_filters import VideoFilterParams
                clip.video_filters = VideoFilterParams()
            except ImportError:
                pass
        if getattr(clip, "chroma_key", None) is None:
            try:
                from app.chroma_key import ChromaKeyParams
                clip.chroma_key = ChromaKeyParams()
            except ImportError:
                pass
        if getattr(clip, "stabilizer", None) is None:
            try:
                from app.video_stabilizer import StabilizerParams
                clip.stabilizer = StabilizerParams()
            except ImportError:
                pass
        if getattr(clip, "bg_removal", None) is None:
            try:
                from app.background_removal import BackgroundRemovalParams
                clip.bg_removal = BackgroundRemovalParams()
            except ImportError:
                pass

    def _on_changed(self) -> None:
        self.effects_changed.emit()
        if self._refresh_fn is not None:
            try:
                self._refresh_fn()
            except Exception:
                pass
