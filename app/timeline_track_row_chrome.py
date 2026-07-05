from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QMenu

from app.effect_cards import SpeedCard
from app.i18n import tr
from app.studio_theme import (
    STUDIO_ACTION,
    STUDIO_ACTION_EDGE,
    STUDIO_ACTION_HI,
    paint_studio_zoom_block,
)


def _format_speed(p: float) -> str:
    if abs(p - round(p)) < 1e-3:
        return f"{int(round(p))}x"
    return f"{p:g}x"

def _paint_clip_length_chrome(
    self,
    painter: QPainter,
    clip_rect: QRect,
    *,
    clip,
    selected: bool,
    active: bool,
    fill: QColor,
    highlight: QColor,
    edge: QColor,
) -> None:
    if clip_rect.width() <= 1 or clip_rect.height() <= 10:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    rail_edge = QColor(edge)
    visual_rect = clip_rect.adjusted(2, 5, -2, -5)
    if visual_rect.height() < 8:
        visual_rect = clip_rect.adjusted(2, 2, -2, -2)
    body = visual_rect
    if body.width() > 0 and body.height() > 0:
        body_grad = QLinearGradient(body.topLeft(), body.bottomLeft())
        top = QColor(highlight)
        bottom = QColor(0, 0, 0)
        top.setAlpha(22 if active else 15)
        bottom.setAlpha(24 if active else 18)
        body_grad.setColorAt(0.0, top)
        body_grad.setColorAt(0.55, QColor(255, 255, 255, 4))
        body_grad.setColorAt(1.0, bottom)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(body_grad))
        painter.drawRoundedRect(body, 4, 4)

    if selected:
        selected_tint = QColor(edge)
        selected_tint.setAlpha(28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(selected_tint)
        painter.drawRoundedRect(visual_rect.adjusted(1, 1, -1, -1), 5, 5)

    if selected and clip_rect.width() >= 48 and clip_rect.height() >= 28:
        handle_fill = QColor(edge)
        handle_fill.setAlpha(138)
        handle_edge = QColor(255, 255, 255, 52)
        handle_w = 9
        handle_h = min(16, max(10, visual_rect.height() - 8))
        y = visual_rect.center().y() - handle_h // 2
        for x in (clip_rect.left() + 6, clip_rect.right() - handle_w - 5):
            handle = QRect(x, y, handle_w, handle_h)
            painter.setPen(QPen(handle_edge, 1))
            painter.setBrush(handle_fill)
            painter.drawRoundedRect(handle, 3, 3)

        dot = QColor(255, 255, 255, 72)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        for x in (clip_rect.left() + 9, clip_rect.right() - 10):
            painter.drawRoundedRect(QRect(x, visual_rect.center().y() - 2, 3, 3), 1, 1)

    if not selected and clip_rect.width() >= 42 and clip_rect.height() >= 24:
        inset = QColor(edge)
        inset.setAlpha(22)
        painter.setPen(QPen(inset, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(visual_rect, 5, 5)

    if clip_rect.width() >= 72 and clip_rect.height() >= 30:
        footer = QRect(
            visual_rect.left() + 5,
            visual_rect.bottom() - 5,
            max(1, visual_rect.width() - 10),
            3,
        )
        footer_grad = QLinearGradient(footer.topLeft(), footer.topRight())
        soft = QColor(edge)
        soft.setAlpha(74 if selected else 34)
        clear = QColor(edge)
        clear.setAlpha(0)
        footer_grad.setColorAt(0.0, clear)
        footer_grad.setColorAt(0.5, soft)
        footer_grad.setColorAt(1.0, clear)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(footer_grad))
        painter.drawRoundedRect(footer, 2, 2)

    dur_ms = max(
        0,
        int(getattr(clip, "timeline_out_ms", 0) or 0)
        - int(getattr(clip, "timeline_in_ms", 0) or 0),
    )
    duration_text = self._duration_chip_text(dur_ms)
    if duration_text and clip_rect.width() >= 112 and clip_rect.height() >= 32:
        font = QFont(painter.font())
        font.setPixelSize(8)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        chip_w = min(max(34, metrics.horizontalAdvance(duration_text) + 14), max(34, clip_rect.width() - 18))
        chip = QRect(
            clip_rect.right() - chip_w - 8,
            clip_rect.bottom() - 19,
            chip_w,
            15,
        )
        if chip.width() > 24:
            chip_fill = QColor(18, 19, 21, 178)
            painter.setBrush(chip_fill)
            rail_edge.setAlpha(118 if selected else 76)
            painter.setPen(QPen(rail_edge, 1))
            painter.drawRoundedRect(chip, 5, 5)
            painter.setPen(QColor(244, 238, 226, 218))
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, duration_text)
    painter.restore()

def _on_context_menu(self, local_pos: QPoint) -> None:
    # Zoom actor right-click: edit / delete menu.
    zactor, _zone = self._zoom_at(local_pos)
    if zactor is not None:
        self.zoom_context_menu.emit(
            self.track.id, zactor.id, self.mapToGlobal(local_pos)
        )
        return
    # Typography actors have priority ??they sit visually on top
    # of the timeline strip.
    typo_actor, _zone = self._typography_at(local_pos)
    if typo_actor is not None:
        self.typography_context_menu.emit(
            self.track.id, typo_actor.id, self.mapToGlobal(local_pos)
        )
        return
    # If the click is on a fade actor, open the fade-type / delete menu
    # instead of the generic track menu.
    fade = self._fade_under(local_pos)
    if fade is not None:
        self._show_fade_menu(fade, self.mapToGlobal(local_pos))
        return
    # Speed segment right-click: rate picker + delete.
    seg = self._speed_segment_under(local_pos)
    if seg is not None:
        self._show_speed_menu(seg, self.mapToGlobal(local_pos))
        return
    # CapCut-style transition block right-click: show transition menu
    # if the cursor is inside any existing transition block.
    trans_clip, _side = self._transition_handle_at(local_pos)
    if trans_clip is None:
        # Also fall back to old proximity check for backwards compat
        trans_clip = self._transition_clip_at(local_pos)
    if trans_clip is not None:
        self._show_transition_menu(trans_clip, self.mapToGlobal(local_pos))
        return
    badge_clip = self._hit_test_clip(local_pos)
    if badge_clip is not None:
        badge_action = self._clip_status_action_at(badge_clip, local_pos)
        if badge_action:
            self.clip_badge_context_menu.emit(
                self.track.id,
                int(badge_clip.id),
                badge_action,
                self.mapToGlobal(local_pos),
            )
            return
    # Video clip right-click ??emit clip_context_menu
    _rclip = self._clip_at(local_pos)
    if _rclip is not None:
        self.clip_context_menu.emit(
            self.track.id, _rclip.id, self.mapToGlobal(local_pos)
        )
        return
    self.context_menu.emit(self.track.id, self.mapToGlobal(local_pos))

def _show_speed_menu(self, seg: "SpeedSegment", global_pos) -> None:
    """Preset rate picker + Frame Blend toggle + delete action for a placed SpeedSegment."""
    menu = QMenu(self)
    # Header (disabled action showing current speed)
    hdr = menu.addAction(tr("veditor.speed_menu.current", speed=_format_speed(seg.speed)))
    hdr.setEnabled(False)
    menu.addSeparator()
    preset_actions: list = []
    for p in SpeedCard.PRESETS:
        a = menu.addAction(SpeedCard._format_preset(p))
        a.setCheckable(True)
        a.setChecked(abs(seg.speed - p) < 1e-3)
        preset_actions.append((a, p))
    menu.addSeparator()
    # Frame blend toggle (only meaningful for slow-motion; shown always for simplicity)
    act_blend = menu.addAction(tr("veditor.speed_menu.frame_blend"))
    act_blend.setCheckable(True)
    act_blend.setChecked(getattr(seg, "frame_blend", False))
    # Blend mode sub-menu
    blend_sub = menu.addMenu(tr("veditor.speed_menu.blend_mode"))
    act_linear = blend_sub.addAction(tr("veditor.speed_menu.blend_linear"))
    act_linear.setCheckable(True)
    act_flow = blend_sub.addAction(tr("veditor.speed_menu.blend_optical_flow"))
    act_flow.setCheckable(True)
    current_mode = getattr(seg, "blend_mode", "linear")
    act_linear.setChecked(current_mode == "linear")
    act_flow.setChecked(current_mode == "optical_flow")
    menu.addSeparator()
    # Ease in/out sub-menu (Bezier speed ramp)
    ease_sub = menu.addMenu("Speed Ramp (Ease)")
    def _ease_act(label, ein, eout):
        a = ease_sub.addAction(label)
        a.setData((ein, eout))
        return a
    _ease_act("None (constant)", 0.0, 0.0)
    _ease_act("Ease In", 0.6, 0.0)
    _ease_act("Ease Out", 0.0, 0.6)
    _ease_act("Ease In+Out", 0.6, 0.6)
    _ease_act("S-Curve (full)", 1.0, 1.0)
    menu.addSeparator()
    act_del = menu.addAction(tr("veditor.speed_menu.delete"))
    chosen = menu.exec(global_pos)
    # Handle ease actions
    if chosen is not None and chosen.data() is not None:
        ein, eout = chosen.data()
        seg.ease_in  = float(ein)
        seg.ease_out = float(eout)
        self.update()
        self.speed_changed.emit(self.track.id)
        return
    if chosen is act_del:
        try:
            self.track.speed_segments.remove(seg)
        except ValueError:
            pass
        self.update()
        self.speed_changed.emit(self.track.id)
        return
    if chosen is act_blend:
        seg.frame_blend = not getattr(seg, "frame_blend", False)
        self.update()
        self.speed_changed.emit(self.track.id)
        return
    if chosen is act_linear:
        seg.blend_mode = "linear"
        self.update()
        self.speed_changed.emit(self.track.id)
        return
    if chosen is act_flow:
        seg.blend_mode = "optical_flow"
        self.update()
        self.speed_changed.emit(self.track.id)
        return
    for a, p in preset_actions:
        if chosen is a:
            seg.speed = float(p)
            self.update()
            self.speed_changed.emit(self.track.id)
            return

def _show_transition_menu(self, clip, global_pos) -> None:
    """Right-click menu on a clip's right edge to set/remove transition."""
    menu = QMenu(self)
    cur_type = str(getattr(clip, "transition_out_type", ""))
    cur_ms = int(getattr(clip, "transition_out_ms", 500))

    # --- Add Transition submenu ---
    add_sub = menu.addMenu("Add Transition")
    _TR_MENU_ITEMS = [
        ("dissolve",   f"Cross Dissolve ({cur_ms}ms)"),
        ("fade_black", f"Fade to Black ({cur_ms}ms)"),
        ("fade_white", f"Fade to White ({cur_ms}ms)"),
        ("slide_left", f"Slide Left ({cur_ms}ms)"),
        ("wipe_left",  f"Wipe Left ({cur_ms}ms)"),
        ("zoom_in",    f"Zoom In ({cur_ms}ms)"),
        ("zoom_out",   f"Zoom Out ({cur_ms}ms)"),
    ]
    act_dissolve = act_fade_black = act_fade_white = None
    _tr_acts = {}
    for ttype_k, label_k in _TR_MENU_ITEMS:
        act_k = add_sub.addAction(label_k)
        act_k.setCheckable(True)
        act_k.setChecked(cur_type == ttype_k)
        _tr_acts[ttype_k] = act_k
    act_dissolve = _tr_acts["dissolve"]
    act_fade_black = _tr_acts["fade_black"]
    act_fade_white = _tr_acts["fade_white"]
    add_sub.addSeparator()
    act_custom = add_sub.addAction("Custom duration...")

    act_remove = menu.addAction("Remove Transition")
    act_remove.setEnabled(bool(cur_type))

    chosen = menu.exec(global_pos)
    if chosen is None:
        return
    # Check if chosen is one of the transition type actions
    _tr_label_by_type = {
        str(ttype): str(label).split("(", 1)[0].strip()
        for ttype, label in _TR_MENU_ITEMS
    }
    for ttype_k, act_k in _tr_acts.items():
        if chosen is act_k:
            clip.transition_out_type = ttype_k
            clip.transition_out_ms = cur_ms
            clip.transition_preset_meta = {
                "id": ttype_k,
                "name": _tr_label_by_type.get(ttype_k, ttype_k.replace("_", " ").title()),
                "kind": "transition",
            }
            self.update()
            return
    if chosen is act_custom:
        from PySide6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getInt(
            self, "Transition Duration", "Duration (ms):",
            cur_ms, 50, 10000, 50,
        )
        if ok:
            clip.transition_out_ms = val
            # Keep type if already set, default to dissolve if not
            if not clip.transition_out_type:
                clip.transition_out_type = "dissolve"
                clip.transition_preset_meta = {
                    "id": "dissolve",
                    "name": "Cross Dissolve",
                    "kind": "transition",
                }
    elif chosen is act_remove:
        clip.transition_out_type = ""
        clip.transition_preset_meta = {}
    else:
        return
    self.update()

def _paint_zoom_actor(
    self, painter: QPainter, zactor: ZoomActor, strip_rect: QRect
) -> None:
    from PySide6.QtGui import QLinearGradient, QBrush, QPolygonF
    from PySide6.QtCore import QPointF

    r = self._zoom_actor_rect(zactor, strip_rect)
    if r.width() < 2:
        return

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Body ??gradient that visually conveys the fade-in / hold /
    # fade-out shape: edges fade from a darker to a fuller blue,
    # so the trapezoid intent reads even before the user touches
    # the inner handles.
    in_x = self._ms_to_x(zactor.start_ms + zactor.zoom_in_ms)
    out_x = self._ms_to_x(zactor.end_ms - zactor.zoom_out_ms)
    # Clamp handles inside the actor rect so paint stays correct
    # even at min span / drag transitions.
    in_x = max(r.left() + 1, min(r.right() - 1, in_x))
    out_x = max(in_x, min(r.right() - 1, out_x))

    # Background fill ??light blue band.
    paint_studio_zoom_block(painter, r, configured=zactor.is_configured())

    # Trapezoid: dim outside the in/out handles to visualise the
    # ramp ??hold zones (held centre is brightest).
    held_rect = QRect(int(in_x), r.top() + 1,
                      max(1, int(out_x) - int(in_x)), r.height() - 2)
    painter.setBrush(QBrush(QColor(STUDIO_ACTION_HI)))
    painter.drawRect(held_rect)
    # Diagonal triangles for the in / out ramps so the user sees
    # the linear-time mapping.
    if in_x > r.left() + 1:
        ramp = QPolygonF([
            QPointF(r.left() + 1, r.bottom() - 1),
            QPointF(in_x, r.top() + 1),
            QPointF(in_x, r.bottom() - 1),
        ])
        ramp_color = QColor(STUDIO_ACTION)
        ramp_color.setAlpha(160)
        painter.setBrush(QBrush(ramp_color))
        painter.drawPolygon(ramp)
    if out_x < r.right() - 1:
        ramp = QPolygonF([
            QPointF(out_x, r.top() + 1),
            QPointF(r.right() - 1, r.bottom() - 1),
            QPointF(out_x, r.bottom() - 1),
        ])
        ramp_color = QColor(STUDIO_ACTION_EDGE)
        ramp_color.setAlpha(150)
        painter.setBrush(QBrush(ramp_color))
        painter.drawPolygon(ramp)

    # Outer border. Dashed when target rect not picked yet.
    border_color = QColor(STUDIO_ACTION_EDGE)
    pen = QPen(border_color, 2)
    painter.setPen(QPen(QColor("#FFFFFF")))
    painter.drawText(
        r.adjusted(6, 0, -6, 0),
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        "Zoom",
    )
    if not zactor.is_configured():
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(pen)
    painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

    # Inner fade handles ??tall white pins (drawn last so they
    # render on top of the gradient + ramp polys).
    for hx in (in_x, out_x):
        painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        handle_w = 4
        handle_h = r.height() - 4
        painter.drawRoundedRect(
            int(hx) - handle_w // 2, r.top() + 2,
            handle_w, handle_h, 1, 1,
        )

    # Marker + label.
    painter.setPen(QPen(QColor("#FFFFFF")))
    f = QFont(painter.font())
    f.setBold(True)
    f.setPointSize(8)
    painter.setFont(f)
    painter.setPen(QPen(QColor(255, 255, 255, 0)))
    if not zactor.is_configured():
        painter.drawText(
            r.adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            tr("veditor.zoom_actor.unconfigured"),
        )

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

def _paint_typography_actor(
    self, painter: QPainter, actor, strip_rect: QRect
) -> None:
    from PySide6.QtGui import QLinearGradient, QBrush

    r = self._typography_actor_rect(actor, strip_rect)
    if r.width() < 2:
        return

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Muted title/action strip. Keep this calmer than the preset swatch so
    # text actors sit inside the renewed timeline style instead of shouting.
    grad = QLinearGradient(r.left(), 0, r.right(), 0)
    grad.setColorAt(0.0, QColor(86, 80, 94, 178))
    grad.setColorAt(1.0, QColor(65, 72, 86, 168))
    painter.setBrush(QBrush(grad))

    border = QColor("#BDB1C8") if actor.id == self._typo_drag_actor_id else QColor("#807B88")
    painter.setPen(QPen(border, 1.2))
    painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

    # "T" badge + preview (leave room for the 4px edge handles so
    # text doesn't collide with them).
    painter.setPen(QPen(QColor("#F4F0EA")))
    f = QFont(painter.font())
    f.setBold(True)
    f.setPointSize(9)
    painter.setFont(f)
    painter.drawText(r.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, "T")
    preview = actor.display_text()
    if len(preview) > 18:
        preview = preview[:18] + "..."
    f.setBold(False)
    painter.setFont(f)
    painter.drawText(
        r.adjusted(20, 0, -8, 0),
        Qt.AlignmentFlag.AlignVCenter,
        preview,
    )

    key_times: set[int] = set()
    raw_keys = getattr(actor, "keyframes", None)
    if not isinstance(raw_keys, dict):
        animation = getattr(actor, "animation", None)
        custom = getattr(animation, "custom_params", {}) if animation is not None else {}
        raw_keys = custom.get("action_keyframes") if isinstance(custom, dict) else {}
    if isinstance(raw_keys, dict):
        for series in raw_keys.values():
            if isinstance(series, dict):
                series = series.get("keyframes") or series.get("keys") or []
            if not isinstance(series, (list, tuple)):
                continue
            for key in series:
                raw_time = None
                if isinstance(key, dict):
                    raw_time = key.get("time_ms", key.get("ms", key.get("t")))
                elif isinstance(key, (list, tuple)) and key:
                    raw_time = key[0]
                try:
                    t = int(round(float(raw_time)))
                except Exception:
                    continue
                key_times.add(t)
    if key_times and r.width() >= 36:
        duration = max(1, int(getattr(actor, "end_ms", 0)) - int(getattr(actor, "start_ms", 0)))
        start_ms = int(getattr(actor, "start_ms", 0))
        painter.setPen(QPen(QColor(20, 20, 24, 135), 1))
        painter.setBrush(QColor(232, 218, 178, 214))
        y = r.bottom() - 5
        for t in sorted(key_times)[:16]:
            rel = t - start_ms if start_ms <= t <= start_ms + duration else t
            rel = max(0, min(duration, rel))
            x = r.left() + int(round((rel / duration) * max(1, r.width() - 2))) + 1
            painter.drawPolygon(QPolygon([
                QPoint(x, y - 3),
                QPoint(x + 3, y),
                QPoint(x, y + 3),
                QPoint(x - 3, y),
            ]))
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    # Edge trim handles.
    dragging = self._typo_drag_actor_id == actor.id
    hover = self._hover_typo_actor_id == actor.id
    self._paint_edge_handles(
        painter,
        rect_top=r.top(),
        rect_h=r.height(),
        x_left=r.left() + 1,
        x_right=r.right() - 1,
        left_hot=(hover and self._hover_typo_side == "left")
            or (dragging and self._typo_drag_mode == "resize_l"),
        right_hot=(hover and self._hover_typo_side == "right")
            or (dragging and self._typo_drag_mode == "resize_r"),
        dragging=dragging,
        base_color=QColor(238, 235, 228, 205),
        accent_color=QColor("#CFC5D8"),
    )

