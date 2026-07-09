# AGENTS.md — Data Annotation Assistant Workbench (Ar3)

PyQt6 desktop app that embeds a Chromium `QWebEngineView`, loads the Tencent 企鹅标注平台
annotation page, and injects JS to restructure it into a per-model tabbed UI.

## Run / Setup
- **Linux: use `./run.sh`, NOT `python main.py`.** WebEngine needs extra shared libs; `run.sh`
  downloads/extracts `.deb`s into `.venv/shared-libs` and sets `LD_LIBRARY_PATH`. Plain
  `python main.py` crashes on a fresh Linux box.
- `pip install -r requirements.txt` (PyQt6 + PyQt6-WebEngine only).
- Optional first arg overrides target URL: `python main.py <url>`.
- No tests, linter, or typecheck config exist. `.opencode/opencode.json` loads the
  `opencode-auto-qcgates` plugin (QC gates run automatically).

## Critical: WebEngine init order (main.py)
Must happen in this exact order or the app crashes silently:
1. Set `AA_ShareOpenGLContexts` (and on win32 `AA_UseSoftwareOpenGL`) **before** constructing `QApplication`.
2. Construct `QApplication` **before** importing `QWebEngineCore` / `QWebEngineWidgets`.
3. Configure `QWebEngineProfile.defaultProfile()` before any `QWebEngineView` is created.

## Architecture — how it's actually wired
- Entry: `main.py` → `ui/main_window.py` (the real control hub; wires signals directly).
- `ui/browser_panel.py` owns the `QWebEngineView` + toolbar buttons.
- `core/browser_injector.py` runs JS templates and parses JSON string results.
- `core/layout_recognizer.py` turns the detection dict into dataclasses (pure logic).
- **All page-restructure logic lives in JS strings in `utils/js_templates.py`**, not in Python.
  Python only injects and reads back JSON. `APPLY_TABBED_LAYOUT` (~550 lines) is the core.

### Wiring gotchas (do not trust names/docs alone)
- **Toolbar buttons are mislabeled vs behavior**: the 「识别」button calls `_on_save_page`
  (dumps current DOM to `page.html`); the 「解析」button is what actually detects + restructures
  (`_on_parse_clicked`). Confirm intent before "fixing" either.
- **Defined but NOT wired anywhere**: `core/event_bus.py` (`EventBus`), `core/layout_adjuster.py`
  (`LayoutAdjuster`), `ui/assistant_panel.py` (`AssistantPanel`), `ui/widgets/` (empty). The
  EventBus contract below is the *intended* design, not the current reality.
- **No live monitoring loop**: `MONITOR_PAGE_CHANGES` / `GET_PAGE_CHANGES` / `poll_changes()` exist
  but no timer calls them. `SYNC_OVERLAY_IMAGES`, `EVALUATION_STATE_TO_PYTHON`, `SCAN_PAGE_FOR_TEXT`
  are also unused by the UI. There is **no QWebChannel bridge**; Python↔JS is one-shot
  `runJavaScript(script, callback)` returning JSON strings.

### Intended conventions (aspirational, partially unadopted)
- `ui/` = widgets only; `core/` = pure logic, no `PyQt6.QtWidgets` imports.
- EventBus signals: `snake_case` + past tense (`page_loaded`). Payloads = dicts/dataclasses, never QWidgets.
- Frameless window: `Qt.FramelessWindowHint` + custom `title_bar.py`. Edge-resize uses
  `startSystemResize` + `mouseMoveEvent` in `main_window.py` (no nativeEvent/WM_NCHITTEST).
- Theme: single QSS string in `app/theme.py`. base `#1a1a2e`, surface `#16213e`, accent `#e94560`
  (sparing), text `#e0e0e0`.

## How the restructure actually works (APPLY_TABBED_LAYOUT)
- Builds a full-screen **overlay** `#__ar3_tab_overlay` (z-index 9999) over the page. Original
  DOM is **left in place and NOT hidden** — the overlay reads from it and writes back via a
  `MutationObserver`, so Vue reactivity stays intact.
- 8 tabs (模型A~H). Each: left = 参考图 img + model img (click → lightbox); right = 5 dimension cards.
- **Non-obvious control mapping**: each dimension renders **5 buttons**
  (一致 / 轻度 / 中度 / 重度 / 不适用) that map onto the page's **3 checkboxes**
  (一致 / 不一致 / 不适用) plus a severity string. The remark textarea content is composed as
  `参考图：…\n生成图：…\n{轻度|中度|重度}不一致` and written into the original `.customInput`.
- Original remark inputs are located by **text-marker search** up the ancestor chain
  (`prefix+不一致` then `prefix+备注`, e.g. `A-A0不一致`), because the `.customInput` element is
  created by Vue **only after** 不一致/不适用 is selected. Timeouts/retries guard this race.

## Target page facts (verified against A.html / page.html)
Both HTML files are minified Vue snapshots in different dynamic states (A.html fully answered;
page.html partially). Use them as fixtures.
- 9 `.grid-item[id*=content_engine]`: `content_engine0_ref_image`, `content_engine0_model_A`~`_H`.
  Visible image = `img.img` inside; a hidden sibling div holds all 9 (`img[alt=ref_image|model_A..H]`).
- Eval = 8 models × 5 dims = 40 `.multiple-select`. Label in `.ivu-form-item-label`
  (e.g. `A-A0.整体身份`). Selected option = `.checkboxItem` whose class contains
  `ivu-checkbox-wrapper-checked`.
- Each dim + its remark box share a `.t-col.t-col-6` wrapper. Remark `.customInput.horizontalLtr`
  is **only in the DOM when 不一致/不适用 is selected** (A.html has 40, page.html has 3). Validation
  errors add class `errorStyle`.
- Rank: `.rank-list-item` ×8 (模型A~H, draggable); `.rank-title` ×8 (RANK 1~8, each unique
  `background-color`). Anchor nav: `.t-anchor__item-link` ×9. Toolbar: `.z-level__item`.
- Dims order: 整体身份 / 整体形状与局部结构 / 颜色与材质 / 图案装饰品牌Logo商标 / 文字信息.
- A MutationObserver on `.grid-item` must watch `.customInput` add/remove (Vue renders them
  lazily), not just visibility.

## Logging
- `debug.log` at project root is **truncated on every startup** (main.py).
- Format: `[HH:MM:SS.mmm] [LEVEL] source: message`; levels DEBUG/INFO/WARN/ERROR.
- Note: current code only logs a couple of lines via `main.py`; most modules use stdlib `logging`
  without a handler, so their logs do not reach `debug.log`.

## Conventions
- No comments in code unless explicitly requested (existing files follow this).
- User config in `config.json` at root, managed by `config/manager.py` (`config/defaults.py` = schema).
