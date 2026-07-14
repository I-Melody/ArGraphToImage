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
    QSpinBox,
    QDoubleSpinBox,
)

from config import manager as config


class SettingsPanel(QWidget):
    api_key_changed = pyqtSignal(str)
    sort_scheme_changed = pyqtSignal(str)
    scores_changed = pyqtSignal(dict)
    slider_changed = pyqtSignal(dict)

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
            rb.setStyleSheet("""
                QRadioButton {
                    color: #e0e0e0; font-size: 12px; padding: 2px;
                }
                QRadioButton::indicator {
                    width: 14px; height: 14px;
                    border: 2px solid #5c7cfa;
                    border-radius: 8px;
                    background: #12122a;
                }
                QRadioButton::indicator:checked {
                    background: #e94560;
                    border-color: #e94560;
                }
                QRadioButton::indicator:hover {
                    border-color: #a0b0ff;
                }
            """)
        self.sort_group_btns.addButton(self.radio_score, 0)
        self.sort_group_btns.addButton(self.radio_incons, 1)
        sort_layout.addWidget(self.radio_score)
        sort_layout.addWidget(self.radio_incons)
        self.sort_group_btns.buttonClicked.connect(self._on_sort_changed)

        layout.addWidget(sort_group)

        # ---- Score settings ----
        score_group = QGroupBox("评分设置")
        score_group.setStyleSheet(self._group_style())
        score_layout = QVBoxLayout(score_group)
        score_layout.setSpacing(6)
        score_hint = QLabel("不一致扣分（×100 整数）")
        score_hint.setStyleSheet("color: #707080; font-size: 10px;")
        score_layout.addWidget(score_hint)

        self.score_spins = {}
        sevs = [("轻度", "light"), ("中度", "moderate"), ("重度", "severe")]
        for name, key in sevs:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #e0e0e0; font-size: 12px;")
            lbl.setFixedWidth(36)
            spin = QSpinBox()
            spin.setRange(-9999, 0)
            spin.setSingleStep(1)
            spin.setStyleSheet("""
                QSpinBox {
                    background: #12122a; color: #e0e0e0;
                    border: 1px solid #2a2a4a; border-radius: 4px;
                    padding: 4px 6px; font-size: 12px;
                }
                QSpinBox:focus { border-color: #5c7cfa; }
                QSpinBox::up-button, QSpinBox::down-button { width: 0px; }
            """)
            row.addWidget(lbl)
            row.addWidget(spin)
            row.addStretch()
            score_layout.addLayout(row)
            self.score_spins[key] = spin

        self.btn_save_scores = QPushButton("保存分数")
        self.btn_save_scores.setStyleSheet(self._btn_style(primary=True))
        self.btn_save_scores.clicked.connect(self._on_save_scores)
        score_layout.addWidget(self.btn_save_scores)

        self.score_status = QLabel("")
        self.score_status.setStyleSheet("color: #0e9a4a; font-size: 11px;")
        score_layout.addWidget(self.score_status)

        layout.addWidget(score_group)

        # ---- Slider settings ----
        slider_group = QGroupBox("滑块设置")
        slider_group.setStyleSheet(self._group_style())
        slider_layout = QVBoxLayout(slider_group)
        slider_layout.setSpacing(6)

        self.slider_mode_group = QButtonGroup(self)
        self.radio_multi = QRadioButton("乘算（×倍数，同步所有模型）")
        self.radio_add = QRadioButton("加算（±偏移，仅当前模型）")
        for rb in (self.radio_multi, self.radio_add):
            rb.setStyleSheet("QRadioButton{color:#e0e0e0;font-size:12px;padding:2px;}"
                             "QRadioButton::indicator{width:14px;height:14px;border:2px solid #5c7cfa;border-radius:8px;background:#12122a;}"
                             "QRadioButton::indicator:checked{background:#e94560;border-color:#e94560;}")
        self.slider_mode_group.addButton(self.radio_multi, 0)
        self.slider_mode_group.addButton(self.radio_add, 1)
        slider_layout.addWidget(self.radio_multi)
        slider_layout.addWidget(self.radio_add)

        self.slider_spins_multi = []
        self.slider_spins_add = []

        row_m = QHBoxLayout()
        row_m.setSpacing(3)
        QLabel("乘算值:").styleSheet = lambda s: "color:#a0a0b0;font-size:11px;"
        lbl_m = QLabel("乘算值:")
        lbl_m.setStyleSheet("color:#a0a0b0;font-size:11px;")
        lbl_m.setFixedWidth(52)
        row_m.addWidget(lbl_m)
        for i in range(5):
            sp = QDoubleSpinBox()
            sp.setRange(0.01, 100.0)
            sp.setSingleStep(0.01)
            sp.setDecimals(2)
            sp.setStyleSheet("QDoubleSpinBox{background:#12122a;color:#e0e0e0;border:1px solid #2a2a4a;border-radius:4px;padding:3px 4px;font-size:11px;} QDoubleSpinBox:focus{border-color:#5c7cfa;} QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{width:0px;}")
            sp.setFixedWidth(62)
            row_m.addWidget(sp)
            self.slider_spins_multi.append(sp)
        slider_layout.addLayout(row_m)

        row_a = QHBoxLayout()
        row_a.setSpacing(3)
        lbl_a = QLabel("加算值:")
        lbl_a.setStyleSheet("color:#a0a0b0;font-size:11px;")
        lbl_a.setFixedWidth(52)
        row_a.addWidget(lbl_a)
        for i in range(5):
            sp = QSpinBox()
            sp.setRange(-9999, 9999)
            sp.setStyleSheet("QSpinBox{background:#12122a;color:#e0e0e0;border:1px solid #2a2a4a;border-radius:4px;padding:3px 4px;font-size:11px;} QSpinBox:focus{border-color:#5c7cfa;} QSpinBox::up-button,QSpinBox::down-button{width:0px;}")
            sp.setFixedWidth(62)
            row_a.addWidget(sp)
            self.slider_spins_add.append(sp)
        slider_layout.addLayout(row_a)

        self.btn_save_slider = QPushButton("保存滑块")
        self.btn_save_slider.setStyleSheet(self._btn_style(primary=True))
        self.btn_save_slider.clicked.connect(self._on_save_slider)
        slider_layout.addWidget(self.btn_save_slider)

        self.slider_status = QLabel("")
        self.slider_status.setStyleSheet("color: #0e9a4a; font-size: 11px;")
        slider_layout.addWidget(self.slider_status)

        layout.addWidget(slider_group)
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
        scheme = config.get("sort_scheme", "inconsistency")
        if scheme == "inconsistency":
            self.radio_incons.setChecked(True)
        else:
            self.radio_score.setChecked(True)
        scores = config.get("scores", {})
        self.score_spins["light"].setValue(int(scores.get("light", -100)))
        self.score_spins["moderate"].setValue(int(scores.get("moderate", -301)))
        self.score_spins["severe"].setValue(int(scores.get("severe", -710)))
        # Slider
        mode = config.get("slider_mode", "multi")
        if mode == "add":
            self.radio_add.setChecked(True)
        else:
            self.radio_multi.setChecked(True)
        multi_vals = config.get("slider_multi", [0.1, 0.5, 1.0, 2.0, 10.0])
        add_vals = config.get("slider_add", [30, 10, 0, -10, -30])
        for i in range(5):
            self.slider_spins_multi[i].setValue(float(multi_vals[i]) if i < len(multi_vals) else 1.0)
            self.slider_spins_add[i].setValue(int(add_vals[i]) if i < len(add_vals) else 0)

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

    def _on_save_scores(self):
        scores = {
            "light": self.score_spins["light"].value(),
            "moderate": self.score_spins["moderate"].value(),
            "severe": self.score_spins["severe"].value(),
        }
        cfg = config.load()
        cfg["scores"] = scores
        config.save(cfg)
        self.score_status.setText("已保存")
        self.scores_changed.emit(scores)

    def _on_save_slider(self):
        mode = "add" if self.radio_add.isChecked() else "multi"
        multi_vals = [s.value() for s in self.slider_spins_multi]
        add_vals = [s.value() for s in self.slider_spins_add]
        cfg = config.load()
        cfg["slider_mode"] = mode
        cfg["slider_multi"] = multi_vals
        cfg["slider_add"] = add_vals
        config.save(cfg)
        self.slider_status.setText("已保存")
        self.slider_changed.emit({"mode": mode, "multi": multi_vals, "add": add_vals})
