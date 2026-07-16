from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QStatusBar, QApplication,
    QMessageBox, QDialog, QDialogButtonBox
)

import os
import sys
import json
import logging

from ui.title_bar import TitleBar
from ui.browser_panel import BrowserPanel
from ui.assistant_panel import AssistantPanel
from ui.settings_panel import SettingsPanel
from core.browser_injector import BrowserInjector
from core.layout_adjuster import LayoutAdjuster
from core.layout_recognizer import analyze_detection
from core.ai_client import AiClient
from core import ai_client
from core import event_bus
from config import manager as config
from utils.js_templates import POLL_QUEUES
from ui.image_viewer import ImageViewerDialog

_log = logging.getLogger("main_win")
_WORD_CONFIG_CACHE = None


EDGE_MARGIN = 5


class MainWindow(QMainWindow):

    def __init__(self, profile=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setMinimumSize(800, 500)

        self._resize_edge = None
        self._resize_press = False
        self._auto_apply_after_detect = False

        self._build_ui(profile)
        self._setup_core()
        self._setup_monitoring()
        self._connect_signals()
        self._setup_statusbar()

    def _build_ui(self, profile=None):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(EDGE_MARGIN, EDGE_MARGIN, EDGE_MARGIN, EDGE_MARGIN)
        root_layout.setSpacing(0)

        self._title_bar = TitleBar(self)
        root_layout.addWidget(self._title_bar)

        self._browser_panel = BrowserPanel(self, profile=profile)
        root_layout.addWidget(self._browser_panel, 1)

    def _setup_core(self):
        self._injector = BrowserInjector(self.browser(), self)
        self._adjuster = LayoutAdjuster(self._injector)
        self._assistant_panel = AssistantPanel(self)
        self._settings_panel = SettingsPanel(self)
        self._settings_panel.api_key_changed.connect(self._on_api_key_changed)
        self._settings_panel.sort_scheme_changed.connect(self._on_sort_scheme_changed)
        self._settings_panel.scores_changed.connect(self._on_scores_changed)
        self._settings_panel.slider_changed.connect(self._on_slider_changed)
        self._info_dialog = None
        self._ai_client = AiClient(self)
        self._ai_client.describe_done.connect(self._on_ai_described)

    def _setup_monitoring(self):
        cfg = config.load()
        debounce = cfg.get("recognition", {}).get("debounce_ms", 500)
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(max(500, debounce * 2))
        self._monitor_timer.timeout.connect(self._injector.poll_changes)

        self._redetect_timer = QTimer(self)
        self._redetect_timer.setSingleShot(True)
        self._redetect_timer.setInterval(debounce)
        self._redetect_timer.timeout.connect(self._refresh_recognition)

        self._ai_timer = QTimer(self)
        self._ai_timer.setInterval(400)
        self._ai_timer.timeout.connect(self._poll_ai_requests)
        self._ai_timer_active = False

    def _ai_timer_start(self):
        if not self._ai_timer_active:
            self._ai_timer.start()
            self._ai_timer_active = True

    def _ai_timer_stop(self):
        if self._ai_timer_active:
            self._ai_timer.stop()
            self._ai_timer_active = False

    def _connect_signals(self):
        self._browser_panel.title_changed.connect(self._on_page_title_changed)
        self._browser_panel.url_changed.connect(self._on_url_changed)
        self._browser_panel.load_started.connect(lambda: self._status_bar.showMessage("加载中..."))
        self._browser_panel.load_finished.connect(self._on_load_finished)
        self._browser_panel.parse_clicked.connect(self._on_parse_clicked)
        self._browser_panel.recognize_clicked.connect(self._on_info_clicked)

        self._assistant_panel.recognize_clicked.connect(self._on_recognize_requested)
        self._assistant_panel.transform_clicked.connect(self._on_transform_requested)
        self._assistant_panel.remove_clicked.connect(self._on_remove_requested)

        self._injector.page_detected.connect(self._on_page_detected)
        self._injector.detection_failed.connect(self._on_detection_failed)
        self._injector.layout_applied.connect(self._on_layout_applied)
        self._injector.changes_detected.connect(
            lambda payload: event_bus.content_changed.emit(payload))

        event_bus.recognition_done.connect(self._assistant_panel.show_recognition_result)
        event_bus.recognition_error.connect(
            lambda reason: self._assistant_panel.log(f"[识别失败] {reason}"))
        event_bus.content_changed.connect(self._on_content_changed)
        event_bus.layout_restructured.connect(
            lambda info: self._assistant_panel.log(f"[布局] {info.get('status', '')}"))
        event_bus.page_loaded.connect(
            lambda url: self._assistant_panel.log(f"[页面加载] {url}"))

    def _setup_statusbar(self):
        self._status_bar = QStatusBar()
        self._status_bar.setObjectName("statusBar")
        self._status_bar.showMessage("就绪")
        self.setStatusBar(self._status_bar)

    def _on_page_title_changed(self, title):
        if title:
            window_title = f"{title} — 数据标注辅助工作台"
        else:
            window_title = "数据标注辅助工作台"
        self._title_bar.setWindowTitle(window_title)
        self.setWindowTitle(window_title)

    def _on_url_changed(self, url):
        self._status_bar.showMessage(url)
        event_bus.page_navigated.emit(url)

    def _on_load_finished(self, ok):
        self._status_bar.showMessage("就绪" if ok else "加载失败")
        if not ok:
            _log.warning("Page load failed")
            return
        url = self.browser().url().toString()
        _log.info(f"Page loaded: {url}")
        self._inject_word_config()
        event_bus.page_loaded.emit(url)
        self._injector.start_monitoring()
        self._monitor_timer.start()

    def _poll_ai_requests(self):
        self.browser().page().runJavaScript(POLL_QUEUES, self._on_queues_polled)

    def _on_queues_polled(self, payload):
        if not payload or payload == "null":
            return
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return
        ai_payload = data.get("ai", "[]")
        popup_payload = data.get("popup", "[]")
        self._dispatch_ai_requests(ai_payload)
        self._dispatch_popup_requests(popup_payload)
        if data.get("overlayClosed"):
            self._browser_panel.set_url_bar_visible(True)
            self._ai_timer_stop()

    def _dispatch_ai_requests(self, payload):
        if not payload or payload == "[]":
            return
        try:
            requests = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return
        _log.info(f"Dispatching {len(requests)} AI request(s)")
        for req in requests:
            rid = req.get("id")
            ref = req.get("ref")
            model = req.get("model")
            if rid and ref and model:
                self._ai_client.compare(rid, ref, model)

    def _dispatch_popup_requests(self, payload):
        if not payload or payload == "[]":
            return
        try:
            requests = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return
        page = self.browser().page()
        for req in requests:
            key = req.get("key")
            if key == "__close_all__":
                ImageViewerDialog.close_all()
                continue
            src = req.get("src")
            if key and src and hasattr(page, "open_image_popup"):
                page.open_image_popup(key, src)

    def _on_ai_described(self, request_id, result_json):
        js = f"window.__ar3_ai_render({json.dumps(request_id)}, {json.dumps(result_json)});"
        self.browser().page().runJavaScript(js)

    def _on_recognize_requested(self):
        self._auto_apply_after_detect = False
        self._status_bar.showMessage("正在识别页面...")
        _log.info("Recognition requested (manual)")
        self._injector.detect_page_structure()

    def _on_transform_requested(self):
        _log.info("Transform layout requested")
        self._inject_word_config()
        self._adjuster.apply_tabbed_layout()

    def _on_remove_requested(self):
        _log.info("Remove layout requested")
        self._adjuster.remove_layout()
        self._browser_panel.set_url_bar_visible(True)
        self._ai_timer_stop()

    def _on_content_changed(self, payload):
        changes = payload.get("changes", []) if isinstance(payload, dict) else []
        if changes:
            self._assistant_panel.log(f"[内容变化] {len(changes)} 项")
        self._redetect_timer.start()

    def _refresh_recognition(self):
        self._auto_apply_after_detect = False
        self._injector.detect_page_structure()

    def _on_info_clicked(self):
        if self._info_dialog is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("识别信息")
            dlg.resize(620, 640)
            lay = QHBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            lay.addWidget(self._assistant_panel, 1)
            lay.addWidget(self._settings_panel)
            self._info_dialog = dlg
        self._info_dialog.show()
        self._info_dialog.raise_()
        self._info_dialog.activateWindow()

    def _on_api_key_changed(self, key):
        ai_client.set_key(key)
        self._status_bar.showMessage("API Key 已更新")
        _log.info("API key updated")

    def _on_sort_scheme_changed(self, scheme):
        js = f"window.__ar3_sort_scheme = {json.dumps(scheme)};"
        self.browser().page().runJavaScript(js)
        self._status_bar.showMessage(
            "排序方案：总分优先" if scheme == "score" else "排序方案：不一致数量优先")
        _log.info(f"Sort scheme changed: {scheme}")

    def _on_scores_changed(self, scores):
        self._inject_scores(scores)
        self._status_bar.showMessage("评分设置已更新")
        _log.info(f"Scores updated: {scores}")

    def _inject_scores(self, scores=None):
        if scores is None:
            scores = config.get("scores", {})
        s = {
            "light": scores.get("light", -100),
            "moderate": scores.get("moderate", -301),
            "severe": scores.get("severe", -710),
        }
        self.browser().page().runJavaScript(f"window.__ar3_scores = {json.dumps(s)};")

    def _on_slider_changed(self, slider_cfg):
        self._inject_slider_config(slider_cfg)
        self._status_bar.showMessage("滑块设置已更新")
        _log.info(f"Slider config updated: mode={slider_cfg.get('mode')}")

    def _inject_slider_config(self, slider_cfg=None):
        if slider_cfg is None:
            slider_cfg = {
                "mode": config.get("slider_mode", "multi"),
                "multi": config.get("slider_multi", [0.1, 0.5, 1.0, 2.0, 10.0]),
                "add": config.get("slider_add", [30, 10, 0, -10, -30]),
            }
        self.browser().page().runJavaScript(f"window.__ar3_slider_cfg = {json.dumps(slider_cfg)};")

    def _inject_all_config(self):
        scheme = config.get("sort_scheme", "inconsistency")
        scores = config.get("scores", {})
        s = {"light": scores.get("light", -100), "moderate": scores.get("moderate", -301), "severe": scores.get("severe", -710)}
        slider = {"mode": config.get("slider_mode", "multi"), "multi": config.get("slider_multi", [0.1, 0.5, 1.0, 2.0, 10.0]), "add": config.get("slider_add", [30, 10, 0, -10, -30])}
        js = "window.__ar3_sort_scheme=" + json.dumps(scheme) + ";window.__ar3_scores=" + json.dumps(s) + ";window.__ar3_slider_cfg=" + json.dumps(slider) + ";"
        self.browser().page().runJavaScript(js)

    def _inject_word_config(self):
        global _WORD_CONFIG_CACHE
        if _WORD_CONFIG_CACHE is None:
            if getattr(sys, 'frozen', False):
                root = sys._MEIPASS
            else:
                root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cfg_path = os.path.join(root, "word.config")
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    _WORD_CONFIG_CACHE = json.load(f)
            except Exception:
                _WORD_CONFIG_CACHE = {}
        self.browser().page().runJavaScript(f"window.__ar3_word_config = {json.dumps(_WORD_CONFIG_CACHE)};")
        _log.info("Word config injected")

    def _on_parse_clicked(self):
        self.browser().page().runJavaScript(
            "!!document.getElementById('__ar3_tab_overlay')",
            self._on_parse_state_checked)

    def _on_parse_state_checked(self, overlay_open):
        if overlay_open:
            _log.info("Parse toggle: removing overlay")
            self._adjuster.remove_layout()
            self._browser_panel.set_url_bar_visible(True)
            self._status_bar.showMessage("已返回原页面")
            return
        _log.info("Parse toggle: detecting + applying layout")
        self._auto_apply_after_detect = True
        self._status_bar.showMessage("正在解析页面...")
        try:
            self._injector.detect_page_structure()
        except Exception as e:
            _log.exception("Parse detection failed")
            self._status_bar.showMessage(f"解析出错: {e}")
            QMessageBox.warning(self, "解析错误", str(e))

    def _on_detection_failed(self, reason):
        _log.error(f"Detection failed: {reason}")
        self._status_bar.showMessage(f"解析失败: {reason}")
        event_bus.recognition_error.emit(reason)
        if self._auto_apply_after_detect:
            QMessageBox.warning(self, "解析失败", f"无法解析页面:\n{reason}\n\n请确认已打开标注工作页面。")

    def _on_page_detected(self, data):
        try:
            result = analyze_detection(data)
        except Exception as e:
            _log.exception("Page analysis failed")
            self._status_bar.showMessage(f"分析失败: {e}")
            event_bus.recognition_error.emit(str(e))
            return

        _log.info(f"Analysis result: {result.model_count} models, {result.dimension_count} dims, matched={result.matched}")
        event_bus.recognition_done.emit(result)
        self._status_bar.showMessage(f"解析完成: {result.model_count}个模型, {result.dimension_count}个维度")

        if self._auto_apply_after_detect and result.matched and result.model_count > 0:
            _log.info("Auto-applying layout after detection")
            try:
                self._adjuster.apply_tabbed_layout()
            except Exception as e:
                _log.exception("Layout apply failed")
                self._status_bar.showMessage(f"布局失败: {e}")
                QMessageBox.warning(self, "布局错误", str(e))
        self._auto_apply_after_detect = False

    def _on_layout_applied(self, result):
        if not result or not isinstance(result, dict):
            _log.warning("Layout applied but result is not a dict")
            self._status_bar.showMessage("布局应用失败: JS执行错误")
            QMessageBox.warning(self, "布局失败", "无法在页面中应用作业窗口布局。\n页面可能尚未完全加载。")
            return
        event_bus.layout_restructured.emit(result)
        status = result.get("status", "unknown")
        _log.info(f"Layout applied: status={status}, count={result.get('count', 0)}")
        if status == "transformed":
            self._browser_panel.set_url_bar_visible(False)
            self._inject_all_config()
            self._ai_timer_start()
            self._status_bar.showMessage(f"作业窗口已打开: {result.get('count', 0)} 个标签页")
        elif status == "already_transformed":
            self._status_bar.showMessage("作业窗口已存在")
        elif status == "no_grid_found":
            _log.warning("No grid items found on page")
            self._status_bar.showMessage("未找到标注页面元素")
            QMessageBox.warning(self, "解析失败", "未在页面中找到标注工作区元素。\n请确认已进入标注工作页面。")
        else:
            _log.warning(f"Unknown layout status: {status}")
            self._status_bar.showMessage("应用布局失败")
            QMessageBox.warning(self, "错误", f"应用布局失败: {result.get('status', 'unknown')}")

    @staticmethod
    def _format_detection_result(result):
        lines = []
        lines.append(f"页面类型: {result.page_type}")
        lines.append(f"匹配标注页: {'是' if result.matched else '否'}")
        lines.append("")
        lines.append(f"参考图: {'已抓取' if result.reference_image else '未找到'}")
        lines.append(f"模型图: {result.model_count}/8")
        lines.append(f"评价维度: {result.dimension_count} 种")
        lines.append(f"排序项: {len(result.rank_items)}/8")
        lines.append(f"锚点导航: {len(result.anchor_items)}/9")
        return "\n".join(lines)

    def navigate(self, url):
        self._browser_panel.navigate(url)

    def browser(self):
        return self._browser_panel.browser()

    def browser_panel(self):
        return self._browser_panel

    def set_status(self, message):
        self._status_bar.showMessage(message)

    def _edge_at(self, pos):
        rect = self.rect()
        left = pos.x() <= EDGE_MARGIN
        right = pos.x() >= rect.width() - EDGE_MARGIN
        top = pos.y() <= EDGE_MARGIN
        bottom = pos.y() >= rect.height() - EDGE_MARGIN

        if left and top:
            return Qt.Edge.LeftEdge | Qt.Edge.TopEdge
        if right and top:
            return Qt.Edge.RightEdge | Qt.Edge.TopEdge
        if left and bottom:
            return Qt.Edge.LeftEdge | Qt.Edge.BottomEdge
        if right and bottom:
            return Qt.Edge.RightEdge | Qt.Edge.BottomEdge
        if left:
            return Qt.Edge.LeftEdge
        if right:
            return Qt.Edge.RightEdge
        if top:
            return Qt.Edge.TopEdge
        if bottom:
            return Qt.Edge.BottomEdge
        return None

    def _cursor_for_edge(self, edge):
        if edge in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
                     Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in (Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
                     Qt.Edge.RightEdge | Qt.Edge.TopEdge):
            return Qt.CursorShape.SizeBDiagCursor
        if edge in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        if edge in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def mouseMoveEvent(self, event):
        if self.isMaximized():
            self.setCursor(Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(event)
            return

        edge = self._edge_at(event.pos())
        if edge:
            self.setCursor(self._cursor_for_edge(edge))
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._resize_edge = None

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.isMaximized():
            edge = self._edge_at(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_press = True
                self.windowHandle().startSystemResize(edge)
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._resize_edge = None
        self._resize_press = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            self._title_bar.update_maximize_button(self.isMaximized())
        super().changeEvent(event)
