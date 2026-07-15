import json
import os
import sys
from config.defaults import DEFAULT_CONFIG

_CACHE = None
_CACHE_MTIME = 0


def _app_root():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_path():
    return os.path.join(_app_root(), "config.json")


def load():
    path = _config_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return dict(DEFAULT_CONFIG)


def _load_cached():
    global _CACHE, _CACHE_MTIME
    path = _config_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    if _CACHE is None or mtime != _CACHE_MTIME:
        _CACHE = load()
        _CACHE_MTIME = mtime
    return _CACHE


def save(config):
    global _CACHE, _CACHE_MTIME
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    _CACHE = dict(config)
    _CACHE_MTIME = os.path.getmtime(path)


def get(key, default=None):
    cfg = _load_cached()
    keys = key.split(".")
    for k in keys:
        if isinstance(cfg, dict):
            cfg = cfg.get(k)
        else:
            return default
    return cfg if cfg is not None else default
