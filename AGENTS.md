# AGENTS.md — Data Annotation Assistant Workbench (Ar3)

PyQt6 desktop app that embeds a Chromium `QWebEngineView`, loads the Tencent 企鹅标注平台
annotation page, and injects JS to restructure it into a per-model tabbed overlay UI.

## Run / Setup
- **Linux: use `./run.sh`, NOT `python main.py`.** WebEngine needs extra shared libs; `run.sh`
  extracts `.deb`s into `.venv/shared-libs` and sets `LD_LIBRARY_PATH`. Plain `python main.py`
  crashes on a fresh Linux box.
- `pip install -r requirements.txt` (PyQt6 + PyQt6-WebEngine only). `bs4`+`lxml` are installed in
  `.venv` for parsing the HTML fixtures during verification (not a runtime dep).
- Optional first arg overrides target URL: `python main.py <url>`.
- No unit tests / linter / typecheck config. `.opencode/opencode.json` loads the
  `opencode-auto-qcgates` plugin (QC gates run automatically).
- `A.html`, `page.html`, `.webdata/`, `rank_snapshot.json` are git-ignored (`*.log` is NOT).
- `api.log` (root) holds the Zhipu API key in plaintext — required for the AI feature; keep it.

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
`ForcePersistentCookies` + storage/cache under `./.webdata/`, then threads it
`MainWindow(profile=...) → BrowserPanel(profile=...)` where it is applied via
`QWebEnginePage(profile, view)` + `setPage()`. Do **not** revert to
`QWebEngineProfile.defaultProfile()` — that profile is off-the-record and drops all cookies
(logins won't persist).

## Architecture — how it's wired
- Entry `main.py` → `ui/main_window.py` (control hub).
- `core/event_bus.py` `EventBus` is the central signal bus (global instance in `core/__init__.py`).
  Signals: `snake_case` past-tense (`page_loaded`, `recognition_done`, ...); payloads are
  dicts/dataclasses (`recognition_done` carries a `RecognitionResult`), never QWidgets.
- `ui/browser_panel.py` owns the `QWebEngineView` + toolbar.
- `core/browser_injector.py` runs JS templates, parses JSON results, emits signals.
- `core/layout_recognizer.py` = pure logic (detection dict → dataclasses).
- `core/layout_adjuster.py` `LayoutAdjuster` tracks overlay apply/remove state.
- `ui/assistant_panel.py` `AssistantPanel` is **not** in the main layout; it lives inside a popup
  `QDialog` opened by the toolbar 「信息」button.
- Layer rule: `ui/` = widgets; `core/` = pure logic, no `PyQt6.QtWidgets` imports.
- Python↔JS is one-shot `runJavaScript(script, callback)` returning JSON strings. **No QWebChannel.**
- Live monitoring IS active: a `QTimer` polls `poll_changes()` after load; changes debounce-trigger
  a re-detect (`config.recognition.debounce_ms`).

## Toolbar buttons (behavior, not just labels)
- 「信息」(`recognize_clicked` → `_on_info_clicked`): opens the `AssistantPanel` recognition-info
  dialog. (This replaced the old page-dump button; `_on_save_page` is gone.)
- 「解析」(`parse_clicked` → `_on_parse_clicked`): **toggles** the overlay. It first checks the DOM
  for `#__ar3_tab_overlay`; if present it removes the overlay (back to original page), else it
  detects + applies the tabbed layout.

## The overlay (utils/js_templates.py — `APPLY_TABBED_LAYOUT`, ~680 lines)
**All page-restructure logic is JS strings here**, not Python. Key facts:
- Builds a full-screen overlay `#__ar3_tab_overlay` (z-index 9999). Original DOM stays in place;
  a `syncObserver` (MutationObserver on body) mirrors original↔overlay so Vue reactivity survives.
- 8 tabs (模型A~H). Each panel is a **3-column flex row, ratio 1:1:1**: 参考图 img | model img |
  evaluation column. Images click → lightbox.
- Each of the 5 dimensions renders **5 buttons** (一致/轻度/中度/重度/不适用) mapped onto the page's
  **iView checkbox group** (`.checkboxItem`, values 一致/不一致/不适用) + a severity string.
- **In-app scoring is stored as integer ×100** (display divides by 100, `.toFixed(2)`). Auto values:
  一致/不适用 = 0, 轻度 = -100, 中度 = -301, 重度 = -710. Per-dimension card has a 5-tick fine-tune
  **slider** (+0.20/+0.10/0/-0.10/-0.20 → `_ar3_adj_steps` = [20,10,0,-10,-20]); final
  `dim.__ar3_score` = auto + adjustment. Selecting a severity resets the slider to the middle.
  Per-model total in shared `modelScores[letter]`, shown top-right (`__ar3_score_badge`).
- **排序 button** (right of bottom rank bar): ranks models by score desc using **dense ranking**
  (ties share a rank: 1,1,2,3...). It drives the original page's Vue model — the `z-drag-sort_card`
  component's `$data.list` (an array of 8 arrays, one per RANK bucket), reassigned so the change
  **survives 确认** (a pure DOM move gets reverted by Vue). `_ar3_find_sort_card()` walks up from a
  `.rank-content` `__vue__`; `_ar3_apply_rank_dom()` is a fallback when no Vue instance is reachable.
  Ties go into the **same** `.rank-content` bucket (trailing buckets empty).
- **Remark inputs are decoupled from typing**: two textareas (参考图/生成图) + one shared **确定**
  button per dimension. Typing only sets `dim.__ar3_dirty`; the original `.customInput` is written
  **only on 确定** click. The `syncObserver` skips a dimension while it is dirty or focused
  (previously per-keystroke writes caused an observer feedback loop that interrupted input).
- **推送 button** (left of a dimension's inputs, replaced the old 填充AI): pushes THIS dimension's
  参考图 textarea (`taA`) text into the same dimension's **empty** 参考图 box in every other tab.
- Selecting **不适用** on one model propagates 不适用 to the same dimension of all other models
  (`_ar3_set_active(idx, noPropagate)`; sync/propagated calls pass `noPropagate=true`).

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

## AI compare feature (Zhipu GLM-4.6V)
- `core/ai_client.py` `AiClient` reads the key from `api.log`, POSTs to
  `https://open.bigmodel.cn/api/paas/v4/chat/completions` (model `glm-4.6v`) on a background
  thread, emits `describe_done(request_id, json_str)`.
- **Two images per call**: each tab's 「AI对比」button uploads 参考图 + that model图 together and
  asks for per-dimension **differences**. Result JSON is nested:
  `{ "整体身份": {"参考图":..,"生成图":..,"差异":..}, ... }` (5 dim keys).
- **JS↔Python bridge = polling** (no QWebChannel): JS pushes `{id,ref,model}` onto
  `window.__ar3_ai_queue`; a `QTimer` (`_ai_timer`) drains it via `DRAIN_AI_QUEUE`, calls
  `ai_client.compare(...)`, and injects the result back with `window.__ar3_ai_render(id, json)`.
- Results cache in `window.__ar3_last_ai['__ar3_ai_cmp_<letter>']`; auto-fill on tab switch
  (`fillFromAi`) reads `参考图`→taA, `生成图`→taB into empty visible fields. Cache is keyed to a
  **task signature = reference-image src** and cleared at APPLY when it changes. **Do NOT re-add
  cache invalidation inside the `syncObserver`** — it fired spuriously and wiped results mid-use.

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
  its `.text-content` (the inner `content_*` id is random — locate via the container). Shown in the
  overlay under the reference image.
- Anchor nav `.t-anchor__item-link` ×9. Toolbar `.z-level__item`.
- Dims order: 整体身份 / 整体形状与局部结构 / 颜色与材质 / 图案装饰品牌Logo商标 / 文字信息.

## Logging & conventions
- `debug.log` at root is truncated on every startup. Format `[HH:MM:SS.mmm] [LEVEL] source: msg`.
  Note: most modules use stdlib `logging` with no handler, so their logs do NOT reach `debug.log`.
- No code comments unless explicitly requested (existing files follow this).
- User config in `config.json` at root, managed by `config/manager.py` (`config/defaults.py` = schema).
