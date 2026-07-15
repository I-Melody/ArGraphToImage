from PyQt6.QtCore import Qt, QSize, QUrl, QEvent, QPoint, QStandardPaths
from PyQt6.QtGui import QPixmap, QCursor, QPainter, QColor, QPolygon, QTransform
from PyQt6.QtWidgets import (
    QDialog, QLabel, QPushButton,
    QScrollArea, QWidget,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QNetworkDiskCache


class _DragBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


class _ResizeGrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("拖拽调整窗口大小")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemResize(Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 80))
        w, h = self.width(), self.height()
        tri = QPolygon()
        tri.append(QPoint(w, h - 16))
        tri.append(QPoint(w - 16, h))
        tri.append(QPoint(w, h))
        p.drawPolygon(tri)


class ImageViewerDialog(QDialog):
    _open = {}
    _nam = None

    @classmethod
    def _get_nam(cls):
        if cls._nam is None:
            cls._nam = QNetworkAccessManager()
            cache = QNetworkDiskCache()
            import os
            cache_dir = os.path.join(
                QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation),
                "ImageViewer")
            os.makedirs(cache_dir, exist_ok=True)
            cache.setCacheDirectory(cache_dir)
            cls._nam.setCache(cache)
        return cls._nam

    @classmethod
    def show_image(cls, key, src, parent=None):
        existing = cls._open.get(key)
        if existing and existing.isVisible():
            existing.activateWindow()
            existing.raise_()
            return
        dlg = cls(key, src, parent)
        cls._open[key] = dlg
        dlg.finished.connect(lambda: cls._open.pop(key, None))
        dlg.show()

    def __init__(self, key, src, parent=None):
        super().__init__(parent)
        self._key = key
        self._src = src
        self._scale = 1.0
        self._min_scale = 0.1
        self._pixmap = None
        self._rotation = 0
        self._mirrored = False
        self._nam = QNetworkAccessManager(self)

        self.setWindowTitle("图片查看")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("ImageViewerDialog{background:#2a2a2e;}")
        self.resize(400, 300)

        self._scroll = QScrollArea(self)
        self._scroll.setStyleSheet("QScrollArea{background: #2a2a2e; border: none;}")
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel()
        self._label.setStyleSheet("QLabel{background: transparent;}")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidget(self._label)

        # Overlaid widgets — parented to self, raised above the scroll area.
        self._dragbar = _DragBar(self)
        self._dragbar.setStyleSheet("background: rgba(60,60,70,0.5);")
        self._dragbar.setCursor(Qt.CursorShape.SizeAllCursor)
        self._dragbar.setToolTip("拖拽移动窗口")

        self._close_btn = QPushButton("\u2715", self)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("关闭")
        self._close_btn.setStyleSheet(
            "QPushButton{background:rgba(40,40,70,0.5);color:#fff;border:none;"
            "border-radius:16px;font-size:16px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(233,69,96,0.75);}")
        self._close_btn.clicked.connect(self.close)

        _btn_style = (
            "QPushButton{background:rgba(40,40,70,0.5);color:#c0c0c0;border:none;"
            "border-radius:16px;font-size:14px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(100,100,180,0.6);color:#fff;}")

        self._btn_mirror = QPushButton("\u21c4", self)
        self._btn_mirror.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mirror.setToolTip("水平翻转")
        self._btn_mirror.setStyleSheet(_btn_style)
        self._btn_mirror.clicked.connect(self._on_mirror)

        self._btn_rot_left = QPushButton("\u21b6", self)
        self._btn_rot_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rot_left.setToolTip("向左旋转 15°")
        self._btn_rot_left.setStyleSheet(_btn_style)
        self._btn_rot_left.clicked.connect(lambda: self._on_rotate(-15))

        self._btn_rot_right = QPushButton("\u21b7", self)
        self._btn_rot_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rot_right.setToolTip("向右旋转 15°")
        self._btn_rot_right.setStyleSheet(_btn_style)
        self._btn_rot_right.clicked.connect(lambda: self._on_rotate(15))

        self._resize_grip = _ResizeGrip(self)

        self._wheel_zoom_delta = 0

        # Event filter on the viewport: wheel → zoom ONLY (no scrolling); drag → pan.
        vp = self._scroll.viewport()
        vp.installEventFilter(self)
        self._panning = False
        self._pan_origin = QPoint()

        self._fetch_image()

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()
        self._scroll.setGeometry(0, 0, w, h)
        self._dragbar.setGeometry(0, 0, max(0, w - 48), 44)
        self._close_btn.setGeometry(w - 40, 6, 32, 32)
        self._btn_mirror.setGeometry(w - 80, 6, 32, 32)
        self._btn_rot_left.setGeometry(w - 120, 6, 32, 32)
        self._btn_rot_right.setGeometry(w - 160, 6, 32, 32)
        self._resize_grip.setGeometry(w - 20, h - 20, 20, 20)
        self._dragbar.raise_()
        self._close_btn.raise_()
        self._btn_mirror.raise_()
        self._btn_rot_left.raise_()
        self._btn_rot_right.raise_()
        self._resize_grip.raise_()

        if self._pixmap:
            vw = self._scroll.viewport().width()
            vh = self._scroll.viewport().height()
            iw, ih = self._pixmap.width(), self._pixmap.height()
            if vw > 0 and vh > 0 and iw > 0 and ih > 0:
                new_min = min(vw / iw, vh / ih)
                was_fit = abs(self._scale - self._min_scale) < 0.0001
                self._min_scale = new_min
                if was_fit and self._scale > new_min:
                    self._scale = new_min
                    self._apply_scale()

        super().resizeEvent(event)

    def eventFilter(self, obj, event):
        if obj is not self._scroll.viewport():
            return super().eventFilter(obj, event)
        t = event.type()
        # Scroll wheel → zoom only (no scrollbar movement).
        if t == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            self._wheel_zoom_delta += delta
            if abs(self._wheel_zoom_delta) >= 120:
                factor = 1.15 if self._wheel_zoom_delta > 0 else (1.0 / 1.15)
                self._wheel_zoom_delta = 0
                old_scale = self._scale
                self._scale *= factor
                self._scale = max(getattr(self, '_min_scale', 0.1), min(self._scale, 20.0))
                self._apply_scale()
            return True
        # Pointer drag on the image → pan (move scrollbars).
        if t == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._panning = True
                self._pan_origin = event.globalPosition().toPoint()
                self._pan_scroll_start = QPoint(
                    self._scroll.horizontalScrollBar().value(),
                    self._scroll.verticalScrollBar().value())
                self._scroll.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                return True
        if t == QEvent.Type.MouseMove and self._panning:
            delta = event.globalPosition().toPoint() - self._pan_origin
            self._scroll.horizontalScrollBar().setValue(
                max(0, self._pan_scroll_start.x() - delta.x()))
            self._scroll.verticalScrollBar().setValue(
                max(0, self._pan_scroll_start.y() - delta.y()))
            return True
        if t == QEvent.Type.MouseButtonRelease and self._panning:
            self._panning = False
            self._scroll.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return True
        return super().eventFilter(obj, event)

    def _apply_scale(self):
        if self._pixmap is None:
            return
        w = int(self._pixmap.width() * self._scale)
        h = int(self._pixmap.height() * self._scale)
        scaled = self._pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        if self._mirrored or self._rotation != 0:
            t = QTransform()
            if self._mirrored:
                t.scale(-1, 1)
            if self._rotation != 0:
                t.rotate(self._rotation)
            scaled = scaled.transformed(t, Qt.TransformationMode.SmoothTransformation)
        self._label.setPixmap(scaled)
        self._label.resize(scaled.size())

    def _on_mirror(self):
        self._mirrored = not self._mirrored
        self._apply_scale()

    def _on_rotate(self, delta):
        self._rotation = (self._rotation + delta) % 360
        self._apply_scale()

    def _on_image_loaded(self, data):
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        self._pixmap = pix
        self._auto_fit()

    def _auto_fit(self):
        if self._pixmap is None:
            return
        iw, ih = self._pixmap.width(), self._pixmap.height()
        if iw <= 0 or ih <= 0:
            return
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        max_w = int(avail.width() * 0.9)
        max_h = int(avail.height() * 0.9)
        r = min(max_w / iw, max_h / ih, 1.0 if iw <= max_w and ih <= max_h else 999.0)
        w, h = int(iw * r), int(ih * r)
        w = max(w, 100)
        h = max(h, 100)
        self.resize(w, h)
        x = max(avail.x(), avail.x() + (avail.width() - w) // 2)
        y = max(avail.y(), avail.y() + (avail.height() - h) // 2)
        self.move(x, y)

        # Set initial scale to EXACTLY fill the window (image fits edge-to-edge).
        # Also clamp minimum zoom to this fill-window scale.
        win_w, win_h = self._scroll.viewport().width(), self._scroll.viewport().height()
        if win_w > 0 and win_h > 0 and iw > 0 and ih > 0:
            fit_scale = min(win_w / iw, win_h / ih)
            self._min_scale = fit_scale
            self._scale = fit_scale
        else:
            self._scale = 1.0
            self._min_scale = 0.1
        self._apply_scale()

    def _fetch_image(self):
        url = QUrl(self._src)
        req = QNetworkRequest(url)
        req.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                         QNetworkRequest.CacheLoadControl.PreferCache)
        self._nam = ImageViewerDialog._get_nam()
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_reply(r))

    def _on_reply(self, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            self._on_image_loaded(data)
        reply.deleteLater()
