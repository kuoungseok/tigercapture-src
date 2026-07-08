"""Core editing, creative, actor, capture, and review adapter methods."""
from __future__ import annotations

from app.actions.editor_adapter_editing_audio import EditingAudioAdapterMixin
from app.actions.editor_adapter_editing_clip import EditingClipAdapterMixin
from app.actions.editor_adapter_editing_creative_actor import EditingCreativeActorAdapterMixin
from app.actions.editor_adapter_editing_review import EditingReviewAdapterMixin
from app.actions.editor_adapter_scalars import _bool, _float, _int


class EditingAdapterMixin(
    EditingClipAdapterMixin,
    EditingAudioAdapterMixin,
    EditingCreativeActorAdapterMixin,
    EditingReviewAdapterMixin,
):
    """Compatibility facade for registered editing action adapter methods."""


__all__ = ["EditingAdapterMixin", "_bool", "_float", "_int"]
