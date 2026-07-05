from __future__ import annotations

from app.simple_video_player import PlayerState
from app.drawing import SpeechBubble, SpeechBubbleItem


def _open_paint_dialog(self) -> None:
    if not self._ensure_preview_pixmap_for_paint():
        return
    # Pause playback while drawing so the background stays fixed.
    was_playing = self._player.state() is PlayerState.PLAYING
    if was_playing:
        self._player.pause()

    from app.drawing import PaintDialog

    # Hide preview bubble / sticker items while editing in the
    # dialog; respawn after so the dialog owns the interactive
    # version during the edit.
    for item in list(self._bubble_items):
        item.deleteLater()
    self._bubble_items.clear()
    for item in list(self._sticker_items):
        item.deleteLater()
    self._sticker_items.clear()

    dlg = PaintDialog(
        background_pixmap=self._preview_pixmap,
        initial_strokes=self._strokes,
        time_ms=self._player.position(),
        parent=self,
        initial_bubbles=self._bubbles,
        initial_stickers=self._stickers,
    )
    if dlg.exec() == dlg.DialogCode.Accepted:
        self._strokes = dlg.result_strokes()
        self._bubbles = dlg.result_bubbles()
        self._stickers = dlg.result_stickers()
        self._drawing_canvas.update()
    # Respawn passive items so the user sees bubbles / stickers on
    # the preview.
    for sticker in self._stickers:
        self._spawn_sticker_item(sticker)
    for bubble in self._bubbles:
        self._spawn_bubble_item(bubble)
    self._update_bubble_visibility(self._player.position())
    self._update_sticker_visibility(self._player.position())


def _spawn_bubble_item(self, bubble: SpeechBubble) -> SpeechBubbleItem:
    item = SpeechBubbleItem(bubble, self._drawing_canvas)
    item.sync_to_parent()
    item.show()
    item.moved.connect(lambda it=item: it.sync_to_bubble())
    item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
    self._bubble_items.append(item)
    return item


def _remove_bubble(self, bubble: SpeechBubble, item: SpeechBubbleItem) -> None:
    try:
        self._bubbles.remove(bubble)
    except ValueError:
        pass
    try:
        self._bubble_items.remove(item)
    except ValueError:
        pass
    item.deleteLater()


def _resync_bubbles_to_preview(self) -> None:
    for item in self._bubble_items:
        item.sync_to_parent()


def _update_bubble_visibility(self, pos_ms: int) -> None:
    for item in self._bubble_items:
        item.setVisible(item.bubble.start_ms <= int(pos_ms))


def _spawn_sticker_item(self, sticker):
    from app.drawing import StickerItem

    item = StickerItem(sticker, self._drawing_canvas)
    item.sync_to_parent()
    item.show()
    item.moved.connect(lambda it=item: it.sync_to_sticker())
    item.deleted.connect(lambda it=item, s=sticker: self._remove_sticker(s, it))
    item.duplicated.connect(lambda s=sticker: self._duplicate_sticker(s))
    item.raise_requested.connect(lambda s=sticker: self._reorder_sticker(s, +1))
    item.lower_requested.connect(lambda s=sticker: self._reorder_sticker(s, -1))
    self._sticker_items.append(item)
    for b_item in self._bubble_items:
        b_item.raise_()
    return item


def _remove_sticker(self, sticker, item) -> None:
    try:
        self._stickers.remove(sticker)
    except ValueError:
        pass
    try:
        self._sticker_items.remove(item)
    except ValueError:
        pass
    item.deleteLater()


def _duplicate_sticker(self, sticker) -> None:
    import copy

    dup = copy.deepcopy(sticker)
    dup.x_norm = min(0.95, dup.x_norm + 0.03)
    dup.y_norm = min(0.95, dup.y_norm + 0.03)
    current_max = max((s.z_index for s in self._stickers), default=0)
    dup.z_index = current_max + 1
    self._stickers.append(dup)
    self._spawn_sticker_item(dup)
    self._update_sticker_visibility(self._player.position())


def _reorder_sticker(self, sticker, direction: int) -> None:
    if direction > 0:
        sticker.z_index = max(
            (s.z_index for s in self._stickers if s is not sticker),
            default=0,
        ) + 1
    else:
        sticker.z_index = min(
            (s.z_index for s in self._stickers if s is not sticker),
            default=0,
        ) - 1
    self._sticker_items.sort(key=lambda it: int(it.sticker.z_index))
    for item in self._sticker_items:
        item.raise_()
    for b_item in self._bubble_items:
        b_item.raise_()


def _resync_stickers_to_preview(self) -> None:
    for item in self._sticker_items:
        item.sync_to_parent()


def _update_sticker_visibility(self, pos_ms: int) -> None:
    from app.drawing import _sticker_active

    t = int(pos_ms)
    for item in self._sticker_items:
        item.setVisible(_sticker_active(item.sticker, t))

