from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_BG_L3,
    COLOR_BG_L4,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)
from app.timeline_model import ZoomActor
from app.typo_layout import (
    aligned_line_origin,
    background_rect_for_block,
    clamp_opacity,
    glyph_pivot,
    make_text_preview_font,
    measure_text_block,
    resolve_text_fill_color,
)
from app.typography import TextClip
from app.video_track_legacy import VideoTrack

__all__ = [
    "TypographyEditorDialog",
    "ZoomActorDialog",
    "_AnimationPickerButton",
    "_FontPickerButton",
    "_FontPickerDelegate",
    "_PresetPickerButton",
    "_PreviewView",
    "_TextPreviewItem",
    "_ZoomRegionPicker",
]

class _TextPreviewItem:
    """Lightweight QGraphicsItem that paints a TextClip preview.

    Implemented via composition with a QGraphicsRectItem so we don't
    need to subclass QGraphicsItem (which is awkward in PySide6 because
    the abstract methods make instantiation finicky).

    ``bg_provider`` is a zero-arg callable returning a QPixmap to paint
    behind the text (the editor uses this to show the video frame at the
    current playhead). Returning ``None`` falls back to a solid black
    backdrop."""

    def __init__(self, clip: TextClip, bg_provider=None, time_provider=None):
        from PySide6.QtWidgets import QGraphicsRectItem
        self.clip = clip
        self._bg_provider = bg_provider
        # ``time_provider`` returns the current playback time (seconds
        # since the clip's start) used to drive the IN/HOLD/OUT
        # animation. Returning ``None`` means "show the static
        # final-state result" (i.e. no animation applied).
        self._time_provider = time_provider

        self._root = QGraphicsRectItem(0, 0, 1920, 1080)
        from PySide6.QtGui import QBrush
        self._root.setBrush(QBrush(QColor("#000")))
        self._root.setPen(QPen(Qt.PenStyle.NoPen))

        # Custom paint via overriding paint() on the rect item ??easiest
        # cross-version Qt path.
        original_paint = self._root.paint

        def _paint(painter, option, widget=None):
            original_paint(painter, option, widget)
            self._draw_background(painter)
            self._draw_text(painter)

        self._root.paint = _paint

    def graphics_item(self):
        return self._root

    def refresh(self):
        self._root.update()

    def _draw_background(self, painter: QPainter) -> None:
        if self._bg_provider is None:
            return
        try:
            pm = self._bg_provider()
        except Exception:
            return
        if pm is None or pm.isNull():
            return
        scene_w, scene_h = 1920.0, 1080.0
        pw, ph = pm.width(), pm.height()
        if pw <= 0 or ph <= 0:
            return
        scale = min(scene_w / pw, scene_h / ph)
        draw_w = pw * scale
        draw_h = ph * scale
        ox = (scene_w - draw_w) / 2.0
        oy = (scene_h - draw_h) / 2.0
        painter.drawPixmap(int(ox), int(oy), int(draw_w), int(draw_h), pm)

    def _draw_text(self, painter: QPainter) -> None:
        from PySide6.QtGui import QFontMetrics, QPainterPath
        from app.typo_animations import (
            compute_clip_transform, compute_clip_glyph_transforms,
            compute_clip_layers, TextTransform,
        )
        clip = self.clip
        text = clip.text or "Enter text"
        style = clip.style

        scene_w, scene_h = 1920.0, 1080.0
        cx = float(style.position_x) * scene_w
        cy = float(style.position_y) * scene_h

        # Resolve play time; ``None`` = paused (steady HOLD state).
        play_time = None
        if self._time_provider is not None:
            play_time = self._time_provider()

        # Multi-layer dispatch (RGB split / glitch animations) ??drawn
        # once per layer with each layer's color + offset.
        if play_time is not None:
            layers = compute_clip_layers(clip, float(play_time))
            if layers is not None:
                self._draw_text_layers(painter, text, style, cx, cy, layers)
                return

        # Per-glyph dispatch: if the active animation is per-glyph,
        # rendering branches into a different path that iterates each
        # character with its own transform around its own pivot.
        glyph_xfs = None
        if play_time is not None:
            glyph_xfs = compute_clip_glyph_transforms(
                clip, float(play_time), len(text or "")
            )
        if glyph_xfs is not None:
            self._draw_text_perglyph(painter, text, style, cx, cy, glyph_xfs)
            return

        # Whole-text fast path.
        if play_time is not None:
            xf = compute_clip_transform(clip, float(play_time)) or TextTransform.identity()
        else:
            xf = TextTransform.identity()

        # Apply opacity globally for the text drawing block; geometric
        # transform pivots on the text's center (cx, cy).
        painter.save()
        painter.setOpacity(clamp_opacity(xf.opacity))
        painter.translate(cx + xf.offset_x, cy + xf.offset_y)
        if abs(xf.rotation_deg) > 0.05:
            painter.rotate(xf.rotation_deg)
        if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
            painter.scale(xf.scale_x, xf.scale_y)
        painter.translate(-cx, -cy)

        font = make_text_preview_font(style)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Multi-line: split on newlines, render line-by-line.
        layout = measure_text_block(text, fm, float(style.line_height), cx, cy)

        # Background rect
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(*background_rect_for_block(layout, pad), radius, radius)

        # For each line: shadow ??outline ??fill
        for i, ln in enumerate(layout.lines):
            ln_w = fm.horizontalAdvance(ln)
            # Honor alignment within the bounding block.
            lx, ly = aligned_line_origin(layout, ln_w, i, fm.ascent(), style.alignment)

            # Shadow
            if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                painter.setPen(QColor(style.shadow_color))
                painter.drawText(
                    int(lx + style.shadow_offset_x),
                    int(ly + style.shadow_offset_y),
                    ln,
                )

            # Outline
            if style.outline_color and style.outline_width and style.outline_width > 0:
                path = QPainterPath()
                path.addText(lx, ly, font, ln)
                pen = QPen(QColor(style.outline_color))
                pen.setWidth(int(style.outline_width))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            # Fill
            painter.setPen(QColor(resolve_text_fill_color(style.color)))
            painter.drawText(int(lx), int(ly), ln)

        # Close the save() that opened the animation transform block.
        painter.restore()

    def _draw_text_perglyph(
        self, painter: QPainter, text: str, style, cx: float, cy: float,
        glyph_xfs: list,
    ) -> None:
        """Render a Folding-style per-glyph animation. Each char gets
        its own transform around its own pivot. Effects (shadow /
        outline / fill) are drawn per-character so rotation pivots
        stay correct."""
        from PySide6.QtGui import QFontMetrics, QPainterPath

        font = make_text_preview_font(style)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Lay out chars by line (multi-line text ??newlines split).
        # Per-glyph animations don't make as much sense for multi-line,
        # but we still place them sensibly.
        layout = measure_text_block(text, fm, float(style.line_height), cx, cy)

        # Background rect (drawn once, behind every glyph)
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(*background_rect_for_block(layout, pad), radius, radius)

        # Walk every char in order, mapping it to the i-th transform.
        # Newlines bump the cursor to the next line and don't consume
        # an entry from glyph_xfs (the animation generator received the
        # full character count including \n; we just skip the visible
        # render for \n). Keep the indices aligned by iterating with i.
        char_idx = 0
        for line_no, ln in enumerate(layout.lines):
            ln_w = fm.horizontalAdvance(ln)
            lx, ly = aligned_line_origin(layout, ln_w, line_no, fm.ascent(), style.alignment)

            cursor_x = lx
            for ch in ln:
                gx = cursor_x
                gw = fm.horizontalAdvance(ch)
                if char_idx >= len(glyph_xfs):
                    xf = glyph_xfs[-1] if glyph_xfs else None
                else:
                    xf = glyph_xfs[char_idx]
                char_idx += 1

                if xf is None or ch.strip() == "":
                    # Whitespace still advances the cursor but we don't
                    # bother drawing.
                    cursor_x += gw
                    continue

                # pivot_y: 0=top of glyph (above baseline), 1=bottom.
                # baseline is at ly; ascent above, descent below.
                pivot_px_x, pivot_px_y = glyph_pivot(
                    gx, gw, ly, fm.ascent(), fm.height(), xf.pivot_x, xf.pivot_y
                )

                painter.save()
                painter.setOpacity(clamp_opacity(xf.opacity))
                painter.translate(
                    pivot_px_x + xf.offset_x,
                    pivot_px_y + xf.offset_y,
                )
                if abs(xf.rotation_deg) > 0.05:
                    painter.rotate(xf.rotation_deg)
                if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
                    painter.scale(xf.scale_x, xf.scale_y)
                painter.translate(-pivot_px_x, -pivot_px_y)

                # Shadow (per char)
                if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                    painter.setPen(QColor(style.shadow_color))
                    painter.drawText(
                        int(gx + style.shadow_offset_x),
                        int(ly + style.shadow_offset_y),
                        ch,
                    )

                # Outline
                if style.outline_color and style.outline_width and style.outline_width > 0:
                    path = QPainterPath()
                    path.addText(gx, ly, font, ch)
                    pen = QPen(QColor(style.outline_color))
                    pen.setWidth(int(style.outline_width))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)

                # Fill ??honor color override if the glyph carries one,
                # unless the user has locked the clip to a single color.
                fill_color = resolve_text_fill_color(
                    style.color,
                    xf.color_override,
                    mono=bool(getattr(self.clip.animation, "mono_color", False)),
                )
                painter.setPen(QColor(fill_color))
                painter.drawText(int(gx), int(ly), ch)

                painter.restore()
                cursor_x += gw
            # Skip the implicit \n character index when there are
            # multiple lines ??the global character count we pass to
            # the animation generator includes \n delimiters.
            if line_no < len(layout.lines) - 1:
                char_idx += 1

    def _draw_text_layers(
        self, painter: QPainter, text: str, style, cx: float, cy: float,
        layers: list,
    ) -> None:
        """Multi-layer rendering ??re-draws the entire text once per
        LayerTransform (different colour + offset). Used by glitch /
        RGB-split style animations."""
        from PySide6.QtGui import QFontMetrics, QPainterPath

        font = make_text_preview_font(style)
        painter.setFont(font)
        fm = QFontMetrics(font)

        layout = measure_text_block(text, fm, float(style.line_height), cx, cy)

        # Background rect drawn once (under all layers).
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(*background_rect_for_block(layout, pad), radius, radius)

        # Iterate layers back-to-front. Mono-color flag forces every
        # layer to honor style.color (effectively collapsing the RGB
        # split ??useful when users want the glitch motion without
        # the chromatic aberration).
        mono = bool(getattr(self.clip.animation, "mono_color", False))
        for layer in layers:
            painter.save()
            painter.setOpacity(clamp_opacity(layer.opacity))
            painter.translate(layer.offset_x, layer.offset_y)

            fill_color = resolve_text_fill_color(style.color, layer.color_override, mono=mono)

            for i, ln in enumerate(layout.lines):
                ln_w = fm.horizontalAdvance(ln)
                lx, ly = aligned_line_origin(layout, ln_w, i, fm.ascent(), style.alignment)

                # Outline only on the topmost layer (last iteration)
                # so the chromatic split stays visible underneath.
                is_top = layer is layers[-1]
                if is_top and style.outline_color and style.outline_width and style.outline_width > 0:
                    path = QPainterPath()
                    path.addText(lx, ly, font, ln)
                    pen = QPen(QColor(style.outline_color))
                    pen.setWidth(int(style.outline_width))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)

                painter.setPen(QColor(fill_color))
                painter.drawText(int(lx), int(ly), ln)

            painter.restore()


