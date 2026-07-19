# AGENTS.md — Data Annotation Assistant Workbench (Ar3)

PyQt6 desktop app that embeds a Chromium `QWebEngineView`, loads the Tencent 企鹅标注平台
annotation page, and injects JS to restructure it into a per-model tabbed overlay UI.

## Run / Setup / Build
- **Linux: use `./run.sh`, NOT `python main.py`.** WebEngine needs extra shared libs; `run.sh`
  extracts `.deb`s into `.venv/shared-libs` and sets `LD_LIBRARY_PATH`. Plain `python main.py`
  crashes on a fresh Linux box.
- `pip install -r requirements.txt` (PyQt6 + PyQt6-WebEngine only). `bs4`+`lxml` are installed in
  `.venv` for parsing the HTML fixtures during verification (not a runtime dep).
- Optional first arg overrides target URL: `python main.py <url>`.
- Windows release: `pyinstaller GraphToImage.spec` — bundles `word.config` + `config.json` as
  datas. Frozen code resolves both via `sys._MEIPASS` (`config/manager.py:_app_root`,
  `main_window._inject_word_config`); keep that branch when touching path logic.
- No unit tests / linter / typecheck config. `.opencode/opencode.json` loads the
  `opencode-auto-qcgates` plugin (QC gates run automatically).
- Git-ignored: `A.html`, `page.html`, `.webdata/`, `rank_snapshot.json`, `*.log` (incl.
  `debug.log`), `.opencode/`, `build/`, `dist/`.
- **Zhipu API key lives in `config.json` → `api.api_key`** (edited via the 「信息」dialog's AI
  panel; the old `api.log` mechanism is gone). `config.json` IS git-tracked and bundled into the
  EXE — it intentionally carries the real key; don't blank it "for security" without asking.

## Verification without a live site (no test suite exists)
- **JS syntax**: extract a template string and run `node --check` on a temp file (piping to
  `/dev/stdin` fails on this box — write a real temp file).
- **End-to-end**: boot the app offscreen against the `file://` fixtures. Working incantation:
  ```
  export QT_QPA_PLATFORM=offscreen
  export LD_LIBRARY_PATH=".venv/shared-libs/usr/lib/x86_64-linux-gnu:<PyQt6 Qt6/lib>:$LD_LIBRARY_PATH"
  # set AA_ShareOpenGLContexts, create QApplication, import MainWindow, navigate to file://A.html
  ```
  Then drive `w._on_transform_requested()` / `runJavaScript(...)` and read back DOM state. The
  `QVulkanInstance: Failed to initialize Vulkan` warning is harmless.
- Fixtures: `A.html` = fully answered, `page.html` = partially answered (different Vue states).

## Critical: WebEngine init order (main.py)
Exact order or the app crashes silently:
1. Set `AA_ShareOpenGLContexts` (and on win32 `AA_UseSoftwareOpenGL`) **before** constructing `QApplication`.
2. Construct `QApplication` **before** importing `QWebEngineCore` / `QWebEngineWidgets`.
3. Build the profile and pass it down **before** any `QWebEngineView` is created.

## Cookie / login persistence
`main.py` builds a **named, non-off-the-record** `QWebEngineProfile("Ar3Profile")` with
`ForcePersistentCookies` + storage/cache under a **per-user** directory (`QStandardPaths.
AppLocalDataLocation`), threaded `MainWindow(profile=...) → BrowserPanel(profile=...)` and applied
via `QWebEnginePage(profile, view)` + `setPage()`.  Do **not** revert to
`QWebEngineProfile.defaultProfile()` — it is off-the-record and drops all cookies.  Do **not**
place cookie storage beside the EXE — that leaks logins across users on shared machines.

## Architecture — how it's wired
- Entry `main.py` → `ui/main_window.py` (control hub).
- `core/event_bus.py` `EventBus` is the central signal bus (global instance in `core/__init__.py`).
  Signals: `snake_case` past-tense; payloads are dicts/dataclasses, never QWidgets.
