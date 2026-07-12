from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


class _DragBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


class ImagePopupWindow(QWidget):
    def __init__(self, profile):
        super().__init__()
        self.setWindowTitle("图片查看")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(900, 700)

        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.page.setBackgroundColor(Qt.GlobalColor.transparent)
        self.view.setPage(self.page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        # Native drag strip: dragging it moves the window via startSystemMove (no
        # Chromium work-area clamp, unlike window.moveTo). Leaves room for close btn.
        self._dragbar = _DragBar(self)
        self._dragbar.setStyleSheet("background: transparent;")
        self._dragbar.setCursor(Qt.CursorShape.SizeAllCursor)
        self._dragbar.setToolTip("拖拽移动窗口")

        self._close_btn = QPushButton("\u2715", self)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("关闭")
        self._close_btn.setStyleSheet(
            "QPushButton{background:rgba(20,20,40,0.55);color:#fff;border:none;"
            "border-radius:16px;font-size:16px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(233,69,96,0.9);}")
        self._close_btn.clicked.connect(self.close)

        # JS window.close() (e.g. ESC) -> close the window.
        self.page.windowCloseRequested.connect(self.close)
        # JS window.resizeTo (auto-fit) -> resize this window to the image ratio.
        self.page.geometryChangeRequested.connect(self._on_geometry_requested)

    def _on_geometry_requested(self, rect):
        self.resize(rect.size())

    def resizeEvent(self, event):
        w = self.width()
        self._dragbar.setGeometry(0, 0, max(0, w - 48), 44)
        self._close_btn.setGeometry(w - 40, 6, 32, 32)
        self._dragbar.raise_()
        self._close_btn.raise_()
        super().resizeEvent(event)


class ImagePopupPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._popups = []

    def createWindow(self, _window_type):
        win = ImagePopupWindow(self.profile())
        win.destroyed.connect(lambda: self._popups.remove(win) if win in self._popups else None)
        self._popups.append(win)
        win.show()
        return win.page


class BrowserPanel(QWidget):
    url_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    load_started = pyqtSignal()
    load_finished = pyqtSignal(bool)
    parse_clicked = pyqtSignal()
    recognize_clicked = pyqtSignal()  # i.e. "信息" button

    def __init__(self, parent=None, profile=None):
        super().__init__(parent)
        self.setObjectName("browserPanel")
        self._web_profile = profile or QWebEngineProfile.defaultProfile()
        self._loading = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._browser = QWebEngineView()
        self._browser.setObjectName("browser")
        self._page = ImagePopupPage(self._web_profile, self._browser)
        self._browser.setPage(self._page)
        self._browser.urlChanged.connect(self._on_url_changed)
        self._browser.titleChanged.connect(self._on_title_changed)
        self._browser.loadStarted.connect(self._on_load_started)
        self._browser.loadFinished.connect(self._on_load_finished)

        self._url_bar = self._create_url_bar()
        layout.addWidget(self._url_bar)
        layout.addWidget(self._browser, 1)

    def _create_url_bar(self):
        bar = QWidget()
        bar.setObjectName("urlBar")
        bar.setFixedHeight(38)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        self._btn_back = QPushButton("\u25c0")
        self._btn_back.setToolTip("后退")
        self._btn_back.clicked.connect(self._browser.back)

        self._btn_forward = QPushButton("\u25b6")
        self._btn_forward.setToolTip("前进")
        self._btn_forward.clicked.connect(self._browser.forward)

        self._btn_reload = QPushButton("\u21bb")
        self._btn_reload.setToolTip("刷新")
        self._btn_reload.clicked.connect(self._toggle_reload_stop)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("输入URL ...")
        self._url_input.returnPressed.connect(self._on_url_entered)

        self._btn_clipboard = QPushButton("\u2398")
        self._btn_clipboard.setToolTip("读取剪切板URL并跳转")
        self._btn_clipboard.clicked.connect(self._on_clipboard_go)

        self._btn_go = QPushButton("\u2192")
        self._btn_go.setToolTip("转到")
        self._btn_go.clicked.connect(self._on_url_entered)

        self._btn_save = QPushButton("\u4fe1\u606f")
        self._btn_save.setToolTip("显示识别信息面板")
        self._btn_save.clicked.connect(self.recognize_clicked.emit)

        self._btn_parse = QPushButton("\u89e3\u6790")
        self._btn_parse.setObjectName("btnParse")
        self._btn_parse.setToolTip("解析页面结构 / 返回原页面（切换）")
        self._btn_parse.setStyleSheet("""
            QPushButton#btnParse {
                background-color: #0f3460;
                color: #e0e0e0;
                border: 1px solid #5c7cfa;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#btnParse:hover {
                background-color: #5c7cfa;
                color: #ffffff;
            }
            QPushButton#btnParse:pressed {
                background-color: #4a6de0;
            }
        """)
        self._btn_parse.clicked.connect(self.parse_clicked.emit)

        layout.addWidget(self._btn_back)
        layout.addWidget(self._btn_forward)
        layout.addWidget(self._btn_reload)
        layout.addWidget(self._url_input, 1)
        layout.addWidget(self._btn_clipboard)
        layout.addWidget(self._btn_go)
        layout.addWidget(self._btn_save)
        layout.addWidget(self._btn_parse)
        return bar

    def _toggle_reload_stop(self):
        if self._loading:
            self._browser.stop()
        else:
            self._browser.reload()

    def _on_url_entered(self):
        text = self._url_input.text().strip()
        if not text:
            return
        self._navigate_to_text(text)

    def _on_clipboard_go(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if not text:
            return
        self._url_input.setText(text)
        self._navigate_to_text(text)

    def _navigate_to_text(self, text):
        if "." not in text and "://" not in text:
            text = "https://www.google.com/search?q=" + text
        elif "://" not in text:
            text = "https://" + text
        url = QUrl(text)
        if url.isValid():
            self._browser.setUrl(url)

    def _on_url_changed(self, url):
        url_str = url.toString()
        self._url_input.setText(url_str)
        self.url_changed.emit(url_str)

    def _on_title_changed(self, title):
        self.title_changed.emit(title)

    def _on_load_started(self):
        self._loading = True
        self._btn_reload.setText("\u2715")
        self._btn_reload.setToolTip("停止加载")
        self.load_started.emit()

    def _on_load_finished(self, ok):
        self._loading = False
        self._btn_reload.setText("\u21bb")
        self._btn_reload.setToolTip("刷新")
        if ok:
            self._url_input.setText(self._browser.url().toString())
        self.load_finished.emit(ok)

    def navigate(self, url):
        self._browser.setUrl(QUrl(url))

    def browser(self):
        return self._browser

    def page(self):
        return self._browser.page()

    def profile(self):
        return self._web_profile
