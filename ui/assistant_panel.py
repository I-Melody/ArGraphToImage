from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QGroupBox,
    QHBoxLayout,
)


class AssistantPanel(QWidget):
    recognize_clicked = pyqtSignal()
    transform_clicked = pyqtSignal()
    remove_clicked = pyqtSignal()
    capture_rank_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        actions_group = QGroupBox("Actions")
        actions_group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #a0a0b0;
            }
        """)
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(6)

        self.btn_recognize = QPushButton("Recognize Page")
        self.btn_recognize.setObjectName("btn_recognize")
        self.btn_recognize.setStyleSheet("""
            QPushButton#btn_recognize {
                background: #e94560;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#btn_recognize:hover {
                background: #d63850;
            }
            QPushButton#btn_recognize:disabled {
                background: #3a1a2e;
                color: #606070;
            }
        """)
        self.btn_recognize.clicked.connect(self.recognize_clicked.emit)
        actions_layout.addWidget(self.btn_recognize)

        self.btn_transform = QPushButton("Apply Tabbed Layout")
        self.btn_transform.setStyleSheet("""
            QPushButton {
                background: #0f3460;
                color: #e0e0e0;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #5c7cfa;
            }
        """)
        self.btn_transform.clicked.connect(self.transform_clicked.emit)
        actions_layout.addWidget(self.btn_transform)

        self.btn_remove = QPushButton("Remove Layout")
        self.btn_remove.setStyleSheet("""
            QPushButton {
                background: #16213e;
                color: #a0a0b0;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #1e2e50;
                color: #e0e0e0;
            }
        """)
        self.btn_remove.clicked.connect(self.remove_clicked.emit)
        actions_layout.addWidget(self.btn_remove)

        self.btn_capture = QPushButton("抓取排序")
        self.btn_capture.setToolTip("抓取原页面排序栏结构（输出到信息面板 + rank_snapshot.json）")
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background: #2a2a5a;
                color: #c0c0e0;
                border: 1px solid #5c7cfa;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #3a3a6a;
                color: #ffffff;
            }
        """)
        self.btn_capture.clicked.connect(self.capture_rank_clicked.emit)
        actions_layout.addWidget(self.btn_capture)

        layout.addWidget(actions_group)

        info_group = QGroupBox("Recognition Results")
        info_group.setStyleSheet(actions_group.styleSheet())
        info_layout = QVBoxLayout(info_group)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Element", "Details"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background: #16213e;
                color: #e0e0e0;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #1e1e3a;
            }
            QTreeWidget::item:selected {
                background: #0f3460;
            }
            QTreeWidget QHeaderView::section {
                background: #1a1a2e;
                color: #a0a0b0;
                border: none;
                border-bottom: 1px solid #2a2a4a;
                padding: 4px;
            }
        """)
        info_layout.addWidget(self.tree)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #a0a0b0; font-size: 11px; padding: 4px;")
        info_layout.addWidget(self.status_label)

        layout.addWidget(info_group)

        log_group = QGroupBox("Log")
        log_group.setStyleSheet(actions_group.styleSheet())
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background: #12122a;
                color: #a0a0b0;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        log_layout.addWidget(self.log_output)

        layout.addWidget(log_group)
        layout.addStretch()

    def show_recognition_result(self, result):
        self.tree.clear()
        if not result.matched:
            self.status_label.setText("No annotation page detected")
            return

        root = QTreeWidgetItem(self.tree, ["Page Type", result.page_type])
        root.setExpanded(True)

        ref = result.reference_image
        if ref:
            ref_item = QTreeWidgetItem(root, ["Reference Image", ref.title])
            QTreeWidgetItem(ref_item, ["ID", ref.id])
            QTreeWidgetItem(ref_item, ["Src", ref.image_src[:60] + "..."])

        models_root = QTreeWidgetItem(root, [f"Models ({result.model_count})", ""])
        for group in result.model_groups:
            model_item = QTreeWidgetItem(models_root, [f"Model {group.model_letter}", ""])
            if group.image:
                QTreeWidgetItem(model_item, ["Image", group.image.id])
            dims_item = QTreeWidgetItem(model_item, ["Dimensions", str(len(group.dimensions))])
            for d in group.dimensions:
                checked = ", ".join(d.checked_values) if d.checked_values else "none"
                QTreeWidgetItem(dims_item, [d.label[:40], checked])

        rank_root = QTreeWidgetItem(root, ["Rank Items", str(len(result.rank_items))])
        for r in result.rank_items:
            QTreeWidgetItem(rank_root, [r.get("model", ""), f"Pos: {r['position']}"])

        models_root.setExpanded(True)
        rank_root.setExpanded(False)

        self.status_label.setText(f"Detected: {result.model_count} models, {result.dimension_count} dimensions")

    def log(self, message):
        self.log_output.append(message)

    def set_status(self, text):
        self.status_label.setText(text)
