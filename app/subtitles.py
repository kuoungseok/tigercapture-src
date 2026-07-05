from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size


@dataclass
class Subtitle:
    start_ms: int
    end_ms: int
    text: str
    show_box: bool = True
    style: dict = field(default_factory=dict)

    def contains(self, pos_ms: int) -> bool:
        return self.start_ms <= pos_ms < self.end_ms


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}.{(ms % 1000) // 100}"


class SubtitleEditDialog(QDialog):
    """Modal editor for a single Subtitle. Time is entered in seconds with
    one decimal place for sub-second precision; text is multi-line."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial: Subtitle | None = None,
        max_ms: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("subtitle.edit.title"))
        self.setModal(True)
        self.resize(440, 280)

        max_s = max(1, max_ms // 1000)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(QLabel(tr("subtitle.edit.start")))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, max_s * 10)
        self.start_spin.setSuffix(" · 0.1s")
        time_row.addWidget(self.start_spin)
        time_row.addSpacing(12)
        time_row.addWidget(QLabel(tr("subtitle.edit.end")))
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, max_s * 10)
        self.end_spin.setSuffix(" · 0.1s")
        time_row.addWidget(self.end_spin)
        time_row.addStretch(1)
        root.addLayout(time_row)

        root.addWidget(QLabel(tr("subtitle.edit.text")))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(tr("subtitle.edit.placeholder"))
        root.addWidget(self.text_edit, stretch=1)

        self.box_check = QCheckBox(tr("subtitle.edit.show_box"))
        self.box_check.setChecked(True)
        root.addWidget(self.box_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if initial is not None:
            self.start_spin.setValue(initial.start_ms // 100)
            self.end_spin.setValue(max(initial.end_ms // 100, initial.start_ms // 100 + 1))
            self.text_edit.setPlainText(initial.text)
            self.box_check.setChecked(initial.show_box)
        else:
            self.start_spin.setValue(0)
            self.end_spin.setValue(30)

    def result_subtitle(self) -> Subtitle:
        s = self.start_spin.value() * 100
        e = max(s + 100, self.end_spin.value() * 100)
        return Subtitle(
            start_ms=s,
            end_ms=e,
            text=self.text_edit.toPlainText(),
            show_box=self.box_check.isChecked(),
        )


class SubtitlePanel(QWidget):
    """Compact list of subtitles with add/edit/delete buttons.

    ``position_provider`` is an optional callable returning the current
    playhead position in ms, used to pre-fill the start time when adding
    a new subtitle ("add at current playhead" UX).
    """

    subtitles_changed = Signal()
    # Bubbled by the panel header's pop-out button; the editor connects this
    # to its toggle handler so the panel can detach into a floating
    # window (same dock pattern as colour grading / timeline).
    popout_requested = Signal()
    DEFAULT_DURATION_MS = 4000

    def __init__(self, position_provider=None) -> None:
        super().__init__()
        # Phase 5 Step A: storage moved to ``SubtitleLayer``. The panel
        # is now a UI binding around the layer — editor-side consumers
        # (preview overlay, timeline ruler markers, export) read the
        # layer directly via ``self.layer``. ``self._subtitles`` stays
        # as a property for back-compat with handlers that took the
        # list directly.
        from app.overlay_layer import SubtitleLayer
        self.layer: SubtitleLayer = SubtitleLayer()
        self._max_ms: int = 0
        self._position_provider = position_provider or (lambda: 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._title_label = QLabel(tr("subtitle.section.title"))
        self._title_label.setStyleSheet("font-weight: 600; color: palette(text);")
        header.addWidget(self._title_label)
        header.addStretch(1)

        self.add_btn = QPushButton(tr("subtitle.btn.add"))
        self.add_btn.setObjectName("ToolButton")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._on_add)

        self.edit_btn = QPushButton(tr("subtitle.btn.edit"))
        self.edit_btn.setObjectName("ToolButton")
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self._on_edit)

        self.del_btn = QPushButton(tr("subtitle.btn.delete"))
        self.del_btn.setObjectName("ToolButton")
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.clicked.connect(self._on_delete)

        header.addWidget(self.add_btn)
        header.addWidget(self.edit_btn)
        header.addWidget(self.del_btn)

        self.popout_btn = QPushButton("")
        self.popout_btn.setObjectName("PreviewPopoutIcon")
        self.popout_btn.setIcon(app_icon("popout", size=16))
        self.popout_btn.setIconSize(icon_size(16))
        self.popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popout_btn.setToolTip(tr("subtitle.popout.tooltip"))
        self.popout_btn.setFixedSize(28, 24)
        self.popout_btn.clicked.connect(self.popout_requested.emit)
        header.addWidget(self.popout_btn)
        root.addLayout(header)

        # The list takes all available vertical space — when the user
        # accumulates many subtitles, QListWidget's built-in vertical
        # scroll bar handles the overflow.
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setMinimumHeight(160)
        self._list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._list.itemDoubleClicked.connect(lambda _: self._on_edit())
        root.addWidget(self._list, stretch=1)

    @property
    def _subtitles(self) -> list[Subtitle]:
        """Phase 5 Step A back-compat: a few external callers
        (gif_editor_window, video_editor_window pickling code) still
        treat the panel as if it owned a flat list. Expose the layer's
        contents through a property so those continue to work without
        a sweeping rename."""
        return self.layer.items()

    def subtitles(self) -> list[Subtitle]:
        return self.layer.items()

    def set_project_duration(self, ms: int) -> None:
        self._max_ms = max(0, int(ms))

    def active_subtitle(self, pos_ms: int) -> Subtitle | None:
        return self.layer.first_active_at(pos_ms)

    def _on_add(self) -> None:
        try:
            current_ms = max(0, int(self._position_provider()))
        except Exception:
            current_ms = 0
        seed = Subtitle(
            start_ms=current_ms,
            end_ms=current_ms + self.DEFAULT_DURATION_MS,
            text="",
        )
        dlg = SubtitleEditDialog(self, seed, self._max_ms)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.layer.add(dlg.result_subtitle())
            self._refresh_list()
            self.subtitles_changed.emit()

    def _on_edit(self) -> None:
        idx = self._list.currentRow()
        items = self.layer.items()
        if idx < 0 or idx >= len(items):
            return
        dlg = SubtitleEditDialog(self, items[idx], self._max_ms)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.layer.replace_at(idx, dlg.result_subtitle())
            self._refresh_list()
            self.subtitles_changed.emit()

    def _on_delete(self) -> None:
        idx = self._list.currentRow()
        items = self.layer.items()
        if idx < 0 or idx >= len(items):
            return
        self.layer.remove(items[idx])
        self._refresh_list()
        self.subtitles_changed.emit()

    def _refresh_list(self) -> None:
        self._list.clear()
        for s in self.layer.items():
            preview = s.text.strip().splitlines()[0] if s.text.strip() else "(empty)"
            if len(preview) > 50:
                preview = preview[:47] + "…"
            item = QListWidgetItem(
                f"{_format_ms(s.start_ms)} → {_format_ms(s.end_ms)}   {preview}"
            )
            self._list.addItem(item)

    def retranslate(self) -> None:
        self._title_label.setText(tr("subtitle.section.title"))
        self.add_btn.setText(tr("subtitle.btn.add"))
        self.edit_btn.setText(tr("subtitle.btn.edit"))
        self.del_btn.setText(tr("subtitle.btn.delete"))
        self.popout_btn.setToolTip(tr("subtitle.popout.tooltip"))


# ---------------------------------------------------------------------------
#  Phase 5 Step B: SubtitleLaneRow — DaVinci-style timeline lane
# ---------------------------------------------------------------------------


class SubtitleLaneRow(QWidget):
    """Timeline lane that paints each subtitle as a Tiger Orange
    rectangle and lets the user drag-move / drag-resize / double-click
    them. The lane is laid out alongside ``TrackRow`` widgets in the
    timeline scroll area; same ``MARGIN`` and ``px_per_sec`` so the
    columns line up exactly.

    Subtitle storage is shared with ``SubtitlePanel`` via the
    ``SubtitleLayer`` (Phase 5 Step A). Mutations here propagate to
    the panel + the preview overlay + the ruler markers automatically
    through the layer's ``on_change`` hook.
    """

    LABEL_H = 14                          # matches TrackRow header strip
    LANE_H = 26
    MARGIN = 180                          # matches TrackRow.MARGIN
    EDGE_GRAB_PX = 6
    MIN_DURATION_MS = 200

    request_edit = Signal(int)            # subtitle index — opens dialog

    def __init__(self, layer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.overlay_layer import SubtitleLayer
        self._layer: SubtitleLayer = layer
        self._px_per_sec: float = 40.0
        self._duration_ms: int = 0
        self._selected_idx: int = -1

        # Drag state.
        self._drag_mode: str | None = None         # "move" | "resize_l" | "resize_r"
        self._drag_idx: int = -1
        self._drag_anchor_x: int = 0
        self._drag_orig_start: int = 0
        self._drag_orig_end: int = 0

        # Hover state for edge highlighting.
        self._hover_idx: int = -1
        self._hover_side: str = ""

        # Tighten the gap to the next video track row — removed the
        # legacy 4 px bottom padding so the subtitle drop strip sits
        # flush against TrackRow.LABEL_H. Users were aiming drops at
        # the resulting bottom space and missing.
        self.setFixedHeight(self.LABEL_H + self.LANE_H)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setVisible(bool(self._layer.items()))

        # Layer change → repaint. The chain returned by
        # ``TimelineRuler.set_subtitle_layer`` already wraps any prior
        # ``on_change``; we register here too by chaining once more.
        prior = layer.on_change

        def _composite():
            self.setVisible(bool(self._layer.items()))
            self.update()
            if prior is not None:
                try:
                    prior()
                except Exception:
                    pass
        layer.on_change = _composite

        self._recalc_width()

    # ---- public API ----

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(4.0, min(300.0, float(px)))
        self._recalc_width()
        self.update()

    def set_project_duration(self, ms: int) -> None:
        self._duration_ms = max(0, int(ms))
        self._recalc_width()
        self.update()

    def selected_index(self) -> int:
        return self._selected_idx

    # ---- coords ----

    def _ms_to_x(self, ms: int) -> int:
        return int(self.MARGIN + ms / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _sub_rect(self, s: Subtitle) -> QRect:
        x1 = self._ms_to_x(s.start_ms)
        x2 = self._ms_to_x(s.end_ms)
        return QRect(x1, self.LABEL_H, max(2, x2 - x1), self.LANE_H)

    def _hit_test(self, pos) -> tuple[int, str]:
        """Return ``(subtitle_index, edge)`` where edge is "left",
        "right", or "" (body). Returns ``(-1, "")`` when the cursor
        isn't over any subtitle."""
        for i, sub in enumerate(self._layer.items()):
            r = self._sub_rect(sub)
            if not r.contains(pos):
                continue
            x = pos.x()
            if x - r.left() < self.EDGE_GRAB_PX:
                return i, "left"
            if r.right() - x < self.EDGE_GRAB_PX:
                return i, "right"
            return i, ""
        return -1, ""

    # ---- sizing ----

    def _recalc_width(self) -> None:
        end_ms = max(self._duration_ms, 30_000)
        for sub in self._layer.items():
            if sub.end_ms > end_ms:
                end_ms = sub.end_ms
        w = int(end_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
        self.setFixedWidth(max(300, w))

    # ---- painting ----

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        label_col = QRect(0, 0, self.MARGIN, self.height())
        p.fillRect(label_col, QColor("#151515"))
        p.setPen(QColor("#2B2B2B"))
        p.drawLine(self.MARGIN - 1, 0, self.MARGIN - 1, self.height())
        p.save()
        label_font = QFont(p.font())
        label_font.setPixelSize(10)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QColor("#CFCFCF"))
        label_y = self.LABEL_H + max(0, (self.LANE_H - 16) // 2)
        p.drawText(
            QRect(12, label_y, 26, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "S1",
        )
        label_font.setPixelSize(9)
        label_font.setBold(False)
        p.setFont(label_font)
        p.setPen(QColor("#858585"))
        p.drawText(
            QRect(56, label_y, self.MARGIN - 70, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tr("subtitle.lane.label"),
        )
        p.restore()
        # Lane backing strip — slightly darker than the timeline host
        # so empty subtitle space reads as a track.
        lane_rect = QRect(
            self.MARGIN, self.LABEL_H,
            max(0, self.width() - 2 * self.MARGIN), self.LANE_H,
        )
        # 80% brightness stripe — same as empty video track
        from app.timeline_striped_host import StripedHost
        StripedHost._draw_stripes(p, lane_rect, StripedHost.BG_80, StripedHost.STRIPE_80)
        # Subtitle rectangles.
        f = QFont(p.font())
        f.setPixelSize(11)
        p.setFont(f)
        fm = p.fontMetrics()
        for i, sub in enumerate(self._layer.items()):
            r = self._sub_rect(sub)
            is_selected = i == self._selected_idx
            fill = QColor("#D85A30") if not is_selected else QColor("#ff7a4a")
            p.fillRect(r, fill)
            border = QPen(
                QColor("#ffffff" if is_selected else "#a03020"),
                2 if is_selected else 1,
            )
            p.setPen(border)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(0, 0, -1, -1))
            # Edge handles on hover.
            if i == self._hover_idx:
                handle_pen = QPen(QColor("#ffffff"), 2)
                p.setPen(handle_pen)
                if self._hover_side == "left":
                    p.drawLine(r.left() + 1, r.top() + 2, r.left() + 1, r.bottom() - 2)
                elif self._hover_side == "right":
                    p.drawLine(r.right() - 1, r.top() + 2, r.right() - 1, r.bottom() - 2)
            # Label, truncated to fit the rect.
            label = sub.text.strip().splitlines()[0] if sub.text.strip() else "—"
            avail = max(0, r.width() - 8)
            elided = fm.elidedText(label, Qt.TextElideMode.ElideRight, avail)
            p.setPen(QColor("#ffffff"))
            p.drawText(
                r.adjusted(4, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided,
            )
        p.end()

    # ---- mouse ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        idx, side = self._hit_test(pos)
        if idx < 0:
            self._selected_idx = -1
            self.update()
            return
        self._selected_idx = idx
        sub = self._layer.items()[idx]
        self._drag_idx = idx
        self._drag_anchor_x = pos.x()
        self._drag_orig_start = sub.start_ms
        self._drag_orig_end = sub.end_ms
        self._drag_mode = (
            "resize_l" if side == "left"
            else "resize_r" if side == "right"
            else "move"
        )
        self.setCursor(
            Qt.CursorShape.SizeHorCursor if side
            else Qt.CursorShape.ClosedHandCursor
        )
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._drag_mode is None:
            # Hover update — drives edge-handle highlighting.
            idx, side = self._hit_test(pos)
            if idx != self._hover_idx or side != self._hover_side:
                self._hover_idx = idx
                self._hover_side = side
                self._update_cursor_for_hover(side)
                self.update()
            return

        delta_ms = (
            int((pos.x() - self._drag_anchor_x) / max(1.0, self._px_per_sec) * 1000)
        )
        items = self._layer.items()
        if self._drag_idx < 0 or self._drag_idx >= len(items):
            self._drag_mode = None
            return
        sub = items[self._drag_idx]

        if self._drag_mode == "move":
            new_start = max(0, self._drag_orig_start + delta_ms)
            new_start = self._snap_subtitle_start(sub, new_start)
            length = self._drag_orig_end - self._drag_orig_start
            sub.start_ms = new_start
            sub.end_ms = new_start + length
        elif self._drag_mode == "resize_l":
            new_start = max(0, self._drag_orig_start + delta_ms)
            new_start = min(new_start, sub.end_ms - self.MIN_DURATION_MS)
            sub.start_ms = new_start
        elif self._drag_mode == "resize_r":
            new_end = max(
                sub.start_ms + self.MIN_DURATION_MS,
                self._drag_orig_end + delta_ms,
            )
            sub.end_ms = new_end
        # Bypass on_change to avoid resorting + listener flood during
        # the drag — fire it once on release.
        self._recalc_width()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_mode is not None:
            # Re-sort the layer by start_ms (drag may have re-ordered)
            # and notify listeners so the panel list / ruler markers
            # / preview overlay all refresh.
            self._layer.replace_all(self._layer.items())
            self._drag_mode = None
            self._drag_idx = -1
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        idx, _ = self._hit_test(event.position().toPoint())
        if idx >= 0:
            self.request_edit.emit(idx)

    def leaveEvent(self, _event) -> None:
        if self._hover_idx != -1:
            self._hover_idx = -1
            self._hover_side = ""
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()

    # ---- helpers ----

    def _snap_subtitle_start(self, sub, desired_start: int) -> int:
        """Snap the dragged subtitle's start to project ms 0 or any
        other subtitle's start/end within an 8 px tolerance. Subtitles
        are allowed to overlap (translations / dual-language tracks),
        so unlike clip drag this doesn't do collision clamping."""
        snap_px = 8
        snap_ms = max(40, int(snap_px / max(1.0, self._px_per_sec) * 1000))
        targets = [0]
        for other in self._layer.items():
            if other is sub:
                continue
            targets.append(other.start_ms)
            targets.append(other.end_ms)
        best = None
        best_d = snap_ms + 1
        for t in targets:
            d = abs(t - desired_start)
            if d < best_d:
                best_d = d
                best = t
        return best if best is not None else desired_start

    def _update_cursor_for_hover(self, side: str) -> None:
        if side in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif self._hover_idx >= 0:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