class _PreviewView(QScrollArea):
    """Wraps a QGraphicsView; re-fits scene to view on resize."""

    def __init__(self):
        from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        self._scene = QGraphicsScene(0, 0, 1920, 1080)
        from PySide6.QtGui import QBrush
        self._scene.setBackgroundBrush(QBrush(QColor("#000")))
        self._gview = QGraphicsView(self._scene)
        self._gview.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._gview.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self._gview.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._gview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gview.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gview.setStyleSheet("QGraphicsView { background-color: #000; border: none; }")
        self.setWidget(self._gview)

    def add_item(self, item):
        self._scene.addItem(item)

    def fit(self):
        self._gview.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit()


class _FontPickerDelegate:
    """Item delegate factory for the font list. Each row shows the
    family name in the default UI font (so users can read the name
    even when the font itself has no Latin glyphs), plus a sample
    string rendered IN the actual font."""

    SAMPLE_TEXT = "Aa Bb ?쒓? 1234"
    ROW_HEIGHT = 40

    @classmethod
    def install(cls, list_widget) -> None:
        """Attach a QStyledItemDelegate on the given QListWidget."""
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QStyledItemDelegate, QStyle

        class _Delegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                painter.save()
                family = index.data(Qt.ItemDataRole.DisplayRole) or ""
                kind = index.data(Qt.ItemDataRole.UserRole) or "font"

                # Background
                if option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(option.rect, QColor(COLOR_ACCENT_BLUE))
                    name_color = QColor(COLOR_TEXT_PRIMARY)
                    sample_color = QColor(COLOR_TEXT_PRIMARY)
                else:
                    painter.fillRect(option.rect, QColor(COLOR_BG_L4))
                    name_color = QColor(COLOR_TEXT_TERTIARY)
                    sample_color = QColor(COLOR_TEXT_PRIMARY)

                if kind == "header":
                    # Section header (non-selectable)
                    f = QFont()
                    f.setBold(True)
                    f.setPointSize(8)
                    painter.setFont(f)
                    painter.setPen(QColor(COLOR_TEXT_TERTIARY))
                    painter.drawText(
                        option.rect.adjusted(10, 0, -8, 0),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        family,
                    )
                    painter.restore()
                    return

                # Top line: family name in the default UI font (small).
                name_font = QFont()
                name_font.setPointSize(8)
                painter.setFont(name_font)
                painter.setPen(name_color)
                painter.drawText(
                    option.rect.adjusted(10, 3, -8, 0),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    family,
                )

                # Bottom line: sample text rendered in this font.
                sample_font = QFont(family, 12)
                painter.setFont(sample_font)
                painter.setPen(sample_color)
                painter.drawText(
                    option.rect.adjusted(10, 16, -8, -3),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    _FontPickerDelegate.SAMPLE_TEXT,
                )
                painter.restore()

            def sizeHint(self, option, index):
                kind = index.data(Qt.ItemDataRole.UserRole)
                if kind == "header":
                    return QSize(200, 22)
                return QSize(200, _FontPickerDelegate.ROW_HEIGHT)

        delegate = _Delegate(list_widget)
        list_widget.setItemDelegate(delegate)
        # Keep a reference so the delegate isn't GC'd when our caller
        # returns ??Qt only takes a weak handle.
        list_widget._delegate_ref = delegate


