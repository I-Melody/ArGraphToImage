import sys
import os
from datetime import datetime

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
os.environ["QTWEBENGINEINSPECTOR"] = "0"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# CRITICAL: Set attributes BEFORE QApplication construction
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
if sys.platform == "win32":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

# Create QApplication MUST happen before importing QWebEngine* modules
QApplication.setApplicationName("数据标注辅助工作台")
QApplication.setOrganizationName("AnnotationAssistant")
app = QApplication(sys.argv)

# Now safe to import WebEngine (QApplication already exists)
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView

from app.theme import THEME_QSS
from ui.main_window import MainWindow
from config import manager as config


_log_truncated = False


def setup_logging():
    global _log_truncated
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [INFO ] app: === Session started ===\n")
    _log_truncated = True
    return log_path


def log_message(log_path, level, source, message):
    global _log_truncated
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] [{level:<5}] {source}: {message}\n"
    mode = "w" if not _log_truncated else "a"
    with open(log_path, mode, encoding="utf-8") as f:
        f.write(line)
    _log_truncated = True


def make_persistent_profile():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".webdata")
    os.makedirs(data_dir, exist_ok=True)

    profile = QWebEngineProfile("Ar3Profile", app)
    profile.setPersistentStoragePath(os.path.join(data_dir, "storage"))
    profile.setCachePath(os.path.join(data_dir, "cache"))
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
    profile.setHttpUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return profile


def main():
    log_path = setup_logging()

    profile = make_persistent_profile()

    app.setStyleSheet(THEME_QSS)

    window = MainWindow(profile=profile)
    window.resize(1400, 900)
    window.move(100, 100)

    cfg = config.load()
    target_url = cfg.get("window", {}).get("target_url",
                   cfg.get("target_url", "https://tlabel.tencent.com"))

    if len(sys.argv) > 1:
        target_url = sys.argv[1]

    window.navigate(target_url)
    window.show()

    log_message(log_path, "INFO", "app", f"Window shown, navigating to {target_url}")

    try:
        sys.exit(app.exec())
    except Exception as e:
        log_message(log_path, "ERROR", "app", str(e))
        raise


if __name__ == "__main__":
    main()
