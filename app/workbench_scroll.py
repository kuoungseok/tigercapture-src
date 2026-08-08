from __future__ import annotations

from PySide6.QtWidgets import QAbstractScrollArea, QWidget


def forward_wheel_to_scroll_area(
    source: QWidget,
    event,
    *,
    object_name: str = "RightDockScroll",
) -> bool:
    """Scroll a nearby named QScrollArea from a child that owns wheel focus."""
    if source is None or event is None:
        return False
    try:
        pixel_delta = int(event.pixelDelta().y())
    except Exception:
        pixel_delta = 0
    try:
        angle_delta = int(event.angleDelta().y())
    except Exception:
        angle_delta = 0
    if pixel_delta == 0 and angle_delta == 0:
        return False
    amount = -pixel_delta if pixel_delta else -angle_delta
    if amount == 0:
        return False

    seen: set[int] = set()
    node: QWidget | None = source
    while node is not None:
        candidates: list[QAbstractScrollArea] = []
        if isinstance(node, QAbstractScrollArea) and node.objectName() == object_name:
            candidates.append(node)
        try:
            candidates.extend(node.findChildren(QAbstractScrollArea, object_name))
        except Exception:
            pass
        for scroll in candidates:
            ident = id(scroll)
            if ident in seen:
                continue
            seen.add(ident)
            try:
                bar = scroll.verticalScrollBar()
                old_value = int(bar.value())
                if bar.maximum() <= bar.minimum():
                    continue
                bar.setValue(old_value + amount)
                if int(bar.value()) != old_value:
                    event.accept()
                    return True
            except Exception:
                continue
        try:
            node = node.parentWidget()
        except Exception:
            node = None
    return False
