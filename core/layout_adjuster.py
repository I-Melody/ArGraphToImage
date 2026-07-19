import logging

from core.layout_recognizer import RecognitionResult

_log = logging.getLogger("layout_adj")


class LayoutAdjuster:
    MODE_TABBED = "tabbed"
    MODE_TILED = "tiled"

    def __init__(self, browser_injector):
        self._injector = browser_injector
        self._is_transformed = False

    @property
    def is_transformed(self):
        return self._is_transformed

    def apply_layout(self, mode=MODE_TABBED):
        if mode == self.MODE_TILED:
            self.apply_tiled_layout()
        else:
            self.apply_tabbed_layout()

    def apply_tabbed_layout(self):
        _log.info("Applying tabbed layout")
        self._injector.apply_tabbed_layout()
        self._is_transformed = True

    def apply_tiled_layout(self):
        _log.info("Applying tiled layout")
        self._injector.apply_tiled_layout()
        self._is_transformed = True

    def remove_layout(self):
        _log.info("Removing layout")
        self._injector.remove_tabbed_layout()
        self._injector.remove_tiled_layout()
        self._is_transformed = False

    def toggle(self):
        if self._is_transformed:
            self.remove_layout()
        else:
            self.apply_tabbed_layout()
