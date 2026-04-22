APP_QSS = """
QMainWindow, QWidget#Central {
    background-color: #f3f3f3;
}

QLabel#SectionLabel {
    color: #5a5a5a;
    font-size: 12px;
    font-weight: 600;
    padding-left: 2px;
}

QPushButton#NewCaptureButton {
    background-color: #0067c0;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 14px 24px;
    font-size: 15px;
    font-weight: 600;
}
QPushButton#NewCaptureButton:hover {
    background-color: #0078d4;
}
QPushButton#NewCaptureButton:pressed {
    background-color: #005a9e;
}
QPushButton#NewCaptureButton:disabled {
    background-color: #a9a9a9;
    color: #e0e0e0;
}

QPushButton[modeButton="true"] {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #e1e1e1;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
}
QPushButton[modeButton="true"]:hover {
    background-color: #f5f5f5;
    border-color: #c7c7c7;
}
QPushButton[modeButton="true"]:checked {
    background-color: #e6f0fb;
    border-color: #0067c0;
    color: #0067c0;
    font-weight: 600;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #e1e1e1;
    border-radius: 6px;
    padding: 6px 10px;
    min-width: 110px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #c7c7c7;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}

QCheckBox {
    color: #1a1a1a;
    font-size: 12px;
    spacing: 6px;
}

QFrame#Divider {
    background-color: #e1e1e1;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

QLabel#RecentEmpty {
    color: #8a8a8a;
    font-size: 12px;
    padding: 20px;
}

QPushButton#IconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 14px;
    min-width: 28px;
    min-height: 28px;
}
QPushButton#IconButton:hover {
    background-color: #ebebeb;
    border-color: #d9d9d9;
}
QPushButton#IconButton:pressed {
    background-color: #dcdcdc;
}

QLabel#AppTitle {
    color: #1a1a1a;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#DonateButton {
    background-color: transparent;
    color: #e54646;
    border: 1px solid #e54646;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#DonateButton:hover {
    background-color: #fff0f0;
    border-color: #c12828;
    color: #c12828;
}
QPushButton#DonateButton:pressed {
    background-color: #ffe0e0;
}

QLabel#CreditFooter {
    color: #3a3a3a;
    font-size: 11px;
    font-weight: 700;
    padding-top: 4px;
    letter-spacing: 0.5px;
}

QScrollArea#RecentStrip {
    background-color: transparent;
}
QWidget#RecentStripContainer {
    background-color: transparent;
}
QWidget#RecentCard {
    background-color: #ffffff;
    border: 1px solid #e1e1e1;
    border-radius: 6px;
}
QWidget#RecentCard:hover {
    border-color: #0067c0;
}
QLabel#RecentThumb {
    background-color: #f6f6f6;
    border-radius: 4px;
    color: #6a6a6a;
    font-size: 11px;
    font-weight: 600;
}
QLabel#RecentThumb[videoPlaceholder="true"] {
    background-color: #2a2a2a;
    color: #ffffff;
}
QLabel#RecentName {
    color: #1a1a1a;
    font-size: 11px;
}
QLabel#RecentMeta {
    color: #8a8a8a;
    font-size: 10px;
}

QPushButton#ToolButton {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #e1e1e1;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
}
QPushButton#ToolButton:hover {
    background-color: #f5f5f5;
    border-color: #c7c7c7;
}
QPushButton#ToolButton:pressed {
    background-color: #ececec;
}

QPushButton#PrimaryToolButton {
    background-color: #0067c0;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#PrimaryToolButton:hover {
    background-color: #0078d4;
}
QPushButton#PrimaryToolButton:pressed {
    background-color: #005a9e;
}

QWidget#PreviewHost {
    background-color: #2a2a2a;
    border-radius: 4px;
}

QLabel#StatusLabel {
    color: #5a5a5a;
    font-size: 11px;
}

QLabel#QuickPasteTarget {
    color: #5a5a5a;
    font-size: 11px;
    padding-left: 4px;
}
"""
