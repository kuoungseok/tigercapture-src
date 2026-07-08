from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.i18n import tr
from app.typography import TextClip
from app.video_editor_typography_dialogs import TypographyEditorDialog


def _find_typography_actor(self, clip_id: int) -> "tuple[VideoTrack, TextClip] | None":
    """Locate a typography actor by its id across every video track."""
    for track in self._tracks:
        for clip in getattr(track, "typography_actors", []):
            if clip.id == clip_id:
                return track, clip
    return None


def _ensure_text_preview_label(self) -> QLabel:
    """Lazily create the preview QLabel used for the active text clip."""
    if self._text_preview_label is None:
        lbl = QLabel(self._drawing_canvas)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.hide()
        self._text_preview_label = lbl
    labels = list(getattr(self, "_text_preview_labels", []) or [])
    if not labels:
        labels = [self._text_preview_label]
        self._text_preview_labels = labels
    return self._text_preview_label


def _ensure_text_preview_labels(self, count: int) -> list[QLabel]:
    first = _ensure_text_preview_label(self)
    labels = list(getattr(self, "_text_preview_labels", []) or [first])
    while len(labels) < max(1, int(count)):
        lbl = QLabel(self._drawing_canvas)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.hide()
        labels.append(lbl)
    self._text_preview_labels = labels
    return labels


def _update_text_clip_overlay(self, pos_ms: int) -> None:
    """Show / hide / restyle the preview text based on active
    typography actors at ``pos_ms``. This lightweight live overlay mirrors the
    current active text stack so catalog/review captures and editor preview do
    not collapse multiple title layers into a single caption.

    Typography actors live per-VideoTrack in track-local source ms.
    Active-check: track-local time = project_ms - track.offset_ms,
    valid when 0 <= local < track.duration_ms and actor.contains(local).
    """
    project_ms = int(pos_ms)

    active: list[TextClip] = []
    for track in self._tracks:
        clips = list(getattr(track, "clips", []) or [])
        has_source = getattr(track, "source_path", None) is not None or any(
            getattr(clip, "source_path", None) is not None for clip in clips
        )
        track_duration = int(getattr(track, "duration_ms", 0) or 0)
        if track_duration <= 0 and clips:
            track_duration = max(
                (int(getattr(clip, "timeline_out_ms", 0) or 0) for clip in clips),
                default=0,
            )
        if not has_source or track_duration <= 0:
            continue
        local = project_ms - int(getattr(track, "offset_ms", 0) or 0)
        if local < 0 or local >= track_duration:
            continue
        for clip in getattr(track, "typography_actors", []):
            if clip.contains(local):
                active.append(clip)

    labels = _ensure_text_preview_labels(self, len(active) if active else 1)

    if not active:
        for lbl in labels:
            lbl.hide()
        return

    canvas = self._drawing_canvas
    cw, ch = canvas.width(), canvas.height()
    if cw <= 0 or ch <= 0:
        for lbl in labels:
            lbl.hide()
        return

    for idx, clip in enumerate(active):
        lbl = labels[idx]
        style = clip.style
        font = QFont(style.font_family, max(8, int(style.font_size * ch / 1080.0)))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if getattr(style, "letter_spacing", 0):
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(style.letter_spacing))
        lbl.setFont(font)
        if style.alignment == "left":
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif style.alignment == "right":
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        css = [
            f"background: {style.background_color or 'transparent'};",
            f"color: {style.color or '#FFFFFF'};",
            f"font-weight: {int(style.font_weight)};",
        ]
        if style.background_radius:
            css.append(f"border-radius: {max(0, int(style.background_radius))}px;")
        if style.background_padding:
            pad = max(0, int(style.background_padding))
            css.append(f"padding: {pad}px;")
        lbl.setStyleSheet(" ".join(css))
        lbl.setText(clip.display_text())
        lbl.adjustSize()

        lw = min(int(cw * 0.92), max(int(cw * 0.24), lbl.width()))
        lh = max(28, lbl.height())
        cx = int(style.position_x * cw)
        cy = int(style.position_y * ch)
        lbl.setGeometry(cx - lw // 2, cy - lh // 2, lw, lh)
        lbl.show()
        lbl.raise_()

    for lbl in labels[len(active):]:
        lbl.hide()


def _on_typography_actor_selected(self, track_id: int, actor_id: int) -> None:
    """Store selected typography actor for Delete key handling."""
    self._selected_typo = (track_id, actor_id)


def _delete_selected_typo_actor(self) -> None:
    """Delete the currently selected typography actor."""
    sel = getattr(self, "_selected_typo", None)
    if sel is None:
        return
    track_id, actor_id = sel
    track = self._find_track(track_id)
    if track is None:
        return
    actors = getattr(track, "typography_actors", [])
    new_actors = [actor for actor in actors if actor.id != actor_id]
    if len(new_actors) == len(actors):
        return
    track.typography_actors = new_actors
    self._selected_typo = None
    row = self._track_rows.get(track_id)
    if row is not None:
        row.update()
    self._update_text_clip_overlay(self._player.position())
    self._register_change("delete typography actor")


def _on_typography_changed(self, track_id: int) -> None:
    """Called after any drag/resize/drop/add/remove of a typography
    actor on any video track."""
    self._update_tracks_host_width()
    self._update_text_clip_overlay(self._player.position())


def _open_typography_editor(self, track_id: int, clip_id: int) -> None:
    """Double-click handler ??opens the (Phase 1 stub) editor for
    the typography actor. Phase 2 replaces this with the full 3-pane
    modal."""
    found = self._find_typography_actor(clip_id)
    if found is None:
        return
    _track, clip = found
    dlg = TypographyEditorDialog(clip, self)
    if dlg.exec() == dlg.DialogCode.Accepted:
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._update_text_clip_overlay(self._player.position())


def _show_typography_menu(self, track_id: int, clip_id: int, global_pos) -> None:
    from PySide6.QtWidgets import QMenu

    found = self._find_typography_actor(clip_id)
    if found is None:
        return
    track, clip = found
    menu = QMenu(self)
    a_edit = menu.addAction(tr("veditor.typo_menu.edit"))
    a_dup = menu.addAction(tr("veditor.typo_menu.duplicate"))
    menu.addSeparator()
    a_del = menu.addAction(tr("veditor.typo_menu.delete"))

    chosen = menu.exec(global_pos)
    if chosen is a_edit:
        self._open_typography_editor(track_id, clip_id)
    elif chosen is a_dup:
        import copy
        dup = copy.deepcopy(clip)
        from app.typography import _next_id
        dup.id = _next_id()
        # Nudge so the copy shows up after the original.
        dup.start_ms = clip.end_ms
        dup.end_ms = dup.start_ms + clip.duration_ms
        if dup.end_ms > track.duration_ms:
            dup.end_ms = track.duration_ms
            dup.start_ms = max(0, dup.end_ms - clip.duration_ms)
        track.typography_actors.append(dup)
        track.typography_actors.sort(key=lambda c: c.start_ms)
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._on_typography_changed(track_id)
    elif chosen is a_del:
        track.typography_actors = [
            c for c in track.typography_actors if c.id != clip_id
        ]
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._on_typography_changed(track_id)
