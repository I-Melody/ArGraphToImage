DEFAULT_CONFIG = {
    "target_url": "https://tlabel.tencent.com",
    "window": {
        "width": 1400,
        "height": 900,
        "x": 100,
        "y": 100
    },
    "api": {
        "base_url": "",
        "api_key": "",
        "timeout": 30,
        "ai_model": "glm-4.6v"
    },
    "recognition": {
        "auto_restructure": True,
        "debounce_ms": 500
    },
    "parse_mode": "tabbed",
    "sort_scheme": "inconsistency",
    "auto_fill_model": False,
    "auto_fill_a3": False,
    "auto_fill_a4": False,
    "auto_fill_a2": False,
    "auto_save_interval_sec": 45,
    "slider_mode": "multi",
    "slider_multi": [0.1, 0.5, 1.0, 2.0, 10.0],
    "slider_add": [30, 10, 0, -10, -30],
    "scores": {
        "light": -100,
        "moderate": -301,
        "severe": -710
    }
}
