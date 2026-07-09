from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy


class TitleBar(QWidget):

    MARGIN = 6

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(36)
        self._parent = parent
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.MARGIN, 0, 0, 0)
        layout.setSpacing(0)

        self._title_label = QLabel("  数据标注辅助工作台")
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._btn_min = QPushButton("\u2014")
        self._btn_min.setObjectName("minButton")
        self._btn_min.setToolTip("最小化")
        self._btn_min.setFixedSize(36, 28)

        self._btn_max = QPushButton("\u25a1")
        self._btn_max.setObjectName("maxButton")
        self._btn_max.setToolTip("最大化")
        self._btn_max.setFixedSize(36, 28)

        self._btn_close = QPushButton("\u2715")
        self._btn_close.setObjectName("closeButton")
        self._btn_close.setToolTip("关闭")
        self._btn_close.setFixedSize(36, 28)

        self._btn_min.clicked.connect(self._on_minimize)
        self._btn_max.clicked.connect(self._on_maximize)
        self._btn_close.clicked.connect(self._on_close)

        layout.addWidget(self._title_label)
        layout.addWidget(self._btn_min)
        layout.addWidget(self._btn_max)
        layout.addWidget(self._btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            if self._parent.isMaximized():
                self._parent.showNormal()
            self._parent.move(self._parent.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._on_maximize()
        super().mouseDoubleClickEvent(event)

    def _on_minimize(self):
        self._parent.showMinimized()

    def _on_maximize(self):
        if self._parent.isMaximized():
            self._parent.showNormal()
            self._btn_max.setText("\u25a1")
        else:
            self._parent.showMaximized()
            self._btn_max.setText("\u2750")

    def _on_close(self):
        self._parent.close()

    def update_maximize_button(self, is_maximized):
        self._btn_max.setText("\u2750" if is_maximized else "\u25a1")

    def setWindowTitle(self, title):
        self._title_label.setText(title)