- `ui/browser_panel.py` owns the `QWebEngineView` + URL toolbar.
- `core/browser_injector.py` runs JS templates, parses JSON results, emits signals.
- `core/layout_recognizer.py` = pure logic (detection dict → dataclasses).
- Layer rule: `ui/` = widgets; `core/` = pure logic, no `PyQt6.QtWidgets` imports.
- **Python↔JS bridge = polling, no QWebChannel.** One `QTimer` (`_ai_timer`, 400 ms, started at
  overlay APPLY, stopped at overlay close) runs `POLL_QUEUES`, which in one shot drains
  `window.__ar3_ai_queue` (AI requests), `window.__ar3_popup_queue` (image popups), and an
  `overlayClosed` flag (JS sets `__ar3_overlay_just_closed` when the in-page 返回原页面 button
  removed the overlay → Python restores the URL bar and stops the timer).
- Image clicks do NOT open an in-page lightbox: JS queues `{key,src}`; Python opens frameless
  always-on-top `ImageViewerDialog`s (`ui/image_viewer.py`: wheel = zoom only, left/right drag =
  pan (context menu suppressed), rotate/mirror, disk-cached). `ImagePopupPage.createWindow`
  returns `self` so `target=_blank` stays in-window. 「关弹窗」button queues key `__close_all__`.
- Live monitoring: `MONITOR_PAGE_CHANGES` observer after load (delegates to the overlay's
  `syncObserver` when active); changes debounce-trigger a re-detect (`recognition.debounce_ms`).
- Legacy templates `DRAIN_AI_QUEUE`, `DRAIN_POPUP_QUEUE`, `SYNC_OVERLAY_IMAGES`,
  `SCAN_PAGE_FOR_TEXT`, `CAPTURE_RANK_STRUCTURE` are defined in js_templates.py but no longer
  imported by Python (superseded by `POLL_QUEUES`; keep for debugging).
- At overlay APPLY, `_inject_all_config()` pushes every setting as `window.__ar3_*` globals
  (sort scheme, scores, slider cfg, ai model, auto-fill flags); panels re-inject on change.
  `word.config` is injected as `window.__ar3_word_config` on every page load.

## Toolbar buttons (behavior, not just labels)
- 「信息」(`recognize_clicked` → `_on_info_clicked`): opens a QDialog holding THREE panels:
  `AssistantPanel` (recognition tree, EN labels) + `SettingsPanel` (排序方案/评分/滑块) +
  `AiSettingsPanel` (API key / model / auto-fill toggles). None of them live in the main layout.
- 「解析」(`parse_clicked`): **toggles** the overlay — checks DOM for `#__ar3_tab_overlay`;
  removes it if present, else detect + auto-apply.

## The overlay (utils/js_templates.py — `APPLY_TABBED_LAYOUT`, ~1700 lines)
**All page-restructure logic is JS strings here**, not Python. Key facts:
- Full-screen overlay `#__ar3_tab_overlay` (z-index 9999). Original DOM stays in place; a
  `syncObserver` (MutationObserver on body) mirrors original↔overlay so Vue reactivity survives.
- 8 tabs (模型A~H), each a 3-column flex row 1:1:1: 参考图(+题目描述) | model img + AI section |
  evaluation column.
- Each of the 5 dimensions renders **5 buttons** (一致/轻度/中度/重度/不适用) mapped onto the page's
  iView checkbox group (values 一致/不一致/不适用) + a severity string in the remark.
- **Scoring is integer ×100** (display `/100` `.toFixed(2)`). Severity scores are runtime-config:
  `window.__ar3_scores` {light,moderate,severe}, defaults -100/-301/-710, read at click time.
  Per-dim slider (5 ticks) obeys `window.__ar3_slider_cfg`: mode `multi` = ×[0.1,0.5,1,2,10] on
  the auto score (`Math.trunc`), **shared across ALL tabs per dimension index** (broadcast via
  `_ar3_set_dim_scale`, persisted in `window.__ar3_saved_dim_scale_idx` across re-applies); mode
  `add` = ±offset, current model only. Selecting a severity KEEPS the shared multiplier.
- **Write-back is batched, not per-keystroke and not per-dim**: typing only sets `__ar3_dirty` and
  adds the model to `window.__ar3_dirty_models`. `window.__ar3_submit_all()` writes originals; it
  runs on 提交全部 button, Ctrl+Enter, tab switch, 排序, 返回原页面, and REMOVE_TABBED_LAYOUT.
  (There is no per-dimension 确定 button anymore.)
- Remark text written to `.customInput`: `参考图：...\n生成图：...\n<severity>`. Severity words come
  from `word.config` (`severity` map 轻度/中度/重度 → synonym lists): the FIRST synonym is written,
  ALL synonyms are recognized when parsing existing remarks back into the overlay.