class _FontPickerButton(QWidget):
    """Compact font picker: a button that shows the current family
    rendered in its own typeface, plus a ??chevron. Clicking opens a
    popup frame (anchored below the button) with a search field and
    the same scrollable list used in the previous implementation.
    Selection commits the change and closes the popup."""

    font_changed = Signal(str)

    PINNED_FONTS = (
        "Pretendard",
        "Noto Sans KR",
        "Noto Serif KR",
        "Nanum Myeongjo",
        "Gaegu",
        "Noto Sans JP",
        "Noto Serif JP",
        "Shippori Mincho",
        "Arial",
        "Segoe UI",
        "Impact",
    )

    def __init__(self, current_family: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._family = current_family
        self._popup: QWidget | None = None
        self._list = None
        self._search = None

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setObjectName("FontPickerBtn")
        self._btn.setMinimumHeight(36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

        self._update_btn_label()

    def current_family(self) -> str:
        return self._family

    def set_family(self, family: str) -> None:
        if family != self._family:
            self._family = family
            self._update_btn_label()

    def _update_btn_label(self) -> None:
        f = QFont(self._family, 11)
        self._btn.setFont(f)
        self._btn.setStyleSheet(
            f"QPushButton#FontPickerBtn {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 6px 10px; text-align: left; }}"
            f"QPushButton#FontPickerBtn:hover {{ border-color: #6a6a72; }}"
        )
        # Right-arrow chevron at the right edge.
        self._btn.setText(f"{self._family}     >")

    # ---- popup ----

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        from PySide6.QtCore import QTimer
        if self._popup is None:
            self._build_popup()
        # Position the popup just below the button, matching its width
        # (with a sensible minimum so the list is usable).
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 320)
        self._popup.resize(target_w, 380)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()
        QTimer.singleShot(0, self._scroll_to_current)

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import QFrame, QLineEdit, QListWidget, QListWidgetItem
        from PySide6.QtGui import QFontDatabase

        # WindowType.Popup makes the frame auto-dismiss on outside
        # clicks and not steal focus from its parent dialog.
        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("FontPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#FontPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.font_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_BG_L4}; "
            f"color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        _FontPickerDelegate.install(self._list)
        v.addWidget(self._list, 1)

        # Populate
        available = set(QFontDatabase.families())
        used: set[str] = set()
        pinned = [f for f in self.PINNED_FONTS if f in available]
        if pinned:
            hdr = QListWidgetItem(tr("veditor.typo_editor.font_recommended"))
            hdr.setData(Qt.ItemDataRole.UserRole, "header")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(hdr)
            for fam in pinned:
                used.add(fam)
                it = QListWidgetItem(fam)
                self._list.addItem(it)
                if fam == self._family:
                    self._list.setCurrentItem(it)
        all_hdr = QListWidgetItem(tr("veditor.typo_editor.font_all"))
        all_hdr.setData(Qt.ItemDataRole.UserRole, "header")
        all_hdr.setFlags(Qt.ItemFlag.NoItemFlags)
        self._list.addItem(all_hdr)
        for fam in sorted(available):
            if fam in used:
                continue
            it = QListWidgetItem(fam)
            self._list.addItem(it)
            if fam == self._family:
                self._list.setCurrentItem(it)

        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(self._on_item_clicked)

    def _on_item_clicked(self, item) -> None:
        if item is None:
            return
        if item.data(Qt.ItemDataRole.UserRole) == "header":
            return
        self._family = item.text()
        self._update_btn_label()
        if self._popup is not None:
            self._popup.hide()
        self.font_changed.emit(self._family)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        for i in range(self._list.count()):
            it = self._list.item(i)
            kind = it.data(Qt.ItemDataRole.UserRole)
            if kind == "header":
                it.setHidden(bool(needle))
                continue
            it.setHidden(bool(needle) and needle not in it.text().lower())

    def _scroll_to_current(self) -> None:
        if self._list is None:
            return
        cur = self._list.currentItem()
        if cur is not None:
            self._list.scrollToItem(
                cur, self._list.ScrollHint.PositionAtCenter,
            )

class _AnimationPickerButton(QWidget):
    """Compact animation picker ??button shows the current animation's
    name + icon, click opens a popup with category tabs and a 3-column
    tile grid. Scales for the 50+ presets coming in Phase 4."""

    animation_changed = Signal(str)        # animation id

    CATEGORIES = ("basic", "kinetic", "folding", "hold")     # extended in Phase 4

    def __init__(self, current_id: str, direction: str,
                 parent: QWidget | None = None,
                 extras_mode: bool = False) -> None:
        super().__init__(parent)
        self._direction = direction        # "in" / "out" / "hold"
        self._current_id = current_id
        self._popup: QWidget | None = None
        # In extras mode the button never reflects the picked animation
        # ??it stays as a "+ Add modifier" trigger and emits the signal
        # so the parent can append to its extras list.
        self._extras_mode = bool(extras_mode)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setObjectName("AnimPickerBtn")
        self._btn.setMinimumHeight(36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

        self._update_btn_label()

    def current_id(self) -> str:
        return self._current_id

    def set_current(self, anim_id: str) -> None:
        if anim_id != self._current_id:
            self._current_id = anim_id
            self._update_btn_label()

    def _update_btn_label(self) -> None:
        if self._extras_mode:
            self._btn.setText("  + " + tr("veditor.typo_editor.modifier.add"))
            self._btn.setMinimumHeight(28)
            self._btn.setStyleSheet(
                f"QPushButton#AnimPickerBtn {{ "
                f"background-color: transparent; color: {COLOR_TEXT_TERTIARY}; "
                f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
                f"padding: 4px 10px; text-align: left; font-size: 11px; }}"
                f"QPushButton#AnimPickerBtn:hover {{ "
                f"border-color: #6a6a72; color: {COLOR_TEXT_PRIMARY}; }}"
            )
            return
        from app.typo_animations import get_animation
        anim = get_animation(self._current_id)
        name = tr(anim.name_key)
        self._btn.setText(f" {anim.icon}   {name}     >")
        self._btn.setStyleSheet(
            f"QPushButton#AnimPickerBtn {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 6px 10px; text-align: left; font-size: 12px; }}"
            f"QPushButton#AnimPickerBtn:hover {{ border-color: #6a6a72; }}"
        )

    # ---- popup ----

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 460)
        self._popup.resize(target_w, 360)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import (
            QFrame, QLineEdit, QTabWidget, QScrollArea, QGridLayout,
        )
        from app.typo_animations import REGISTRY

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("AnimPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#AnimPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.anim_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 4px; top: -1px; }}"
            f"QTabBar::tab {{ background: {COLOR_BG_L4}; color: {COLOR_TEXT_SECONDARY}; "
            f"padding: 6px 12px; border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        v.addWidget(self._tabs, 1)

        # All-tab + per-category tabs
        self._tile_buttons: list = []  # references to keep them alive
        # "All" tab first ??flat grid
        self._add_tab(
            tr("veditor.typo_editor.anim_cat.all"),
            [a for a in REGISTRY.values()
             if a.direction in (self._direction, "any")],
        )
        for cat in self.CATEGORIES:
            anims = [
                a for a in REGISTRY.values()
                if a.category == cat
                and a.direction in (self._direction, "any")
            ]
            if anims:
                self._add_tab(tr(f"veditor.typo_editor.anim_cat.{cat}"), anims)

    def _add_tab(self, label: str, anims: list) -> None:
        from PySide6.QtWidgets import (
            QScrollArea, QGridLayout,
        )
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        scroll.setWidget(grid_host)

        cols = 3
        for idx, anim in enumerate(anims):
            tile = self._make_tile(anim)
            grid.addWidget(tile, idx // cols, idx % cols)
            self._tile_buttons.append(tile)
        # Spacer at bottom
        grid.setRowStretch(grid.rowCount(), 1)

        self._tabs.addTab(page, label)

    def _make_tile(self, anim) -> QWidget:
        """One animation tile in the grid: bordered box with icon at
        top + name at bottom. Click selects + closes the popup."""
        tile = QPushButton()
        tile.setProperty("anim_id", anim.id)
        tile.setProperty("anim_search", f"{tr(anim.name_key)} {anim.id}")
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumSize(130, 80)
        tile.setMaximumHeight(96)
        is_current = anim.id == self._current_id
        tile.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {COLOR_BG_L4}; "
            f"color: {COLOR_TEXT_PRIMARY}; "
            f"border: 2px solid "
            f"{COLOR_ACCENT_BLUE if is_current else COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; }}"
            f"QPushButton:hover {{ border-color: #6a6a72; "
            f"background-color: #34343c; }}"
        )
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        icon = QLabel(anim.icon)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 28px; background: transparent; "
            f"border: none;"
        )
        layout.addWidget(icon, 1)
        name = QLabel(tr(anim.name_key))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; "
            f"font-weight: 600; background: transparent; border: none;"
        )
        layout.addWidget(name, 0)

        tile.clicked.connect(lambda _c=False, aid=anim.id: self._select(aid))
        return tile

    def _select(self, anim_id: str) -> None:
        if not self._extras_mode:
            self._current_id = anim_id
            self._update_btn_label()
        if self._popup is not None:
            self._popup.hide()
        self.animation_changed.emit(anim_id)

    def _filter(self, text: str) -> None:
        """Hide tiles whose name or id doesn't contain ``text``."""
        needle = text.lower().strip()
        for tile in self._tile_buttons:
            haystack = (tile.property("anim_search") or "").lower()
            tile.setVisible(not needle or needle in haystack)


class _PresetPickerButton(QWidget):
    """Top-of-dialog preset picker. Click ??popup with category tabs +
    tile grid. Selecting a preset emits ``preset_applied(preset_id)``,
    which the dialog uses to overwrite animation + style fields and
    rebuild the editor controls."""

    preset_applied = Signal(str)

    CATEGORIES = ("kinetic", "utaite", "korean", "devila")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._tile_buttons: list = []

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton(tr("veditor.typo_editor.preset_btn"))
        self._btn.setObjectName("PresetPickerBtn")
        self._btn.setMinimumHeight(34)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton#PresetPickerBtn {{ "
            f"background-color: #4a4a4a; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid #5a5a5a; border-radius: 4px; "
            f"padding: 6px 14px; font-weight: 700; font-size: 12px; }}"
            f"QPushButton#PresetPickerBtn:hover {{ "
            f"background-color: #5a5a5a; border-color: #6a6a6a; }}"
        )
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 520)
        self._popup.resize(target_w, 380)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import (
            QFrame, QLineEdit, QTabWidget, QScrollArea, QGridLayout,
        )
        from app.typo_presets import list_presets

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("PresetPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#PresetPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.preset_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 4px; top: -1px; }}"
            f"QTabBar::tab {{ background: {COLOR_BG_L4}; color: {COLOR_TEXT_SECONDARY}; "
            f"padding: 6px 12px; border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        v.addWidget(self._tabs, 1)

        # All tab + per-category
        self._add_tab(tr("veditor.typo_editor.preset_cat.all"), list_presets())
        for cat in self.CATEGORIES:
            anims = list_presets(cat)
            if anims:
                self._add_tab(tr(f"veditor.typo_editor.preset_cat.{cat}"), anims)

    def _add_tab(self, label: str, presets: list) -> None:
        from PySide6.QtWidgets import QScrollArea, QGridLayout

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        scroll.setWidget(grid_host)

        cols = 3
        for idx, preset in enumerate(presets):
            tile = self._make_tile(preset)
            grid.addWidget(tile, idx // cols, idx % cols)
            self._tile_buttons.append(tile)
        grid.setRowStretch(grid.rowCount(), 1)
        self._tabs.addTab(page, label)

    def _make_tile(self, preset) -> QWidget:
        tile = QPushButton()
        # Search payload: name + reference + id
        tile.setProperty("preset_id", preset.id)
        search_blob = f"{tr(preset.name_key)} {preset.reference_artist} {preset.id}"
        tile.setProperty("preset_search", search_blob)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumSize(150, 92)
        tile.setMaximumHeight(110)
        tile.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 2px solid {COLOR_BORDER_DEFAULT}; border-radius: 6px; "
            f"padding: 6px; text-align: left; }}"
            f"QPushButton:hover {{ border-color: #D85A30; "
            f"background-color: #34343c; }}"
        )

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Top: icon + name on one line
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        icon = QLabel(preset.icon)
        icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        top.addWidget(icon)
        name = QLabel(tr(preset.name_key))
        name.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        name.setWordWrap(True)
        top.addWidget(name, 1)
        layout.addLayout(top)

        # Bottom: reference artist (if any)
        if preset.reference_artist:
            ref = QLabel(f"- {preset.reference_artist}")
            ref.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
                f"background: transparent; border: none;"
            )
            layout.addWidget(ref)

        layout.addStretch(1)
        tile.clicked.connect(lambda _c=False, pid=preset.id: self._select(pid))
        return tile

    def _select(self, preset_id: str) -> None:
        if self._popup is not None:
            self._popup.hide()
        self.preset_applied.emit(preset_id)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        for tile in self._tile_buttons:
            haystack = (tile.property("preset_search") or "").lower()
            tile.setVisible(not needle or needle in haystack)


