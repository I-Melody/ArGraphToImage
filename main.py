import sys
import os
import logging

os.environ["QTWEBENGINEINSPECTOR"] = "0"

from utils import log

log.setup()

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
if sys.platform == "win32":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

QApplication.setApplicationName("数据标注辅助工作台")
QApplication.setOrganizationName("AnnotationAssistant")
app = QApplication(sys.argv)

from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView

from app.theme import THEME_QSS
from ui.main_window import MainWindow
from config import manager as config

_log = logging.getLogger("app")


def make_persistent_profile():
    from PyQt6.QtCore import QStandardPaths
    app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    data_dir = os.path.join(app_data, "AnnotationAssistant")
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
    _log.info(f"Persistent profile created at {data_dir}")
    return profile


def main():
    profile = make_persistent_profile()

    app.setStyleSheet(THEME_QSS)
    _log.info("QSS stylesheet applied")

    window = MainWindow(profile=profile)
    window.resize(1400, 900)
    window.move(100, 100)

    cfg = config.load()
    target_url = cfg.get("window", {}).get("target_url",
                   cfg.get("target_url", "https://tlabel.tencent.com"))

    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        _log.info(f"URL override from CLI: {target_url}")

    window.navigate(target_url)
    window.show()
    _log.info(f"Window shown, navigating to {target_url}")

    try:
        sys.exit(app.exec())
    except Exception as e:
        _log.exception(f"App crashed: {e}")
        raise


if __name__ == "__main__":
    main()
