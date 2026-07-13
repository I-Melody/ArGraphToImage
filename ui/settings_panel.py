from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
)

from config import manager as config


class SettingsPanel(QWidget):
    api_key_changed = pyqtSignal(str)
    sort_scheme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self._build_ui()
        self._load_from_config()

    def _group_style(self):
        return """
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
        """

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ---- API key ----
        api_group = QGroupBox("联网 API")
        api_group.setStyleSheet(self._group_style())
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(6)

        api_label = QLabel("API Key")
        api_label.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        api_layout.addWidget(api_label)

        self.api_input = QLineEdit()
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setPlaceholderText("输入智谱 API Key ...")
        self.api_input.setStyleSheet("""
            QLineEdit {
                background: #12122a;
                color: #e0e0e0;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #5c7cfa; }
        """)
        api_layout.addWidget(self.api_input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_show = QPushButton("显示")
        self.btn_show.setCheckable(True)
        self.btn_show.setStyleSheet(self._btn_style())
        self.btn_show.toggled.connect(self._on_toggle_show)
        self.btn_save_key = QPushButton("保存")
        self.btn_save_key.setStyleSheet(self._btn_style(primary=True))
        self.btn_save_key.clicked.connect(self._on_save_key)
        btn_row.addWidget(self.btn_show)
        btn_row.addWidget(self.btn_save_key)
        api_layout.addLayout(btn_row)

        self.api_status = QLabel("")
        self.api_status.setStyleSheet("color: #0e9a4a; font-size: 11px;")
        api_layout.addWidget(self.api_status)

        layout.addWidget(api_group)

        # ---- Sort scheme ----
        sort_group = QGroupBox("排序方案")
        sort_group.setStyleSheet(self._group_style())
        sort_layout = QVBoxLayout(sort_group)
        sort_layout.setSpacing(6)

        self.sort_group_btns = QButtonGroup(self)
        self.radio_score = QRadioButton("总分优先")
        self.radio_score.setToolTip("按各模型总评分从高到低排序（同分同名次）")
        self.radio_incons = QRadioButton("不一致数量优先")
        self.radio_incons.setToolTip("按不一致维度数量从少到多排序（少者靠前，平局比总分）")
        for rb in (self.radio_score, self.radio_incons):
            rb.setStyleSheet("QRadioButton { color: #e0e0e0; font-size: 12px; padding: 2px; }")
        self.sort_group_btns.addButton(self.radio_score, 0)
        self.sort_group_btns.addButton(self.radio_incons, 1)
        sort_layout.addWidget(self.radio_score)
        sort_layout.addWidget(self.radio_incons)
        self.sort_group_btns.buttonClicked.connect(self._on_sort_changed)

        layout.addWidget(sort_group)
        layout.addStretch()

    def _btn_style(self, primary=False):
        if primary:
            return """
                QPushButton {
                    background: #0f3460; color: #e0e0e0;
                    border: 1px solid #5c7cfa; border-radius: 4px; padding: 6px 12px;
                }
                QPushButton:hover { background: #5c7cfa; color: #fff; }
            """
        return """
            QPushButton {
                background: #16213e; color: #a0a0b0;
                border: 1px solid #2a2a4a; border-radius: 4px; padding: 6px 12px;
            }
            QPushButton:hover { background: #1e2e50; color: #e0e0e0; }
            QPushButton:checked { background: #0f3460; color: #e0e0e0; }
        """

    def _load_from_config(self):
        self.api_input.setText(config.get("api.api_key", "") or "")
        scheme = config.get("sort_scheme", "score")
        if scheme == "inconsistency":
            self.radio_incons.setChecked(True)
        else:
            self.radio_score.setChecked(True)

    def _on_toggle_show(self, checked):
        self.api_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.btn_show.setText("隐藏" if checked else "显示")

    def _on_save_key(self):
        key = self.api_input.text().strip()
        cfg = config.load()
        cfg.setdefault("api", {})
        cfg["api"]["api_key"] = key
        config.save(cfg)
        self.api_status.setText("已保存" if key else "已清空")
        self.api_key_changed.emit(key)

    def _on_sort_changed(self):
        scheme = "inconsistency" if self.radio_incons.isChecked() else "score"
        cfg = config.load()
        cfg["sort_scheme"] = scheme
        config.save(cfg)
        self.sort_scheme_changed.emit(scheme)