class _ZoomRegionPicker(QWidget):
    """Custom widget for the zoom-target rectangle picker.

    Shows a still frame from the source video and lets the user drag a
    rectangle on it. Emits ``rect_changed(x, y, w, h)`` in source-frame
    pixel coordinates as the user drags.
    """

    rect_changed = Signal(int, int, int, int)

    def __init__(self, frame: QImage, parent=None) -> None:
        super().__init__(parent)
        self._frame = frame
        self._frame_w = frame.width()
        self._frame_h = frame.height()
        # Rectangle in source-frame px; (0,0,0,0) = unset.
        self._rect_src: QRect = QRect()
        self._dragging = False
        self._drag_start_widget: QPoint = QPoint()
        self.setMinimumSize(640, 360)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_initial_rect(self, x: int, y: int, w: int, h: int) -> None:
        if w > 0 and h > 0:
            self._rect_src = QRect(x, y, w, h)
            self.update()

    def current_rect(self) -> QRect:
        return QRect(self._rect_src)

    # ---- coordinate transforms ----

    def _display_rect(self) -> QRect:
        """The widget rect the source frame is painted into, preserving
        aspect. The picker rectangle is drawn relative to this."""
        if self._frame_w <= 0 or self._frame_h <= 0:
            return self.rect()
        wr = self.rect()
        scale = min(wr.width() / self._frame_w, wr.height() / self._frame_h)
        dw = int(self._frame_w * scale)
        dh = int(self._frame_h * scale)
        dx = (wr.width() - dw) // 2
        dy = (wr.height() - dh) // 2
        return QRect(dx, dy, dw, dh)

    def _widget_to_src(self, p: QPoint) -> QPoint:
        d = self._display_rect()
        if d.width() <= 0 or d.height() <= 0:
            return QPoint(0, 0)
        sx = (p.x() - d.left()) * self._frame_w // d.width()
        sy = (p.y() - d.top()) * self._frame_h // d.height()
        sx = max(0, min(self._frame_w - 1, sx))
        sy = max(0, min(self._frame_h - 1, sy))
        return QPoint(sx, sy)

    def _src_to_widget_rect(self, src: QRect) -> QRect:
        d = self._display_rect()
        if d.width() <= 0 or self._frame_w <= 0:
            return QRect()
        x = d.left() + src.x() * d.width() // self._frame_w
        y = d.top() + src.y() * d.height() // self._frame_h
        w = src.width() * d.width() // self._frame_w
        h = src.height() * d.height() // self._frame_h
        return QRect(x, y, w, h)

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._drag_start_widget = event.position().toPoint()
        # Reset the rect ??start a fresh drag.
        sp = self._widget_to_src(self._drag_start_widget)
        self._rect_src = QRect(sp.x(), sp.y(), 0, 0)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging:
            return
        end_widget = event.position().toPoint()
        sp_start = self._widget_to_src(self._drag_start_widget)
        sp_end = self._widget_to_src(end_widget)
        x = min(sp_start.x(), sp_end.x())
        y = min(sp_start.y(), sp_end.y())
        w = abs(sp_end.x() - sp_start.x())
        h = abs(sp_end.y() - sp_start.y())
        self._rect_src = QRect(x, y, w, h)
        self.update()
        self.rect_changed.emit(x, y, w, h)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QPainter as _QP, QPixmap as _QPM
        painter = _QP(self)
        painter.fillRect(self.rect(), QColor("#0a0a0e"))

        d = self._display_rect()
        if not self._frame.isNull() and d.width() > 0:
            painter.drawImage(d, self._frame)

        # Dim everything outside the chosen rect.
        if self._rect_src.width() > 0 and self._rect_src.height() > 0:
            wr = self._src_to_widget_rect(self._rect_src)
            # Dim mask
            painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
            # Punch out the picked rect (re-draw the original clip there)
            painter.setCompositionMode(_QP.CompositionMode.CompositionMode_Source)
            if not self._frame.isNull():
                # Compute the source crop in the original image
                sx = self._rect_src.x() * d.width() // self._frame_w
                sy = self._rect_src.y() * d.height() // self._frame_h
                sw = self._rect_src.width() * d.width() // self._frame_w
                sh = self._rect_src.height() * d.height() // self._frame_h
                src_view = QRect(self._rect_src)
                target_view = wr
                painter.drawImage(target_view, self._frame, src_view)
            painter.setCompositionMode(_QP.CompositionMode.CompositionMode_SourceOver)
            # Highlight border
            pen = QPen(QColor(COLOR_ACCENT_BLUE), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(wr)
            # Centre marker
            cx = wr.left() + wr.width() // 2
            cy = wr.top() + wr.height() // 2
            painter.setPen(QPen(QColor(COLOR_ACCENT_BLUE), 1))
            painter.drawLine(cx - 6, cy, cx + 6, cy)
            painter.drawLine(cx, cy - 6, cx, cy + 6)


class ZoomActorDialog(QDialog):
    """Modal: pick the zoom target rectangle on a still frame from the
    source video, plus zoom-in / zoom-out duration sliders. Mutates the
    actor in-place on Apply."""

    def __init__(self, track: VideoTrack, zactor: ZoomActor,
                 player, parent=None) -> None:
        super().__init__(parent)
        self.track = track
        self.zactor = zactor
        self._player = player
        self.setWindowTitle(tr("veditor.zoom_dialog.title"))
        self.setMinimumSize(820, 620)

        # Snapshot a frame from the source at the actor's start time.
        frame = self._capture_source_frame(zactor.start_ms)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hint = QLabel(tr("veditor.zoom_dialog.hint"))
        hint.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        v.addWidget(hint)

        self._picker = _ZoomRegionPicker(frame)
        self._picker.set_initial_rect(
            zactor.target_x, zactor.target_y, zactor.target_w, zactor.target_h
        )
        v.addWidget(self._picker, 1)

        # Fade times (zoom_in_ms / zoom_out_ms) are edited directly on
        # the timeline via the inner handles on the actor block ??same
        # pattern as Fade actors. The dialog only handles the target
        # rectangle, which can't sensibly live on a 1-D timeline.

        # Apply / Cancel
        from PySide6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).clicked.connect(
            self.reject
        )
        v.addWidget(buttons)

    def _capture_source_frame(self, source_ms: int) -> QImage:
        """Read one frame from the track's source video at ``source_ms``.
        Falls back to a blank frame if reading fails."""
        path = self.track.source_path
        if path is None:
            return QImage(640, 360, QImage.Format.Format_RGB888)
        try:
            import cv2
            import numpy as np
            cap = cv2.VideoCapture(str(path))
            try:
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                idx = int(source_ms / 1000.0 * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    raise RuntimeError("frame read failed")
                rgb = np.ascontiguousarray(bgr[:, :, ::-1])
                h, w = rgb.shape[:2]
                return QImage(rgb.data, w, h, rgb.strides[0],
                              QImage.Format.Format_RGB888).copy()
            finally:
                cap.release()
        except Exception:
            return QImage(640, 360, QImage.Format.Format_RGB888)

    def _on_apply(self) -> None:
        rect = self._picker.current_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                tr("veditor.zoom_dialog.title"),
                tr("veditor.zoom_dialog.no_rect"),
            )
            return
        self.zactor.target_x = int(rect.x())
        self.zactor.target_y = int(rect.y())
        self.zactor.target_w = int(rect.width())
        self.zactor.target_h = int(rect.height())
        self.accept()


