from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QWidget

from app.style import editor_scrollbar_qss


def make_workbench_section_scroll_area(
    parent: QWidget,
    content: QWidget,
    *,
    object_name: str,
    min_content_height: int = 0,
) -> QScrollArea:
    """Wrap a long workbench section body without changing its panel API."""
    scroll = QScrollArea(parent)
    scroll.setObjectName(object_name)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    scroll.setStyleSheet(
        f"QScrollArea#{object_name}{{background:#101112;border:0px solid transparent;}}"
        f"QScrollArea#{object_name} > QWidget > QWidget{{background:#101112;}}"
        + editor_scrollbar_qss(f"QScrollArea#{object_name}")
    )
    if min_content_height > 0:
        content.setMinimumHeight(
            max(
                int(content.minimumHeight()),
                int(content.sizeHint().height()),
                int(min_content_height),
            )
        )
    content.setParent(scroll)
    scroll.setWidget(content)
    return scroll
