"""Modal dialogs for node-mask configuration.

Phase E ships three editors:

- :class:`HSLQualifierDialog` — H/S/L range sliders + softness +
  invert. Eyedropper-from-preview is a Phase E follow-up; for now
  the user dials in numerically.
- :class:`MagicMaskDialog` — pick a feature (lips / left_eye /
  right_eye / face / person) + soften / expand / invert. Mediapipe
  drives the actual detection at render time when present, falling
  back to an OpenCV cascade when not.
- :class:`PowerWindowDialog` — softness + invert + "edit on preview"
  hint. The actual polygon point editor lives in the main editor
  (preview overlay) since it needs the player frame.

All dialogs operate **in place** on the mask object — the caller
hands in a mask, the dialog mutates its fields. ``QDialog.Accepted``
indicates the user confirmed; ``Rejected`` means the caller should
revert (the mask hasn't been added to the node yet) or delete (when
removing).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.node_mask import (
    HSLQualifier,
    MagicMask,
    PowerWindow,
)


def _slider_row(parent: QWidget, label: str, vmin: int, vmax: int, value: int):
    """Build a labelled QSlider + value readout. Returns (slider, layout)."""
    row = QHBoxLayout()
    lab = QLabel(label, parent)
    lab.setMinimumWidth(80)
    sld = QSlider(Qt.Orientation.Horizontal, parent)
    sld.setRange(vmin, vmax)
    sld.setValue(value)
    val = QLabel(str(value), parent)
    val.setMinimumWidth(40)
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    sld.valueChanged.connect(lambda v: val.setText(str(v)))
    row.addWidget(lab)
    row.addWidget(sld, stretch=1)
    row.addWidget(val)
    return sld, row


# ---------------------------------------------------------------------------
# HSL Qualifier
# ---------------------------------------------------------------------------


class HSLQualifierDialog(QDialog):
    """Edit an :class:`HSLQualifier` in place. Live-updates the mask
    on every slider tick so the preview reflects the changes
    immediately (the editor's render pipeline reads the mask via
    its reference)."""

    def __init__(self, mask: HSLQualifier, on_change=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("nodemask.hsl.title"))
        self.setMinimumWidth(420)
        self._mask = mask
        self._on_change = on_change

        root = QVBoxLayout(self)

        # Hue range — degrees. h_min may be > h_max for wrap.
        self.h_min, hm_row = _slider_row(self, tr("nodemask.hsl.h_min"), 0, 360, int(mask.h_min))
        self.h_max, hM_row = _slider_row(self, tr("nodemask.hsl.h_max"), 0, 360, int(mask.h_max))
        # Sat / Lum — scaled int [0, 100] for slider; convert on change.
        self.s_min, sm_row = _slider_row(self, tr("nodemask.hsl.s_min"), 0, 100, int(mask.s_min * 100))
        self.s_max, sM_row = _slider_row(self, tr("nodemask.hsl.s_max"), 0, 100, int(mask.s_max * 100))
        self.l_min, lm_row = _slider_row(self, tr("nodemask.hsl.l_min"), 0, 100, int(mask.l_min * 100))
        self.l_max, lM_row = _slider_row(self, tr("nodemask.hsl.l_max"), 0, 100, int(mask.l_max * 100))
        self.softness, soft_row = _slider_row(self, tr("nodemask.hsl.softness"), 0, 20, int(mask.softness * 1000))
        self.denoise = QSpinBox(self)
        self.denoise.setRange(0, 8)
        self.denoise.setValue(int(mask.denoise_radius))

        for r in (hm_row, hM_row, sm_row, sM_row, lm_row, lM_row, soft_row):
            root.addLayout(r)
        denoise_row = QHBoxLayout()
        denoise_row.addWidget(QLabel(tr("nodemask.hsl.denoise"), self))
        denoise_row.addWidget(self.denoise)
        denoise_row.addStretch(1)
        root.addLayout(denoise_row)

        self.invert_chk = QCheckBox(tr("nodemask.invert"), self)
        self.invert_chk.setChecked(mask.invert)
        root.addWidget(self.invert_chk)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        # Wire live updates to the mask object so the preview tracks
        # slider drags. The editor refreshes the player frame in its
        # mask-edit handler.
        for sld in (self.h_min, self.h_max, self.s_min, self.s_max,
                    self.l_min, self.l_max, self.softness):
            sld.valueChanged.connect(self._apply_to_mask)
        self.denoise.valueChanged.connect(self._apply_to_mask)
        self.invert_chk.toggled.connect(self._apply_to_mask)

    def _apply_to_mask(self, *_args) -> None:
        self._mask.h_min = float(self.h_min.value())
        self._mask.h_max = float(self.h_max.value())
        self._mask.s_min = self.s_min.value() / 100.0
        self._mask.s_max = self.s_max.value() / 100.0
        self._mask.l_min = self.l_min.value() / 100.0
        self._mask.l_max = self.l_max.value() / 100.0
        self._mask.softness = self.softness.value() / 1000.0
        self._mask.denoise_radius = int(self.denoise.value())
        self._mask.invert = self.invert_chk.isChecked()
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Magic Mask (feature picker)
# ---------------------------------------------------------------------------


class MagicMaskDialog(QDialog):
    """Edit a :class:`MagicMask` — feature dropdown + soften /
    expand / invert sliders. The renderer picks Mediapipe (when
    installed) or an OpenCV cascade fallback automatically."""

    FEATURES = [
        ("lips", "nodemask.magic.feature.lips"),
        ("face", "nodemask.magic.feature.face"),
        ("left_eye", "nodemask.magic.feature.left_eye"),
        ("right_eye", "nodemask.magic.feature.right_eye"),
        ("person", "nodemask.magic.feature.person"),
    ]

    def __init__(self, mask: MagicMask, on_change=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("nodemask.magic.title"))
        self.setMinimumWidth(380)
        self._mask = mask
        self._on_change = on_change

        root = QFormLayout(self)
        self.feature_cb = QComboBox(self)
        for key, label in self.FEATURES:
            self.feature_cb.addItem(tr(label), key)
        # Pre-select the current feature.
        for i in range(self.feature_cb.count()):
            if self.feature_cb.itemData(i) == mask.feature:
                self.feature_cb.setCurrentIndex(i)
                break
        root.addRow(tr("nodemask.magic.feature"), self.feature_cb)

        self.softness = QSlider(Qt.Orientation.Horizontal, self)
        self.softness.setRange(0, 50)
        self.softness.setValue(int(mask.softness_norm * 1000))
        root.addRow(tr("nodemask.magic.softness"), self.softness)

        self.expand = QSlider(Qt.Orientation.Horizontal, self)
        self.expand.setRange(-30, 30)
        self.expand.setValue(int(mask.expand_norm * 1000))
        root.addRow(tr("nodemask.magic.expand"), self.expand)

        self.invert_chk = QCheckBox(tr("nodemask.invert"), self)
        self.invert_chk.setChecked(mask.invert)
        root.addRow("", self.invert_chk)

        # Tip — engine selection happens automatically.
        tip = QLabel(tr("nodemask.magic.tip"), self)
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        root.addRow(tip)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addRow(bb)

        self.feature_cb.currentIndexChanged.connect(self._apply_to_mask)
        self.softness.valueChanged.connect(self._apply_to_mask)
        self.expand.valueChanged.connect(self._apply_to_mask)
        self.invert_chk.toggled.connect(self._apply_to_mask)

    def _apply_to_mask(self, *_args) -> None:
        self._mask.feature = self.feature_cb.currentData() or "lips"
        self._mask.softness_norm = self.softness.value() / 1000.0
        self._mask.expand_norm = self.expand.value() / 1000.0
        self._mask.invert = self.invert_chk.isChecked()
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Power Window (polygon)
# ---------------------------------------------------------------------------


class PowerWindowDialog(QDialog):
    """Edit a :class:`PowerWindow`'s softness / invert. The polygon
    points are drawn directly on the preview via the editor's
    PowerWindowOverlay (a separate widget that captures mouse events
    over the preview pane). This dialog stays open while the user
    edits the polygon — closing it commits."""

    def __init__(self, mask: PowerWindow, on_change=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("nodemask.window.title"))
        self.setMinimumWidth(360)
        self._mask = mask
        self._on_change = on_change

        root = QFormLayout(self)

        tip = QLabel(tr("nodemask.window.tip"), self)
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        root.addRow(tip)

        self.softness = QSlider(Qt.Orientation.Horizontal, self)
        self.softness.setRange(0, 50)
        self.softness.setValue(int(mask.softness_norm * 1000))
        root.addRow(tr("nodemask.window.softness"), self.softness)

        self.invert_chk = QCheckBox(tr("nodemask.invert"), self)
        self.invert_chk.setChecked(mask.invert)
        root.addRow("", self.invert_chk)

        clear_btn = QPushButton(tr("nodemask.window.clear_points"), self)
        clear_btn.clicked.connect(self._clear_points)
        root.addRow("", clear_btn)

        # Live point count display so the user can confirm their
        # clicks landed before closing the dialog.
        self.points_lbl = QLabel("", self)
        self._refresh_points_label()
        root.addRow(tr("nodemask.window.points"), self.points_lbl)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        root.addRow(bb)

        self.softness.valueChanged.connect(self._apply_to_mask)
        self.invert_chk.toggled.connect(self._apply_to_mask)

    def _apply_to_mask(self, *_args) -> None:
        self._mask.softness_norm = self.softness.value() / 1000.0
        self._mask.invert = self.invert_chk.isChecked()
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass

    def _clear_points(self) -> None:
        self._mask.points.clear()
        self._refresh_points_label()
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass

    def _refresh_points_label(self) -> None:
        n = len(self._mask.points)
        self.points_lbl.setText(tr("nodemask.window.points_count", n=n))

    def refresh_points_count(self) -> None:
        """Called by the editor's overlay after a point is added so
        the dialog's count label updates without the user clicking
        anything in the dialog itself."""
        self._refresh_points_label()