class TypographyEditorDialog(QDialog):
    """Phase 2 typography editor ??3-pane (text / animation placeholder
    / style) modal with a real-time preview at the top.

    Edits mutate the clip in-place so the underlying preview updates
    live; Cancel restores from a snapshot taken at open time."""

    WEIGHT_PRESETS = [
        ("thin", 200),
        ("regular", 400),
        ("bold", 700),
        ("black", 900),
    ]

    ALIGN_OPTIONS = ("left", "center", "right")

    def __init__(self, clip: TextClip, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip = clip
        self._snapshot = self._snapshot_clip()
        self._suppress_signals = False

        # Capture the parent editor's current preview frame for the
        # video-background option. Copy so subsequent player frames
        # don't mutate it under us.
        self._video_bg_pixmap: QPixmap | None = None
        if parent is not None:
            pm = getattr(parent, "_preview_pixmap", None)
            if pm is not None and not pm.isNull():
                self._video_bg_pixmap = QPixmap(pm)
        self._show_video_bg: bool = self._video_bg_pixmap is not None

        title = clip.text[:30] or "Text"
        self.setWindowTitle(tr("veditor.typo_editor.title", name=title))
        self.setModal(True)
        self.resize(1200, 800)
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
            f"QLabel {{ color: {COLOR_TEXT_SECONDARY}; }}"
            f"QGroupBox {{ color: {COLOR_TEXT_PRIMARY}; font-weight: 700; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"margin-top: 10px; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; "
            f"subcontrol-position: top left; left: 10px; padding: 0 4px; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # ---- Preview ----
        self._preview_view = _PreviewView()
        self._preview_view.setMinimumHeight(280)
        self._preview_item = _TextPreviewItem(
            clip,
            bg_provider=self._current_bg,
            time_provider=self._current_play_time,
        )
        self._preview_view.add_item(self._preview_item.graphics_item())
        root.addWidget(self._preview_view, stretch=2)

        # Playback state for animation preview.
        self._play_time_s: float = 0.0
        self._is_playing: bool = False
        from PySide6.QtCore import QTimer
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)         # ~30 fps; smooth enough
        self._play_timer.timeout.connect(self._on_play_tick)

        # Preview controls row: Play / Reset + Video-background toggle
        from PySide6.QtWidgets import QCheckBox
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(6)

        self._play_btn = QPushButton("")
        self._play_btn.setObjectName("ToolButton")
        self._play_btn.setFixedWidth(40)
        self._play_btn.setIcon(app_icon("play", size=15, color="#D7DAE7"))
        self._play_btn.setIconSize(icon_size(15))
        self._play_btn.setToolTip(tr("veditor.typo_editor.preview_play"))
        self._play_btn.clicked.connect(self._toggle_preview_play)
        ctrl_row.addWidget(self._play_btn)

        self._reset_btn = QPushButton("")
        self._reset_btn.setObjectName("ToolButton")
        self._reset_btn.setFixedWidth(40)
        self._reset_btn.setIcon(app_icon("reset", size=15, color="#D7DAE7"))
        self._reset_btn.setIconSize(icon_size(15))
        self._reset_btn.setToolTip(tr("veditor.typo_editor.preview_reset"))
        self._reset_btn.clicked.connect(self._reset_preview)
        ctrl_row.addWidget(self._reset_btn)

        self._play_label = QLabel(self._format_play_label())
        self._play_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-family: Consolas, monospace;"
        )
        ctrl_row.addWidget(self._play_label)

        ctrl_row.addStretch(1)

        self._video_bg_check = QCheckBox(tr("veditor.typo_editor.show_video_bg"))
        self._video_bg_check.setChecked(self._show_video_bg)
        self._video_bg_check.setEnabled(self._video_bg_pixmap is not None)
        if self._video_bg_pixmap is None:
            self._video_bg_check.setToolTip(
                tr("veditor.typo_editor.show_video_bg.unavailable")
            )
        self._video_bg_check.toggled.connect(self._on_video_bg_toggle)
        ctrl_row.addWidget(self._video_bg_check)

        root.addLayout(ctrl_row)

        # ---- Preset picker (single full-width purple button) ----
        self._preset_picker = _PresetPickerButton()
        self._preset_picker.preset_applied.connect(self._on_preset_picked)
        root.addWidget(self._preset_picker)

        # ---- 3 panes ----
        panes = QHBoxLayout()
        panes.setSpacing(10)
        panes.addWidget(self._build_text_pane(), stretch=1)
        panes.addWidget(self._build_animation_pane(), stretch=1)
        panes.addWidget(self._build_style_pane(), stretch=2)
        self._panes_layout = panes        # kept for preset-apply rebuild
        root.addLayout(panes, stretch=3)

        # ---- Buttons ----
        from PySide6.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox()
        save_btn = bb.addButton(
            tr("veditor.typo_editor.save_template"),
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        save_btn.setEnabled(False)  # Phase 4: preset system
        save_btn.setToolTip(tr("veditor.typo_editor.save_template.tooltip"))
        cancel_btn = bb.addButton(
            tr("veditor.typo_editor.cancel"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        apply_btn = bb.addButton(
            tr("veditor.typo_editor.apply"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        apply_btn.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self._on_cancel)
        root.addWidget(bb)

    # ---- snapshot / cancel ----

    def _snapshot_clip(self) -> dict:
        import copy
        return {
            "text": self._clip.text,
            "style": copy.deepcopy(self._clip.style),
            "in_duration": self._clip.animation.in_duration,
            "out_duration": self._clip.animation.out_duration,
            "in_animation": self._clip.animation.in_animation,
            "out_animation": self._clip.animation.out_animation,
            "hold_animation": getattr(self._clip.animation, "hold_animation", "none"),
            "in_extras": list(getattr(self._clip.animation, "in_extras", []) or []),
            "out_extras": list(getattr(self._clip.animation, "out_extras", []) or []),
            "hold_extras": list(getattr(self._clip.animation, "hold_extras", []) or []),
            "in_intensity": self._clip.animation.in_intensity,
            "out_intensity": self._clip.animation.out_intensity,
            "hold_intensity": getattr(self._clip.animation, "hold_intensity", 100.0),
            "mono_color": getattr(self._clip.animation, "mono_color", False),
        }

    def _on_cancel(self) -> None:
        snap = self._snapshot
        self._clip.text = snap["text"]
        self._clip.style = snap["style"]
        self._clip.animation.in_duration = snap["in_duration"]
        self._clip.animation.out_duration = snap["out_duration"]
        self._clip.animation.in_animation = snap["in_animation"]
        self._clip.animation.out_animation = snap["out_animation"]
        self._clip.animation.hold_animation = snap["hold_animation"]
        self._clip.animation.in_extras = list(snap["in_extras"])
        self._clip.animation.out_extras = list(snap["out_extras"])
        self._clip.animation.hold_extras = list(snap["hold_extras"])
        self._clip.animation.in_intensity = snap["in_intensity"]
        self._clip.animation.out_intensity = snap["out_intensity"]
        self._clip.animation.hold_intensity = snap["hold_intensity"]
        self._clip.animation.mono_color = snap["mono_color"]
        self.reject()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_play_timer"):
            self._play_timer.stop()
        super().closeEvent(event)

    def _refresh_preview(self) -> None:
        self._preview_item.refresh()

    def _current_bg(self):
        """Provider used by ``_TextPreviewItem`` ??returns the captured
        video frame when the user wants it shown, else ``None`` for a
        plain black backdrop."""
        if self._show_video_bg and self._video_bg_pixmap is not None:
            return self._video_bg_pixmap
        return None

    def _on_video_bg_toggle(self, on: bool) -> None:
        self._show_video_bg = bool(on)
        self._refresh_preview()

    # ---- preview playback ----

    def _current_play_time(self):
        """Animation time provider. Returns seconds-since-clip-start
        when the user is actively playing; ``None`` while paused (so
        the preview shows the steady HOLD state for editing)."""
        if self._is_playing:
            return self._play_time_s
        # When paused, show the steady "fully on screen" state by
        # passing a time that lands inside HOLD.
        return None

    def _set_preview_play_icon(self, playing: bool) -> None:
        if not hasattr(self, "_play_btn"):
            return
        self._play_btn.setText("")
        self._play_btn.setIcon(app_icon("pause" if playing else "play", size=15, color="#D7DAE7"))
        self._play_btn.setIconSize(icon_size(15))

    def _toggle_preview_play(self) -> None:
        if self._is_playing:
            self._is_playing = False
            self._play_timer.stop()
            self._set_preview_play_icon(False)
        else:
            # Start fresh from 0 if we were paused at end.
            if self._play_time_s >= self._clip.duration_s - 0.001:
                self._play_time_s = 0.0
            self._is_playing = True
            self._play_timer.start()
            self._set_preview_play_icon(True)
        self._refresh_preview()
        self._update_play_label()

    def _reset_preview(self) -> None:
        self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _on_play_tick(self) -> None:
        # Advance and loop. Looping makes it easy to compare animations
        # without mashing the play button between every change.
        self._play_time_s += self._play_timer.interval() / 1000.0
        if self._play_time_s >= self._clip.duration_s:
            self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _format_play_label(self) -> str:
        return f"{self._play_time_s:5.2f} / {self._clip.duration_s:5.2f} s"

    def _update_play_label(self) -> None:
        if hasattr(self, "_play_label"):
            self._play_label.setText(self._format_play_label())

    # ---- text pane ----

    def _build_text_pane(self) -> QWidget:
        from PySide6.QtWidgets import QGroupBox, QPlainTextEdit

        box = QGroupBox(tr("veditor.typo_editor.text_pane"))
        box.setMinimumWidth(220)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(8)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlainText(self._clip.text)
        self._text_edit.setPlaceholderText(tr("veditor.typo_editor.placeholder"))
        self._text_edit.setStyleSheet(
            f"QPlainTextEdit {{ padding: 8px; font-size: 14px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._text_edit.textChanged.connect(self._on_text_changed)
        lay.addWidget(self._text_edit, stretch=1)

        return box

    def _on_text_changed(self) -> None:
        if self._suppress_signals:
            return
        self._clip.text = self._text_edit.toPlainText()
        self._refresh_preview()

    # ---- animation pane (placeholder + timing sliders) ----

    def _build_animation_pane(self) -> QWidget:
        from PySide6.QtWidgets import QGroupBox

        box = QGroupBox(tr("veditor.typo_editor.animation_pane"))
        box.setMinimumWidth(240)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(10)

        # IN animation picker ??visual grid in popup.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_in")))
        self._in_picker = _AnimationPickerButton(
            self._clip.animation.in_animation, direction="in",
        )
        self._in_picker.animation_changed.connect(self._on_in_anim_picked)
        lay.addWidget(self._in_picker)
        # IN extras chip row + add button
        self._in_extras_row = self._build_extras_row("in")
        lay.addWidget(self._in_extras_row)

        # IN duration slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.timing.in"),
            value=int(self._clip.animation.in_duration * 1000),
            minimum=0, maximum=5000, suffix=" ms", step=50,
            on_change=self._on_in_changed,
        ))
        # IN intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.in"),
            value=int(self._clip.animation.in_intensity),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_in_intensity_changed,
        ))

        # OUT animation picker
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_out")))
        self._out_picker = _AnimationPickerButton(
            self._clip.animation.out_animation, direction="out",
        )
        self._out_picker.animation_changed.connect(self._on_out_anim_picked)
        lay.addWidget(self._out_picker)
        # OUT extras chip row
        self._out_extras_row = self._build_extras_row("out")
        lay.addWidget(self._out_extras_row)

        # OUT duration slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.timing.out"),
            value=int(self._clip.animation.out_duration * 1000),
            minimum=0, maximum=5000, suffix=" ms", step=50,
            on_change=self._on_out_changed,
        ))
        # OUT intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.out"),
            value=int(self._clip.animation.out_intensity),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_out_intensity_changed,
        ))

        # HOLD animation picker ??loops between IN and OUT.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_hold")))
        self._hold_picker = _AnimationPickerButton(
            getattr(self._clip.animation, "hold_animation", "none"),
            direction="hold",
        )
        self._hold_picker.animation_changed.connect(self._on_hold_anim_picked)
        lay.addWidget(self._hold_picker)
        # HOLD extras chip row
        self._hold_extras_row = self._build_extras_row("hold")
        lay.addWidget(self._hold_extras_row)

        # HOLD intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.hold"),
            value=int(getattr(self._clip.animation, "hold_intensity", 100.0)),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_hold_intensity_changed,
        ))

        # Hold derived label (live) ??shows the seconds available between IN and OUT.
        self._hold_label = QLabel("")
        self._hold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hold_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        self._update_hold_label()
        lay.addWidget(self._hold_label)

        # Mono-color toggle ??disables per-glyph color overrides
        # (e.g. Angle Break's flash) so the whole clip stays one tone.
        from PySide6.QtWidgets import QCheckBox
        self._mono_check = QCheckBox(tr("veditor.typo_editor.mono_color"))
        self._mono_check.setChecked(bool(getattr(self._clip.animation, "mono_color", False)))
        self._mono_check.setToolTip(tr("veditor.typo_editor.mono_color.tooltip"))
        self._mono_check.toggled.connect(self._on_mono_color_toggle)
        lay.addWidget(self._mono_check)

        lay.addStretch(1)
        return box

    # ---- extras (composed animations) ----

    def _extras_attr(self, direction: str) -> str:
        return f"{direction}_extras"

    def _build_extras_row(self, direction: str) -> QWidget:
        """Wraps the chips + an `[+ Add modifier]` button for one slot.
        The wrapper widget keeps a hidden ``_AnimationPickerButton`` in
        ``extras_mode`` so we get the picker popup for free."""
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Hidden adder picker: we trigger its popup by clicking the
        # visible add-button. Adding it to the layout keeps Qt's parent
        # ownership tidy; visibility is the picker button's responsibility.
        adder = _AnimationPickerButton(
            current_id="none", direction=direction, extras_mode=True,
        )
        adder.animation_changed.connect(
            lambda aid, d=direction: self._on_extra_added(d, aid)
        )
        setattr(self, f"_{direction}_adder", adder)

        chips_host = QWidget()
        chips_lay = QHBoxLayout(chips_host)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(4)
        setattr(self, f"_{direction}_chips_lay", chips_lay)

        lay.addWidget(chips_host, 0)
        lay.addWidget(adder, 1)
        self._render_extras_chips(direction)
        return wrap

    def _render_extras_chips(self, direction: str) -> None:
        """Rebuild the chip widgets for ``direction`` from the current
        clip state."""
        chips_lay: QHBoxLayout | None = getattr(self, f"_{direction}_chips_lay", None)
        if chips_lay is None:
            return
        # Clear existing
        while chips_lay.count():
            item = chips_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        extras = list(getattr(self._clip.animation, self._extras_attr(direction), []) or [])
        from app.typo_animations import get_animation
        for idx, aid in enumerate(extras):
            anim = get_animation(aid)
            chip = QPushButton(f" {tr(anim.name_key)}  x")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(tr("veditor.typo_editor.modifier.remove_tooltip"))
            chip.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; "
                f"color: {COLOR_TEXT_PRIMARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
                f"border-radius: 10px; padding: 2px 8px; font-size: 10px; }}"
                f"QPushButton:hover {{ background-color: #4a3a3a; "
                f"border-color: #7a4a4a; }}"
            )
            chip.clicked.connect(
                lambda _c=False, d=direction, i=idx: self._on_extra_removed(d, i)
            )
            chips_lay.addWidget(chip)

    def _on_extra_added(self, direction: str, anim_id: str) -> None:
        if not anim_id or anim_id == "none":
            return
        attr = self._extras_attr(direction)
        cur = list(getattr(self._clip.animation, attr, []) or [])
        cur.append(anim_id)
        setattr(self._clip.animation, attr, cur)
        self._render_extras_chips(direction)
        self._refresh_preview()

    def _on_extra_removed(self, direction: str, index: int) -> None:
        attr = self._extras_attr(direction)
        cur = list(getattr(self._clip.animation, attr, []) or [])
        if 0 <= index < len(cur):
            del cur[index]
            setattr(self._clip.animation, attr, cur)
            self._render_extras_chips(direction)
            self._refresh_preview()

    # ---- primary picker handlers ----

    def _on_in_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.in_animation = anim_id
        self._refresh_preview()

    def _on_out_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.out_animation = anim_id
        self._refresh_preview()

    def _on_hold_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.hold_animation = anim_id
        self._refresh_preview()

    def _on_preset_picked(self, preset_id: str) -> None:
        """Apply a preset bundle to the clip and rebuild the editor's
        controls so users immediately see the new animation + style
        choices. Animation pane (pickers + sliders) and style pane
        (font, size, weight, effects, etc.) need a full rebuild ??the
        cheapest way is to discard them and re-add."""
        from app.typo_presets import get_preset, apply_preset
        preset = get_preset(preset_id)
        if preset is None:
            return
        apply_preset(self._clip, preset)

        # Rebuild the IN/OUT pickers' visible label by re-syncing them
        # to the clip's new animation ids.
        self._in_picker.set_current(self._clip.animation.in_animation)
        self._out_picker.set_current(self._clip.animation.out_animation)
        if hasattr(self, "_hold_picker"):
            self._hold_picker.set_current(
                getattr(self._clip.animation, "hold_animation", "none"),
            )

        # The size / weight / color / sliders / effects don't have a
        # cheap "set value" path that handles every control, so the
        # safest move is to rebuild the whole 3-pane row. Delegate to a
        # helper that swaps the panes in place.
        self._rebuild_panes()

        # Reset the preview clock so the user sees the IN sequence of
        # the new preset right away.
        self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _rebuild_panes(self) -> None:
        """Replace the 3-pane row with freshly-built widgets so every
        control reflects current clip state. Called after preset apply."""
        panes_layout = self._panes_layout
        if panes_layout is None:
            return
        # Remove old widgets
        while panes_layout.count():
            item = panes_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        panes_layout.addWidget(self._build_text_pane(), stretch=1)
        panes_layout.addWidget(self._build_animation_pane(), stretch=1)
        panes_layout.addWidget(self._build_style_pane(), stretch=2)

    def _slider_row(self, *, label: str, value: int, minimum: int,
                    maximum: int, suffix: str, step: int, on_change) -> QWidget:
        """Inline label + QSlider + value-readout helper."""
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        readout = QLabel(f"{value}{suffix}")
        readout.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600;")
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(lbl)
        head.addStretch(1)
        head.addWidget(readout)
        v.addLayout(head)

        sld = StudioSlider("accent")
        sld.setRange(minimum, maximum)
        sld.setSingleStep(step)
        sld.setPageStep(step * 4)
        sld.setValue(int(value))

        def _emit(val: int) -> None:
            readout.setText(f"{val}{suffix}")
            on_change(val)

        sld.valueChanged.connect(_emit)
        v.addWidget(sld)
        return wrap

    def _on_in_changed(self, ms: int) -> None:
        self._clip.animation.in_duration = max(0.0, ms / 1000.0)
        self._update_hold_label()
        self._refresh_preview()

    def _on_out_changed(self, ms: int) -> None:
        self._clip.animation.out_duration = max(0.0, ms / 1000.0)
        self._update_hold_label()
        self._refresh_preview()

    def _on_in_intensity_changed(self, percent: int) -> None:
        self._clip.animation.in_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_out_intensity_changed(self, percent: int) -> None:
        self._clip.animation.out_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_hold_intensity_changed(self, percent: int) -> None:
        self._clip.animation.hold_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_mono_color_toggle(self, on: bool) -> None:
        self._clip.animation.mono_color = bool(on)
        self._refresh_preview()

    def _update_hold_label(self) -> None:
        if not hasattr(self, "_hold_label"):
            return
        hold = self._clip.hold_duration_s
        self._hold_label.setText(
            tr("veditor.typo_editor.timing.hold", seconds=f"{hold:.2f}")
        )

    # ---- style pane ----

    # Recommended fonts pinned to the top of the picker. These are the
    # families the typography spec recommends for Korean / Japanese MV
    # styles + a few staple Latin display faces. Filtered against the
    # actual installed set at runtime.
    PINNED_FONTS = (
        "Pretendard",
        "Noto Sans KR",
        "Noto Serif KR",
        "Nanum Myeongjo",
        "Gaegu",
        "Noto Sans JP",
        "Noto Serif JP",
        "Shippori Mincho",
        "Arial",
        "Segoe UI",
        "Impact",
    )

    def _build_style_pane(self) -> QWidget:
        from PySide6.QtWidgets import (
            QGroupBox, QPushButton, QButtonGroup, QSpinBox,
        )

        box = QGroupBox(tr("veditor.typo_editor.style_pane"))
        box.setMinimumWidth(300)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(10)

        s = self._clip.style

        # Font family ??compact button + click-to-open popup picker.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.font")))
        self._font_picker = _FontPickerButton(s.font_family)
        self._font_picker.font_changed.connect(self._on_font_family_changed)
        lay.addWidget(self._font_picker)

        # Size
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.size")))
        size_row = QHBoxLayout()
        self._size_slider = StudioSlider("accent")
        self._size_slider.setRange(16, 200)
        self._size_slider.setValue(int(s.font_size))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(16, 200)
        self._size_spin.setValue(int(s.font_size))
        self._size_spin.setFixedWidth(64)
        self._size_slider.valueChanged.connect(self._size_spin.setValue)
        self._size_spin.valueChanged.connect(self._size_slider.setValue)
        self._size_spin.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_slider, stretch=1)
        size_row.addWidget(self._size_spin)
        lay.addLayout(size_row)

        # Weight buttons
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.weight")))
        weight_row = QHBoxLayout()
        self._weight_group = QButtonGroup(self)
        self._weight_group.setExclusive(True)
        for key, weight in self.WEIGHT_PRESETS:
            btn = QPushButton(tr(f"veditor.typo_editor.weight.{key}"))
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.setProperty("weight", weight)
            if abs(s.font_weight - weight) < 50:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c=False, w=weight: self._on_weight_changed(w))
            self._weight_group.addButton(btn)
            weight_row.addWidget(btn)
        lay.addLayout(weight_row)

        # Color + Alignment row
        ca_row = QHBoxLayout()
        self._color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._color_btn.setObjectName("ToolButton")
        self._update_color_btn_swatch()
        self._color_btn.clicked.connect(self._on_color_picked)
        ca_row.addWidget(self._color_btn, stretch=1)

        # Alignment
        self._align_group = QButtonGroup(self)
        self._align_group.setExclusive(True)
        for key in self.ALIGN_OPTIONS:
            btn = QPushButton(tr(f"veditor.typo_editor.align.{key}"))
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.setProperty("align_key", key)
            if s.alignment == key:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c=False, k=key: self._on_align_changed(k))
            self._align_group.addButton(btn)
            ca_row.addWidget(btn)
        lay.addLayout(ca_row)

        # Position X / Y
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.position_x"),
            value=int(s.position_x * 100),
            minimum=0, maximum=100, suffix=" %", step=1,
            on_change=self._on_pos_x_changed,
        ))
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.position_y"),
            value=int(s.position_y * 100),
            minimum=0, maximum=100, suffix=" %", step=1,
            on_change=self._on_pos_y_changed,
        ))

        # Letter spacing
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.letter_spacing"),
            value=int(s.letter_spacing),
            minimum=-5, maximum=30, suffix=" px", step=1,
            on_change=self._on_letter_spacing_changed,
        ))

        # Effects (outline / shadow / background) ??collapsed-style block
        lay.addWidget(self._build_effects_block())

        lay.addStretch(1)
        return box

    def _build_effects_block(self) -> QWidget:
        from PySide6.QtWidgets import QCheckBox, QGroupBox, QPushButton

        s = self._clip.style
        box = QGroupBox(tr("veditor.typo_editor.effects.section"))
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 14, 8, 8)
        v.setSpacing(6)

        # ---- Outline ----
        ol_row = QHBoxLayout()
        self._outline_check = QCheckBox(tr("veditor.typo_editor.effects.outline"))
        self._outline_check.setChecked(bool(s.outline_color and s.outline_width > 0))
        self._outline_check.toggled.connect(self._on_outline_toggle)
        ol_row.addWidget(self._outline_check)
        self._outline_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._outline_color_btn.setObjectName("ToolButton")
        self._update_outline_swatch()
        self._outline_color_btn.clicked.connect(self._on_outline_color)
        ol_row.addWidget(self._outline_color_btn)
        v.addLayout(ol_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.outline_width"),
            value=int(s.outline_width or 0),
            minimum=0, maximum=12, suffix=" px", step=1,
            on_change=self._on_outline_width,
        ))

        # ---- Shadow ----
        sh_row = QHBoxLayout()
        self._shadow_check = QCheckBox(tr("veditor.typo_editor.effects.shadow"))
        self._shadow_check.setChecked(bool(s.shadow_color))
        self._shadow_check.toggled.connect(self._on_shadow_toggle)
        sh_row.addWidget(self._shadow_check)
        self._shadow_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._shadow_color_btn.setObjectName("ToolButton")
        self._update_shadow_swatch()
        self._shadow_color_btn.clicked.connect(self._on_shadow_color)
        sh_row.addWidget(self._shadow_color_btn)
        v.addLayout(sh_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.shadow_x"),
            value=int(s.shadow_offset_x or 0),
            minimum=-20, maximum=20, suffix=" px", step=1,
            on_change=self._on_shadow_x,
        ))
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.shadow_y"),
            value=int(s.shadow_offset_y or 0),
            minimum=-20, maximum=20, suffix=" px", step=1,
            on_change=self._on_shadow_y,
        ))

        # ---- Background ----
        bg_row = QHBoxLayout()
        self._bg_check = QCheckBox(tr("veditor.typo_editor.effects.background"))
        self._bg_check.setChecked(bool(s.background_color))
        self._bg_check.toggled.connect(self._on_bg_toggle)
        bg_row.addWidget(self._bg_check)
        self._bg_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._bg_color_btn.setObjectName("ToolButton")
        self._update_bg_swatch()
        self._bg_color_btn.clicked.connect(self._on_bg_color)
        bg_row.addWidget(self._bg_color_btn)
        v.addLayout(bg_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.bg_padding"),
            value=int(s.background_padding or 0),
            minimum=0, maximum=80, suffix=" px", step=2,
            on_change=self._on_bg_padding,
        ))
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.bg_radius"),
            value=int(s.background_radius or 0),
            minimum=0, maximum=80, suffix=" px", step=2,
            on_change=self._on_bg_radius,
        ))

        return box

    @staticmethod
    def _labelled(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
                          f"font-weight: 700; letter-spacing: 0.5px;")
        return lbl

    # ---- style change handlers ----

    def _on_font_family_changed(self, family: str) -> None:
        self._clip.style.font_family = family
        self._refresh_preview()

    def _on_size_changed(self, value: int) -> None:
        self._clip.style.font_size = int(value)
        self._refresh_preview()

    def _on_weight_changed(self, weight: int) -> None:
        self._clip.style.font_weight = int(weight)
        self._refresh_preview()

    def _on_color_picked(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.color or "#FFFFFF")
        chosen = QColorDialog.getColor(cur, self,
                                       tr("veditor.typo_editor.color_dialog"))
        if chosen.isValid():
            self._clip.style.color = chosen.name()
            self._update_color_btn_swatch()
            self._refresh_preview()

    def _on_align_changed(self, key: str) -> None:
        self._clip.style.alignment = key
        self._refresh_preview()

    def _on_pos_x_changed(self, percent: int) -> None:
        self._clip.style.position_x = max(0.0, min(1.0, percent / 100.0))
        self._refresh_preview()

    def _on_pos_y_changed(self, percent: int) -> None:
        self._clip.style.position_y = max(0.0, min(1.0, percent / 100.0))
        self._refresh_preview()

    def _on_letter_spacing_changed(self, value: int) -> None:
        self._clip.style.letter_spacing = int(value)
        self._refresh_preview()

    # ---- effects ----

    def _on_outline_toggle(self, on: bool) -> None:
        if on and not self._clip.style.outline_color:
            self._clip.style.outline_color = "#000000"
        if on and self._clip.style.outline_width <= 0:
            self._clip.style.outline_width = 2
        if not on:
            self._clip.style.outline_width = 0
        self._update_outline_swatch()
        self._refresh_preview()

    def _on_outline_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.outline_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.outline_color = c.name()
            if not self._outline_check.isChecked():
                self._outline_check.setChecked(True)
            self._update_outline_swatch()
            self._refresh_preview()

    def _on_outline_width(self, w: int) -> None:
        self._clip.style.outline_width = int(w)
        if w > 0 and not self._outline_check.isChecked():
            self._outline_check.setChecked(True)
        self._refresh_preview()

    def _on_shadow_toggle(self, on: bool) -> None:
        if on and not self._clip.style.shadow_color:
            self._clip.style.shadow_color = "#000000"
        if on and not (self._clip.style.shadow_offset_x or self._clip.style.shadow_offset_y):
            self._clip.style.shadow_offset_x = 3
            self._clip.style.shadow_offset_y = 3
        if not on:
            self._clip.style.shadow_color = None
        self._update_shadow_swatch()
        self._refresh_preview()

    def _on_shadow_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.shadow_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.shadow_color = c.name()
            if not self._shadow_check.isChecked():
                self._shadow_check.setChecked(True)
            self._update_shadow_swatch()
            self._refresh_preview()

    def _on_shadow_x(self, v: int) -> None:
        self._clip.style.shadow_offset_x = int(v)
        self._refresh_preview()

    def _on_shadow_y(self, v: int) -> None:
        self._clip.style.shadow_offset_y = int(v)
        self._refresh_preview()

    def _on_bg_toggle(self, on: bool) -> None:
        if on and not self._clip.style.background_color:
            self._clip.style.background_color = "#000000"
        if not on:
            self._clip.style.background_color = None
        self._update_bg_swatch()
        self._refresh_preview()

    def _on_bg_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.background_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.background_color = c.name()
            if not self._bg_check.isChecked():
                self._bg_check.setChecked(True)
            self._update_bg_swatch()
            self._refresh_preview()

    def _on_bg_padding(self, v: int) -> None:
        self._clip.style.background_padding = int(v)
        self._refresh_preview()

    def _on_bg_radius(self, v: int) -> None:
        self._clip.style.background_radius = int(v)
        self._refresh_preview()

    # ---- swatch updates ----

    def _swatch_style(self, hex_color: str | None) -> str:
        c = hex_color or "transparent"
        return (
            f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 8px; text-align: left; }}"
            # We'll prepend a colored square via icon-ish trick below
        )

    def _set_swatch_button(self, btn, hex_color: str | None, label: str) -> None:
        c = hex_color or "transparent"
        if hex_color:
            btn.setText(f"  {label}  ({hex_color})")
            # Use a stylesheet block with a left-side colored gutter
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 4px 8px; "
                f"border-left: 12px solid {hex_color}; }}"
                f"QPushButton:hover {{ border-color: #6a6a72; }}"
            )
        else:
            btn.setText(f"  {label}")
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_TERTIARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 4px 8px; }}"
                f"QPushButton:hover {{ border-color: #6a6a72; }}"
            )

    def _update_color_btn_swatch(self) -> None:
        self._set_swatch_button(
            self._color_btn, self._clip.style.color,
            tr("veditor.typo_editor.btn.text_color"),
        )

    def _update_outline_swatch(self) -> None:
        col = self._clip.style.outline_color if self._clip.style.outline_width else None
        self._set_swatch_button(
            self._outline_color_btn, col,
            tr("veditor.typo_editor.btn.color"),
        )

    def _update_shadow_swatch(self) -> None:
        self._set_swatch_button(
            self._shadow_color_btn, self._clip.style.shadow_color,
            tr("veditor.typo_editor.btn.color"),
        )

    def _update_bg_swatch(self) -> None:
        self._set_swatch_button(
            self._bg_color_btn, self._clip.style.background_color,
            tr("veditor.typo_editor.btn.color"),
        )
