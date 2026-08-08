from __future__ import annotations


AI_COMMAND_HOST_OPEN_HEIGHT = 136
AI_COMMAND_HOST_CLOSED_HEIGHT = 37
AI_COMMAND_DOCK_MIN_HEIGHT = 90
AI_COMMAND_DOCK_MAX_HEIGHT = 96


AI_COMMAND_DOCK_QSS = """
QWidget#AICommandDock {
    background: #101112;
    border: 1px solid #22262B;
    border-radius: 5px;
}
QLabel#AICommandBadge {
    color: #FFFFFF;
    background: #252A31;
    border: 1px solid rgba(220,225,238,42);
    border-radius: 5px;
    font-weight: 760;
    letter-spacing: 0px;
    font-size: 10px;
}
QLabel#AICommandStatus {
    color: rgba(204, 211, 232, 205);
    font-size: 10px;
    font-weight: 700;
}
QComboBox#AICommandProviderCombo {
    color: #E9ECF7;
    background: #111316;
    border: 1px solid #2B3037;
    border-radius: 4px;
    padding: 1px 16px 1px 6px;
    font-size: 10px;
    font-weight: 620;
}
QComboBox#AICommandProviderCombo:hover {
    border-color: #565F6E;
    background: #171A1F;
}
QPlainTextEdit#AICommandChatLog {
    color: #E7EBF8;
    background: rgba(6, 8, 15, 178);
    border: 1px solid rgba(98, 105, 145, 80);
    border-radius: 14px;
    padding: 5px 9px;
    selection-background-color: #7A63FF;
    selection-color: #FFFFFF;
    font-weight: 720;
}
QLineEdit#AICommandInput {
    color: #EFF2FF;
    background: #111316;
    border: 1px solid #2B3037;
    border-radius: 4px;
    padding: 1px 6px;
    selection-background-color: #7A63FF;
    selection-color: #FFFFFF;
    font-weight: 520;
    font-size: 10px;
}
QLineEdit#AICommandInput:focus {
    border: 1px solid #616C7D;
    background: #171A1F;
}
QPushButton#AICommandRunButton {
    color: #FFFFFF;
    background: #2A3038;
    border: 1px solid #48515E;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: 680;
}
QPushButton#AICommandReviewButton {
    color: #DDE3F7;
    background: #15181D;
    border: 1px solid #2B3037;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: 620;
}
QToolButton#AICommandIconButton {
    color: #DDE3F7;
    background: #15181D;
    border: 1px solid #2B3037;
    border-radius: 4px;
    padding: 0px;
    font-weight: 620;
}
QPushButton#AICommandReviewButton:hover,
QToolButton#AICommandIconButton:hover {
    background: #20242B;
    border-color: #565F6E;
}
"""
