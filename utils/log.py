import logging
import os
from datetime import datetime

_INITIALIZED = False


def setup(log_dir=None):
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    if log_dir is None:
        log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_path = os.path.join(log_dir, "debug.log")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [INFO ] app     : === Session started ===\n")

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    handler = _LogHandler(log_path)
    handler.setLevel(logging.INFO)
    root.addHandler(handler)


class _LogHandler(logging.Handler):
    def __init__(self, path):
        super().__init__()
        self._f = open(path, "a", encoding="utf-8")

    def emit(self, record):
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        level = record.levelname[:5]
        source = record.name.split(".")[-1][:8]
        msg = record.getMessage()
        line = f"[{ts}] [{level:<5}] {source:<8}: {msg}\n"
        self._f.write(line)
        self._f.flush()

    def close(self):
        if self._f:
            self._f.close()
        super().close()