- **排序 button**: submits dirty dims first, then ranks by `window.__ar3_sort_scheme` —
  `'inconsistency'` (default: fewer 不一致 dims first, tie → higher score) or `'score'`. **Dense
  ranking** (1,1,2,3...). It drives the original page's Vue model — `z-drag-sort_card` `$data.list`
  (array of 8 bucket-arrays) reassigned so the change **survives 确认**; `_ar3_apply_rank_dom()` is
  the fallback when no Vue instance is reachable. Ties share one `.rank-content` bucket.
- 推送 pushes THIS dim's 参考图 text into the same dim's **empty** 参考图 in every other tab;
  强制 does the same but overwrites non-empty too.
- Selecting 不适用 propagates 不适用 to the same dimension of all other models
  (`setActive(4, true)`; sync/propagated calls pass `noPropagate=true`).
- Auto-fill flags (from AiSettingsPanel → `window.__ar3_auto_fill_*`): A0/A3/A4 fill a default
  生成图 text on 轻/中/重 click when empty; A2 replaces the 生成图 textarea with a 深浅/艳柔/亮暗
  triple-slider + color/extra inputs panel that composes the text (`_ar3_a2_compose`).
  The A2 panel has 4 vertical range sliders: 深/浅, 艳/柔, 亮/暗, 冷/暖 + a 色彩 text input
  + 额外说明 field.
- **Keyboard** (capture-phase listener, inactive while typing/IME): `A~H`/`←→` switch tab,
  `↑↓` move focused dim card, `1~5` set severity of focused dim, `Ctrl+Enter` submit all. Other
  Ctrl/Alt combos deliberately fall through (copy/paste must keep working).
- Tab buttons show per-dim state chars `[ 0, 1, ×, - ... ]` (0=一致, 1/2/3=severity, ×=不适用,
  -=unset) + done count; incomplete tabs are amber. A dim is "done" once a severity is picked and,
  if 不一致, both textareas are non-empty. Bottom rank slots mirror the chars and click-activate
  their tab.
- **IME guards are load-bearing**: composition events set `dim.__ar3_composing` +
  `window.__ar3_ime_until`; the syncObserver skips dirty/focused/composing dims and skips the whole
  remark sync while any IME is active; `_ar3_compose_reason` retries until IME idle. Programmatic
  `textarea.value` writes during composition leak pinyin — don't add DOM writes in composition
  handlers or per-keystroke sync.

## Tiled mode (平铺模式, `APPLY_TILED_LAYOUT` / `REMOVE_TILED_LAYOUT`)
- Second parse mode selected in 「信息」→SettingsPanel「解析方式」(config `parse_mode`:
  `tabbed`|`tiled`). 解析 button dispatches via `LayoutAdjuster.apply_layout(mode)`; the toggle
  check and `remove_layout()` handle BOTH overlay ids (`#__ar3_tab_overlay` / `#__ar3_tile_overlay`,
  mutually exclusive — each APPLY guards against the other being open).
- Deliberately minimal: `#__ar3_tile_grid` = 3-col CSS grid of 参考图 + 模型A~H. Images do NOT
  open popups on click — each cell has top-right buttons: semi-transparent ⇄/↶/↷ (mirror,
  rotate ±15°) + 「窗口查看」(queues `__ar3_popup_queue`, same keys `ref_image`/`model_X`).
  Per-cell wheel = zoom ×1.15 (1~10, `preventDefault`), right-button drag = pan (only when
  zoomed; pan listeners live on the overlay so they die with it; contextmenu suppressed
  overlay-wide), and a translucent ↻ reset button appears bottom-right once any transform is
  active (state in `cell.__ar3_zoom`, transform = `translate rotate scale [scaleX(-1)]`).
  Model cells reorder via HTML5 drag-and-drop (dragover does live `insertBefore`, grid reflow =
  补位); the ref cell has no dragover handler so it stays fixed at slot 0. Bottom
  `#__ar3_tile_rank_bar` mirrors the original page's `.rank-title` colors / `.rank-list-item`
  order — display only, NO sorting logic yet.
- Same status contract as tabbed (`{status, mode, count}` → shared `_on_layout_applied`); tiled
  skips `_inject_all_config()` but still starts the poll timer (popups + `overlayClosed`).

### Driving Vue-backed controls (non-obvious, load-bearing)
- **Read selected option** from the wrapper class `ivu-checkbox-wrapper-checked` via
  `_ar3_selected_option()`, NOT `input.checked` (unset in this DOM).
