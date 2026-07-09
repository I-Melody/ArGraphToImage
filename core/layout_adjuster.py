from core.layout_recognizer import RecognitionResult


class LayoutAdjuster:
    def __init__(self, browser_injector):
        self._injector = browser_injector
        self._is_transformed = False

    @property
    def is_transformed(self):
        return self._is_transformed

    def apply_tabbed_layout(self):
        self._injector.apply_tabbed_layout()
        self._is_transformed = True

    def remove_layout(self):
        self._injector.remove_tabbed_layout()
        self._is_transformed = False

    def toggle(self):
        if self._is_transformed:
            self.remove_layout()
        else:
            self.apply_tabbed_layout()
