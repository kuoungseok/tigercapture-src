MOTION_DESIGNER_QSS = """
* { font-family: "Segoe UI"; font-size: 11px; letter-spacing: 0; }
QMainWindow#MotionDesignerWindow { background: #111317; color: #e4e7eb; }
QDockWidget#MotionAIDock {
  background: #121419; color: #e4e7eb; border-left: 1px solid #30353d;
}
QDockWidget#MotionAIDock::title {
  background: #1a1d22; color: #d7dbe1; padding: 5px 8px; text-align: left;
}
QLabel { color: #cbd0d8; }
QLabel:disabled { color: #686f79; }
QToolBar {
  background: #1b1e23; border: 0; border-bottom: 1px solid #30353d;
  spacing: 2px; padding: 2px 5px;
}
QToolBar::separator { background: #353a43; width: 1px; margin: 5px; }
QToolButton {
  color: #d9dde3; min-width: 26px; min-height: 24px;
  border: 1px solid transparent; border-radius: 3px; padding: 2px 6px;
}
QToolButton:hover { background: #292e36; border-color: #414853; }
QToolButton:checked { background: #283944; border-color: #4c7a8e; }
QToolButton#MotionTrackingButton {
  background: #232830; border: 1px solid #3b434e; border-radius: 3px;
  min-height: 24px; padding: 2px 8px;
}
QToolButton#MotionTrackingButton:hover { background: #2c333d; border-color: #5b6877; }
QWidget#MotionTransport {
  background: #171a1f; border: 1px solid #3a424d; border-radius: 3px;
}
QToolButton#MotionTransportButton {
  color: #eef1f5; background: #232830; border: 1px solid #3b434e;
  border-radius: 2px; padding: 0; min-width: 27px; max-width: 27px;
  min-height: 25px; max-height: 25px;
}
QToolButton#MotionTransportButton:hover {
  background: #303741; border-color: #657282;
}
QToolButton#MotionTransportButton:checked {
  background: #2f6178; border-color: #66a8c2;
}
QMenu { background: #20242a; color: #e7e9ed; border: 1px solid #414750; padding: 3px; }
QMenu::item { padding: 5px 24px 5px 8px; }
QMenu::item:selected { background: #315369; }
QSplitter::handle { background: #30343b; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QTreeWidget, QListWidget, QTableWidget, QGraphicsView, QWidget#InspectorPanel {
  background: #121419; color: #d7dbe1; border: 0;
  selection-background-color: #2d5368; selection-color: #ffffff;
}
QWidget#MotionVectorPanel,
QScrollArea#MotionInspectorScroll,
QWidget#MotionInspectorViewport,
QWidget#MotionInspectorContent {
  background: #121419; color: #d7dbe1; border: 0;
}
QTreeWidget::item, QListWidget::item { min-height: 22px; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #2d5368; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #242a31; }
QHeaderView::section {
  background: #1a1d22; color: #aeb5bf; border: 0;
  border-right: 1px solid #30353d; border-bottom: 1px solid #30353d; padding: 4px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #1c2026; color: #edf0f4; border: 1px solid #343b45;
  border-radius: 3px; min-height: 22px; padding: 1px 5px;
}
QTextEdit, QPlainTextEdit {
  background: #171a1f; color: #edf0f4; border: 1px solid #343b45;
  border-radius: 3px; padding: 5px; selection-background-color: #315369;
}
QPlainTextEdit#MotionAIPrompt, QPlainTextEdit#MotionAIResult {
  background: #171a1f; color: #edf0f4; border: 1px solid #343b45;
  border-radius: 3px; padding: 7px; selection-background-color: #315369;
}
QPlainTextEdit#MotionAIPrompt:focus { border-color: #4f8197; }
QListWidget#MotionAIReferences {
  background: #15181d; border: 1px dashed #3d4651; border-radius: 3px;
  padding: 2px; selection-background-color: #2d5368;
}
QLabel#MotionAIHeading { color: #f0f2f5; font-weight: 700; }
QLabel#MotionAIStatus { color: #76b4cb; font-size: 10px; }
QLabel#MotionAIHint { color: #7e8792; font-size: 10px; }
QToolButton#MotionAIIconButton {
  min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
  background: #1c2026; border: 1px solid #343b45; border-radius: 3px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #4f8197; }
QPushButton {
  background: #232830; color: #edf0f4; border: 1px solid #3b434e;
  border-radius: 3px; min-height: 24px; padding: 3px 8px;
}
QPushButton:hover { background: #2c333d; border-color: #4a5563; }
QPushButton#MotionPrimaryButton { background: #2d5c72; border-color: #427d96; }
QPushButton#MotionPrimaryButton:hover { background: #386d84; }
QPushButton#MotionPrimaryButton:disabled { color: #77808a; background: #20252b; border-color: #303741; }
QSlider::groove:horizontal { height: 3px; background: #343a43; }
QSlider::sub-page:horizontal { background: #4f8197; }
QSlider::handle:horizontal { width: 10px; margin: -4px 0; background: #d2d7dd; border-radius: 5px; }
QTabWidget::pane { border: 0; border-top: 1px solid #30353d; background: #121419; }
QTabBar::tab {
  background: #191c21; color: #aeb4bd; border: 0; min-height: 22px;
  padding: 3px 11px;
}
QTabBar::tab:hover { color: #f0f2f5; background: #22272e; }
QTabBar::tab:selected { color: #ffffff; background: #20242a; border-bottom: 2px solid #55a5c1; }
QWidget#MotionViewerHeader { background: #171a1f; border-bottom: 1px solid #30353d; }
QLabel#MotionTimecode { color: #d8dde3; font-size: 13px; min-width: 76px; padding: 0 5px; }
QLabel#MotionInspectorSection { color: #f0f2f5; font-weight: 600; padding-top: 8px; }
QListWidget#MotionGraphProperties { background: #15181d; border-right: 1px solid #30353d; }
QWidget#MotionLibraryPanel QListWidget::item { padding: 4px; }
QScrollBar:vertical { background: #171a1f; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #424954; min-height: 24px; border-radius: 3px; }
QScrollBar:horizontal { background: #171a1f; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #424954; min-width: 24px; border-radius: 3px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
"""
