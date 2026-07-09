THEME_QSS = """
/* ===== Global ===== */
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

/* ===== Main Window ===== */
QMainWindow {
    background-color: #1a1a2e;
    border: 1px solid #2a2a4a;
}

/* ===== Title Bar ===== */
QWidget#titleBar {
    background-color: #0d0d1a;
    border-bottom: 1px solid #2a2a4a;
}

QWidget#titleBar QLabel {
    color: #c0c0c0;
    font-size: 13px;
    padding-left: 8px;
}

QWidget#titleBar QPushButton {
    background-color: transparent;
    border: none;
    color: #c0c0c0;
    font-size: 14px;
    padding: 4px 10px;
    border-radius: 0px;
}

QWidget#titleBar QPushButton:hover {
    background-color: #2a2a4a;
}

QWidget#titleBar QPushButton#closeButton:hover {
    background-color: #e94560;
    color: #ffffff;
}

/* ===== URL Bar ===== */
QWidget#urlBar {
    background-color: #16213e;
    border-bottom: 1px solid #2a2a4a;
    padding: 4px;
}

QWidget#urlBar QPushButton {
    background-color: transparent;
    border: none;
    color: #a0a0b0;
    font-size: 16px;
    padding: 4px 8px;
    border-radius: 4px;
    min-width: 28px;
    min-height: 24px;
}

QWidget#urlBar QPushButton:hover {
    background-color: #0f3460;
    color: #e0e0e0;
}

QWidget#urlBar QPushButton:pressed {
    background-color: #0a2550;
}

QWidget#urlBar QLineEdit {
    background-color: #0d0d1a;
    color: #e0e0e0;
    border: 1px solid #2a2a4a;
    border-radius: 6px;
    padding: 4px 10px;
    selection-background-color: #0f3460;
    font-size: 13px;
}

QWidget#urlBar QLineEdit:focus {
    border-color: #5c7cfa;
}

/* ===== Browser Area ===== */
QWidget#browserContainer {
    background-color: #1a1a2e;
}

/* ===== Scroll Bars ===== */
QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 8px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #2a2a4a;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3a3a5a;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1a1a2e;
    height: 8px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #2a2a4a;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3a3a5a;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===== Tool Tips ===== */
QToolTip {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2a2a4a;
    padding: 4px 8px;
    border-radius: 4px;
}

/* ===== Status Bar ===== */
QStatusBar {
    background-color: #0d0d1a;
    color: #a0a0b0;
    border-top: 1px solid #2a2a4a;
    font-size: 12px;
}

/* ===== Splitter ===== */
QSplitter::handle {
    background-color: #2a2a4a;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}

/* ===== Menu ===== */
QMenuBar {
    background-color: #0d0d1a;
    color: #e0e0e0;
    border-bottom: 1px solid #2a2a4a;
}

QMenuBar::item:selected {
    background-color: #0f3460;
}

QMenu {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2a2a4a;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0f3460;
}

QMenu::separator {
    height: 1px;
    background-color: #2a2a4a;
    margin: 4px 8px;
}
"""
