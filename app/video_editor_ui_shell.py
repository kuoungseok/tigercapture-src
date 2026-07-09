from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QSplitter, QVBoxLayout, QWidget

from app.video_editor_layout_specs import (
    LEFT_DOCK_MIN_WIDTH,
    MAIN_DOCK_MAX_HEIGHT,
    MAIN_DOCK_MIN_HEIGHT,
    main_dock_splitter_qss,
    left_dock_scroll_qss,
    right_dock_scroll_qss,
)


def build_editor_shell(self):
    # Outer vertical layout: a compact top work area contains media,
    # viewer, workbench, and side tools; the frame editor/timeline spans
    # the full bottom width, matching the reference editor layout.
    outer = QVBoxLayout(self)
    outer.setContentsMargins(12, 10, 12, 12)
    outer.setSpacing(8)
    self._editor_outer_layout = outer

    self._main_dock_splitter = QSplitter(Qt.Orientation.Horizontal, self)
    self._main_dock_splitter.setObjectName("MainDockSplitter")
    self._main_dock_splitter.setChildrenCollapsible(False)
    self._main_dock_splitter.setHandleWidth(1)
    self._main_dock_splitter.setStyleSheet(main_dock_splitter_qss())
    self._main_dock_splitter.setMinimumHeight(MAIN_DOCK_MIN_HEIGHT)
    self._main_dock_splitter.setMaximumHeight(MAIN_DOCK_MAX_HEIGHT)
    outer.addWidget(self._main_dock_splitter, stretch=0)

    # Left = media pool dock. DaVinci-style: imported clips live
    # here, drag them onto a track to add to the timeline.
    self._left_dock_host = QWidget(self._main_dock_splitter)
    self._left_dock_host.setObjectName("LeftDockColumn")
    self._left_dock_host.setMinimumWidth(LEFT_DOCK_MIN_WIDTH)
    self._left_dock_scroll = QScrollArea(self._main_dock_splitter)
    self._left_dock_scroll.setObjectName("LeftDockScroll")
    self._left_dock_scroll.setWidgetResizable(True)
    self._left_dock_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self._left_dock_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._left_dock_scroll.setFrameShape(QFrame.Shape.NoFrame)
    self._left_dock_scroll.setMinimumWidth(LEFT_DOCK_MIN_WIDTH)
    self._left_dock_scroll.setStyleSheet(left_dock_scroll_qss())
    left_dock_layout = QVBoxLayout(self._left_dock_host)
    left_dock_layout.setContentsMargins(0, 0, 0, 0)
    left_dock_layout.setSpacing(10)
    self._left_dock_layout = left_dock_layout
    self._left_dock_scroll.setWidget(self._left_dock_host)
    self._main_dock_splitter.addWidget(self._left_dock_scroll)

    # Center = main work area. ``root`` (QVBoxLayout) is preserved
    # as the local name everything below appends to, so the rest
    # of the build flow keeps reading naturally.
    main_col = QWidget(self._main_dock_splitter)
    main_col.setObjectName("CenterWorkbench")
    self._center_workbench = main_col
    root = QVBoxLayout(main_col)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(10)
    self._main_dock_splitter.addWidget(main_col)

    # Unified Workbench stack. The main Workbench and its secondary
    # sections live in this single scroll area so wheel scrolling moves
    # the node/inspector area and the lower tools as one surface.
    self._right_dock_scroll = QScrollArea(main_col)
    self._right_dock_scroll.setObjectName("RightDockScroll")
    self._right_dock_scroll.setWidgetResizable(True)
    self._right_dock_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self._right_dock_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._right_dock_scroll.setFrameShape(QFrame.Shape.NoFrame)
    self._right_dock_scroll.setMinimumWidth(0)
    self._right_dock_scroll.setMinimumHeight(48)
    self._right_dock_scroll.setMaximumHeight(16777215)
    self._right_dock_scroll.setStyleSheet(right_dock_scroll_qss())
    self._right_dock_host = QWidget(self._right_dock_scroll)
    self._right_dock_host.setObjectName("RightDockColumn")
    self._right_dock_host.setMinimumWidth(0)
    right_dock_layout = QVBoxLayout(self._right_dock_host)
    right_dock_layout.setContentsMargins(0, 0, 0, 0)
    right_dock_layout.setSpacing(2)
    self._right_dock_layout = right_dock_layout
    self._right_dock_scroll.setWidget(self._right_dock_host)
    self._right_dock_scroll.hide()

    # Stretch factors: the centre column is now the canvas + workbench.
    # Secondary panels no longer steal a right-side splitter column.
    self._main_dock_splitter.setStretchFactor(0, 1)
    self._main_dock_splitter.setStretchFactor(1, 7)
    # Default sizes; user-dragged sizes are persisted via Qt's
    # splitter state if we wire it later.
    self._main_dock_splitter.setSizes([188, 1240])
    self._yield_startup_ui("shell_splitters")
    return main_col, root