- **Set a checkbox**: simulate a real `.click()` on the `.checkboxItem` (`_ar3_apply_option`, one
  toggle per pass, re-query after ~60ms). Setting `input.checked` does not update Vue state.
- **Write the remark** (`.customInput` is a `contenteditable` div): `focus()` + set `innerText` +
  dispatch `InputEvent('input')` — `textContent` alone won't trigger Vue.
- Original remark element is found by text-marker search up the ancestor chain (`prefix+不一致`
  then `prefix+备注`, e.g. `A-A0不一致`); it exists only after 不一致/不适用 is selected, so
  timeouts/retries guard the race.

## AI describe feature (Zhipu, core/ai_client.py)
- `AiClient.describe(request_id, ref_src, desc)` — **single image** (参考图) + optional 题目描述
  text, POST `https://open.bigmodel.cn/api/paas/v4/chat/completions`, model from
  `AVAILABLE_MODELS` (`glm-4.6v` | `glm-4.6v-flash`), ThreadPoolExecutor(2), emits
  `describe_done(request_id, json_str)`. (The old two-image 「AI对比」 flow is gone.)
- Result JSON: 5 dim keys `{"整体身份":{"描述":..}, "整体形状与局部结构":.., "颜色与材质":..,
  "图案装饰logo商标":.., "文字信息":..}`.
- 「AI描述」button (one per tab, shared result): canvas-downscales the ref img to ≤2048px JPEG 0.75,
  queues `{id:'__ar3_ai_desc', ref, desc}`. Result cached in
  `window.__ar3_last_ai['__ar3_ai_desc']` and rendered into every `.__ar3_ai_desc_out` — it does
  NOT change with tab switching.
- 「推送AI」button distributes each dimension's 描述 into that dim's **empty** 参考图 textarea
  across ALL models (marks them dirty; submit still required).
- Cache is keyed to a **task signature = reference-image src** and cleared at APPLY when it
  changes. **Do NOT re-add cache invalidation inside the `syncObserver`** — it fired spuriously
  and wiped results mid-use.

## Target page facts (verified against A.html / page.html)
- 9 `.grid-item[id*=content_engine]`: `content_engine0_ref_image`, `content_engine0_model_A`~`_H`.
  Visible image = `img.img`; a hidden sibling div holds all 9 (`img[alt=ref_image|model_A..H]`).
- Eval = 8 models × 5 dims = 40 `.multiple-select`. **Detect only `.multiple-select` that has
  `.checkboxItem` children** — a broader `[class*=form-item]` selector double-counts the remark
  form-items (gives 80 instead of 40).
- Label in `.ivu-form-item-label` (e.g. `A-A0.整体身份`). A dim and its remark share a
  `.t-col.t-col-6` wrapper; find the remark by walking up to that common ancestor.
- Remark `.customInput.horizontalLtr` is in the DOM only when 不一致/不适用 is selected (A.html 40,
  page.html 3). Validation errors add class `errorStyle`.
- Rank: two `.rank` groups — `.rank[0]` = 8 `.rank-title` (RANK 1~8, unique `background-color`);
  `.rank[1]` = 8 **fixed `.rank-content` buckets** (index = rank). A tie = multiple
  `.rank-list-item` in one bucket; trailing buckets go empty. Backed by Vue (see 排序 above).
- `preserve_description` (题目描述): container `#engine0_default_item_preserve_description`; text in
  its `.text-content` (the inner `content_*` id is random — locate via the container). Shown under
  the overlay's reference image AND passed as `desc` to the AI prompt.
- Anchor nav `.t-anchor__item-link` ×9. Toolbar `.z-level__item`.
- Dims order: 整体身份 / 整体形状与局部结构 / 颜色与材质 / 图案装饰品牌Logo商标 / 文字信息.

## Logging & conventions
- `debug.log` at root is truncated on every startup. `utils/log.py` installs a root-logger
  handler, so ALL stdlib `logging` output lands in `debug.log` (format
  `[HH:MM:SS.mmm] [LEVEL] source: msg`) — useful first stop when debugging.
- No code comments unless explicitly requested (existing files follow this).
- User config in `config.json` at root, managed by `config/manager.py` (`config/defaults.py` =
  schema; `load()` merges defaults, `get()` supports dotted keys, mtime-based cache).
