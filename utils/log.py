import logging
import os
from datetime import datetime

_INITIALIZED = False
_MAX_BYTES = 2 * 1024 * 1024


def _trim_if_needed(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= _MAX_BYTES:
        return
    try:
        with open(path, "rb") as f:
            f.seek(size - int(_MAX_BYTES * 0.75))
            f.readline()
            tail = f.read()
        with open(path, "wb") as f:
            f.write(b"[... older log truncated ...]\n")
            f.write(tail)
    except Exception:
        pass


def setup(log_dir=None):
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    if log_dir is None:
        log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_path = os.path.join(log_dir, "debug.log")

    _trim_if_needed(log_path)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [INFO ] app     : === Session started ===\n")

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
