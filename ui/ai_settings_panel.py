from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QComboBox,
    QCheckBox,
)

from config import manager as config


class AiSettingsPanel(QWidget):
    api_key_changed = pyqtSignal(str)
    ai_model_changed = pyqtSignal(str)
    auto_fill_model_changed = pyqtSignal(bool)
    auto_fill_a3_changed = pyqtSignal(bool)
    auto_fill_a4_changed = pyqtSignal(bool)
    auto_fill_a2_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
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

        ai_model_label = QLabel("AI 模型")
        ai_model_label.setStyleSheet("color: #a0a0b0; font-size: 11px; margin-top: 6px;")
        api_layout.addWidget(ai_model_label)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setStyleSheet("""
            QComboBox {
                background: #12122a;
                color: #e0e0e0;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 12px;
            }
            QComboBox:focus { border-color: #5c7cfa; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #12122a;
                color: #e0e0e0;
                border: 1px solid #2a2a4a;
                selection-background-color: #0f3460;
                outline: none;
            }
        """)
        from core.ai_client import AVAILABLE_MODELS
        self.ai_model_combo.addItems(AVAILABLE_MODELS)
        self.ai_model_combo.currentTextChanged.connect(self._on_ai_model_changed)
        api_layout.addWidget(self.ai_model_combo)

        layout.addWidget(api_group)

        auto_fill_group = QGroupBox("自动填充")
        auto_fill_group.setStyleSheet(self._group_style())
        auto_fill_layout = QVBoxLayout(auto_fill_group)
        auto_fill_layout.setSpacing(4)

        self.auto_fill_check = QCheckBox("A0 条目：切换为轻/中/重度时自动填充模型图描述")
        self.auto_fill_check.setToolTip("开启后，在A0维度点击轻度/中度/重度按钮时，若生成图描述为空则自动填入对应默认文本")
        self.auto_fill_check.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0; font-size: 12px; padding: 2px;
            }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 2px solid #5c7cfa;
                border-radius: 3px;
                background: #12122a;
            }
            QCheckBox::indicator:checked {
                background: #e94560;
                border-color: #e94560;
            }
        """)
        self.auto_fill_check.toggled.connect(self._on_auto_fill_changed)
        auto_fill_layout.addWidget(self.auto_fill_check)

        self.auto_fill_a2_check = QCheckBox("A2 条目：启用色调/打光滑块面板（替换模型图输入框）")
        self.auto_fill_a2_check.setToolTip("开启后，在A2(颜色与材质)维度使用深-浅/艳-柔/亮-暗三个滑块+色彩输入框替代文本输入，自动生成描述")
        self.auto_fill_a2_check.setStyleSheet(self.auto_fill_check.styleSheet())
        self.auto_fill_a2_check.toggled.connect(self._on_auto_fill_a2_changed)
        auto_fill_layout.addWidget(self.auto_fill_a2_check)

        self.auto_fill_a3_check = QCheckBox("A3 条目：切换为轻/中/重度时自动填充模型图描述")
        self.auto_fill_a3_check.setToolTip("开启后，在A3(图案装饰logo商标)维度点击轻度/中度/重度时，若生成图描述为空则自动填入对应默认文本")
        self.auto_fill_a3_check.setStyleSheet(self.auto_fill_check.styleSheet())
        self.auto_fill_a3_check.toggled.connect(self._on_auto_fill_a3_changed)
        auto_fill_layout.addWidget(self.auto_fill_a3_check)

        self.auto_fill_a4_check = QCheckBox("A4 条目：切换为轻/中/重度时自动填充模型图描述")
        self.auto_fill_a4_check.setToolTip("开启后，在A4(文字信息)维度点击轻度/中度/重度时，若生成图描述为空则自动填入对应默认文本")
        self.auto_fill_a4_check.setStyleSheet(self.auto_fill_check.styleSheet())
        self.auto_fill_a4_check.toggled.connect(self._on_auto_fill_a4_changed)
        auto_fill_layout.addWidget(self.auto_fill_a4_check)

        layout.addWidget(auto_fill_group)
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
        model = config.get("api.ai_model", "glm-4.6v")
        idx = self.ai_model_combo.findText(model)
        if idx >= 0:
            self.ai_model_combo.setCurrentIndex(idx)
        self.auto_fill_check.setChecked(bool(config.get("auto_fill_model", False)))
        self.auto_fill_a3_check.setChecked(bool(config.get("auto_fill_a3", False)))
        self.auto_fill_a4_check.setChecked(bool(config.get("auto_fill_a4", False)))
        self.auto_fill_a2_check.setChecked(bool(config.get("auto_fill_a2", False)))

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

    def _on_ai_model_changed(self, model):
        cfg = config.load()
        cfg.setdefault("api", {})
        cfg["api"]["ai_model"] = model
        config.save(cfg)
        from core import ai_client as ac
        ac.set_model(model)
        self.ai_model_changed.emit(model)

    def _on_auto_fill_changed(self, checked):
        cfg = config.load()
        cfg["auto_fill_model"] = bool(checked)
        config.save(cfg)
        self.auto_fill_model_changed.emit(bool(checked))

    def _on_auto_fill_a3_changed(self, checked):
        cfg = config.load()
        cfg["auto_fill_a3"] = bool(checked)
        config.save(cfg)
        self.auto_fill_a3_changed.emit(bool(checked))

    def _on_auto_fill_a4_changed(self, checked):
        cfg = config.load()
        cfg["auto_fill_a4"] = bool(checked)
        config.save(cfg)
        self.auto_fill_a4_changed.emit(bool(checked))

    def _on_auto_fill_a2_changed(self, checked):
        cfg = config.load()
        cfg["auto_fill_a2"] = bool(checked)
        config.save(cfg)
        self.auto_fill_a2_changed.emit(bool(checked))
