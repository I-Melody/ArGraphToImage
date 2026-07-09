from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    page_loaded = pyqtSignal(str)
    page_navigated = pyqtSignal(str)
    recognition_done = pyqtSignal(object)
    recognition_error = pyqtSignal(str)
    content_changed = pyqtSignal(dict)
    api_response = pyqtSignal(dict)
    api_error = pyqtSignal(str)
    layout_restructured = pyqtSignal(dict)
    log_message = pyqtSignal(str, str)
