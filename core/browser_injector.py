import json
import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEnginePage

from utils.js_templates import (
    DETECT_PAGE_STRUCTURE,
    MONITOR_PAGE_CHANGES,
    GET_PAGE_CHANGES,
    APPLY_TABBED_LAYOUT,
    REMOVE_TABBED_LAYOUT,
    EVALUATION_STATE_TO_PYTHON,
)

logger = logging.getLogger(__name__)


class BrowserInjector(QObject):
    page_detected = pyqtSignal(dict)
    changes_detected = pyqtSignal(dict)
    layout_applied = pyqtSignal(dict)
    evaluation_snapshot = pyqtSignal(list)
    detection_failed = pyqtSignal(str)

    def __init__(self, web_view, parent=None):
        super().__init__(parent)
        self._web_view = web_view
        self._page = web_view.page()
        self._last_detection = None
        self._monitor_active = False

    def detect_page_structure(self):
        self._page.runJavaScript(DETECT_PAGE_STRUCTURE, self._on_page_detected)

    def _on_page_detected(self, result_str):
        if not result_str:
            logger.warning("Detection returned empty result")
            self.detection_failed.emit("JS执行无返回数据")
            return
        try:
            data = json.loads(result_str)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Detection JSON parse failed: {e}")
            self.detection_failed.emit(f"JSON解析失败: {e}")
            return
        models = len(data.get("model_images", []))
        evals = len(data.get("evaluation_groups", []))
        logger.info(f"Page detected: {models} models, {evals} eval groups, page_type={data.get('page_type')}")
        self._last_detection = data
        self.page_detected.emit(data)

    def start_monitoring(self):
        self._monitor_active = True
        self._page.runJavaScript(MONITOR_PAGE_CHANGES, self._on_monitor_started)

    def _on_monitor_started(self, result):
        logger.info(f"Page monitor: {result}")

    def poll_changes(self):
        self._page.runJavaScript(GET_PAGE_CHANGES, self._on_changes_polled)

    def _on_changes_polled(self, changes_str):
        if not changes_str or changes_str == "[]":
            return
        try:
            changes = json.loads(changes_str)
        except (json.JSONDecodeError, TypeError):
            return
        if changes:
            self.changes_detected.emit({"changes": changes})

    def apply_tabbed_layout(self):
        self._page.runJavaScript(APPLY_TABBED_LAYOUT, self._on_layout_applied)

    def _on_layout_applied(self, result_str):
        if not result_str:
            logger.warning("Layout apply returned empty result")
            return
        try:
            result = json.loads(result_str)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Layout result JSON parse failed: {e}")
            return
        logger.info(f"Layout apply result: {result.get('status')} (models={result.get('count', 0)})")
        self.layout_applied.emit(result)

    def remove_tabbed_layout(self):
        self._page.runJavaScript(REMOVE_TABBED_LAYOUT)

    def get_evaluation_state(self):
        self._page.runJavaScript(EVALUATION_STATE_TO_PYTHON, self._on_evaluation_state)

    def _on_evaluation_state(self, result_str):
        if not result_str:
            return
        try:
            data = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            return
        self.evaluation_snapshot.emit(data)
