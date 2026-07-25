import json

from PyQt6.QtCore import QUrl, QSize, Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

TILED_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body{width:100%;height:100%;overflow:hidden;font-family:"Microsoft YaHei",sans-serif;background:#1a1a2e;}
#__ar3_tile_grid{width:100%;height:100%;display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:1fr;gap:8px;padding:8px;overflow-y:auto;min-height:0;}
.tile_cell{position:relative;display:flex;align-items:center;justify-content:center;background:#16213e;border-radius:8px;overflow:hidden;min-height:120px;border:3px solid #2a2a4a;}
.tile_cell_active_incomplete{border-color:#e0a030;}
.tile_cell_active_complete{border-color:#e0e0e0;}
.tile_cell_label{position:absolute;top:6px;left:10px;z-index:1;color:#a0a0b0;font-size:12px;font-weight:bold;background:rgba(26,26,46,0.7);padding:2px 8px;border-radius:4px;cursor:pointer;user-select:none;}
.tile_cell_label:hover{color:#fff;background:rgba(92,124,250,0.6);}
.tile_btn_row{position:absolute;top:6px;right:8px;z-index:2;display:flex;gap:4px;align-items:center;}
.tile_ghost_btn{width:26px;height:26px;padding:0;background:rgba(15,52,96,0.45);color:rgba(224,224,224,0.8);border:1px solid rgba(92,124,250,0.45);border-radius:13px;cursor:pointer;font-size:13px;line-height:1;font-family:inherit;}
.tile_ghost_btn:hover{background:rgba(92,124,250,0.75);color:#fff;}
.tile_view_btn{background:#0f3460;color:#e0e0e0;border:1px solid #5c7cfa;border-radius:4px;padding:3px 10px;cursor:pointer;font-size:12px;font-family:inherit;}
.tile_view_btn:hover{background:#5c7cfa;}
.tile_cell img{max-width:100%;max-height:100%;object-fit:contain;transform-origin:center center;}
.tile_reset_btn{position:absolute;bottom:8px;right:8px;z-index:2;display:none;width:30px;height:30px;background:rgba(15,52,96,0.45);color:rgba(224,224,224,0.8);border:1px solid rgba(92,124,250,0.45);border-radius:15px;cursor:pointer;font-size:15px;line-height:1;font-family:inherit;}
.tile_reset_btn:hover{background:rgba(92,124,250,0.75);color:#fff;}
</style>
</head>
<body>
<div id="__ar3_tile_grid"></div>
<script>
(function() {
    var DATA = __AR3_TILE_DATA__;
    if (!DATA || !DATA.models) return;

    var grid = document.getElementById('__ar3_tile_grid');
    var draggedCell = null;
    var _cellsByModel = {};

    function queueSwitch(letter) {
        window.__ar3_tile_switch_queue = window.__ar3_tile_switch_queue || [];
        window.__ar3_tile_switch_queue.push(JSON.stringify({letter: letter}));
    }

    function queuePopup(key, src) {
        if (!src) return;
        window.__ar3_tile_popup_queue = window.__ar3_tile_popup_queue || [];
        window.__ar3_tile_popup_queue.push({key: key, src: src});
    }

    var panState = null;
    document.addEventListener('contextmenu', function(e) { e.preventDefault(); });
    document.addEventListener('mousemove', function(e) {
        if (!panState) return;
        panState.z.tx = panState.baseTx + (e.clientX - panState.startX);
        panState.z.ty = panState.baseTy + (e.clientY - panState.startY);
        panState.z.apply();
    });
    document.addEventListener('mouseup', function(e) {
        if (e.button === 2) panState = null;
    });

    function makeCell(labelText, key, src, letter) {
        var cell = document.createElement('div');
        cell.className = 'tile_cell';
        if (letter) _cellsByModel[letter] = cell;
        var label = document.createElement('span');
        label.className = 'tile_cell_label';
        label.textContent = labelText;
        if (letter) {
            label.onclick = function(e) { e.stopPropagation(); queueSwitch(letter); };
            label.title = '点击切换到模型' + letter + '标签页';
        }
        cell.appendChild(label);

        var btnRow = document.createElement('div');
        btnRow.className = 'tile_btn_row';
        cell.appendChild(btnRow);

        var viewBtn = document.createElement('button');
        viewBtn.className = 'tile_view_btn';
        viewBtn.textContent = '\u7a97\u53e3\u67e5\u770b';
        viewBtn.title = '\u5728\u72ec\u7acb\u7a97\u53e3\u4e2d\u67e5\u770b\u6b64\u56fe\u7247';
        viewBtn.draggable = false;
        viewBtn.onclick = function(e) { e.stopPropagation(); queuePopup(key, src); };
        btnRow.appendChild(viewBtn);

        if (src) {
            var img = document.createElement('img');
            img.src = src;
            img.draggable = false;
            cell.appendChild(img);

            var resetBtn = document.createElement('button');
            resetBtn.className = 'tile_reset_btn';
            resetBtn.textContent = '\u21bb';
            resetBtn.title = '\u6062\u590d\u539f\u59cb\u5927\u5c0f\u3001\u4f4d\u7f6e\u548c\u65b9\u5411';
            resetBtn.draggable = false;
            cell.appendChild(resetBtn);

            var zoom = {scale: 1, tx: 0, ty: 0, rot: 0, mir: false};
            zoom.apply = function() {
                img.style.transform = 'translate(' + zoom.tx + 'px,' + zoom.ty + 'px) rotate(' + zoom.rot + 'deg) scale(' + zoom.scale + ')' + (zoom.mir ? ' scaleX(-1)' : '');
                var changed = (zoom.scale > 1.001 || zoom.rot % 360 !== 0 || zoom.mir);
                resetBtn.style.display = changed ? 'block' : 'none';
            };
            zoom.reset = function() {
                zoom.scale = 1; zoom.tx = 0; zoom.ty = 0; zoom.rot = 0; zoom.mir = false;
                zoom.apply();
            };
            zoom.apply();
            cell.__ar3_zoom = zoom;

            resetBtn.onclick = function(e) { e.stopPropagation(); zoom.reset(); };

            function makeGhostBtn(text, title) {
                var b = document.createElement('button');
                b.className = 'tile_ghost_btn';
                b.textContent = text;
                b.title = title;
                b.draggable = false;
                return b;
            }

            var mirrorBtn = makeGhostBtn('\u21c4', '\u6c34\u5e73\u7ffb\u8f6c');
            mirrorBtn.onclick = function(e) { e.stopPropagation(); zoom.mir = !zoom.mir; zoom.apply(); };
            var rotLBtn = makeGhostBtn('\u21b6', '\u5411\u5de6\u65cb\u8f6c 15\u00b0');
            rotLBtn.onclick = function(e) { e.stopPropagation(); zoom.rot -= 15; zoom.apply(); };
            var rotRBtn = makeGhostBtn('\u21b7', '\u5411\u53f3\u65cb\u8f6c 15\u00b0');
            rotRBtn.onclick = function(e) { e.stopPropagation(); zoom.rot += 15; zoom.apply(); };
            btnRow.insertBefore(rotRBtn, viewBtn);
            btnRow.insertBefore(rotLBtn, rotRBtn);
            btnRow.insertBefore(mirrorBtn, rotLBtn);

            cell.addEventListener('wheel', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var factor = (e.deltaY < 0) ? 1.15 : (1 / 1.15);
                zoom.scale = Math.min(10, Math.max(1, zoom.scale * factor));
                if (zoom.scale <= 1.001) { zoom.scale = 1; zoom.tx = 0; zoom.ty = 0; }
                zoom.apply();
            }, {passive: false});

            cell.addEventListener('mousedown', function(e) {
                if (e.button !== 2 || zoom.scale <= 1) return;
                e.preventDefault();
                panState = {z: zoom, startX: e.clientX, startY: e.clientY, baseTx: zoom.tx, baseTy: zoom.ty};
            });
        }
        return cell;
    }

    function makeDraggable(cell) {
        cell.draggable = true;
        cell.style.cursor = 'grab';
        cell.addEventListener('dragstart', function(e) {
            draggedCell = cell;
            cell.style.opacity = '0.4';
            if (e.dataTransfer) {
                e.dataTransfer.effectAllowed = 'move';
                try { e.dataTransfer.setData('text/plain', cell.getAttribute('data-model') || ''); } catch (err) {}
            }
        });
        cell.addEventListener('dragend', function() {
            cell.style.opacity = '1';
            draggedCell = null;
        });
        cell.addEventListener('dragover', function(e) {
            if (!draggedCell || draggedCell === cell) return;
            e.preventDefault();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
            var cells = Array.prototype.slice.call(grid.children);
            var from = cells.indexOf(draggedCell);
            var to = cells.indexOf(cell);
            if (from < 0 || to < 0 || from === to) return;
            if (from < to) grid.insertBefore(draggedCell, cell.nextSibling);
            else grid.insertBefore(draggedCell, cell);
        });
        cell.addEventListener('drop', function(e) { e.preventDefault(); });
    }

    var refData = DATA.ref || {};
    var refCell = makeCell('\u53c2\u8003\u56fe', 'ref_image', refData.src, null);
    refCell.setAttribute('data-ref', '1');
    grid.appendChild(refCell);

    (DATA.models || []).forEach(function(m) {
        var cell = makeCell('\u6a21\u578b' + m.letter, 'model_' + m.letter, m.src, m.letter);
        cell.setAttribute('data-model', m.letter);
        makeDraggable(cell);
        grid.appendChild(cell);
    });

    window.setTileHighlight = function(sync) {
        if (!sync) { window.__ar3_tile_highlight_log = 'no_sync'; return; }
        window.__ar3_tile_highlight_log = JSON.stringify(sync);
        var active = sync.active;
        var states = sync.states || {};
        Object.keys(_cellsByModel).forEach(function(l) {
            var cell = _cellsByModel[l];
            if (!cell) return;
            cell.classList.remove('tile_cell_active_incomplete', 'tile_cell_active_complete');
            if (l === active) {
                var st = states[l] || {};
                var cls = st.incomplete ? 'tile_cell_active_incomplete' : 'tile_cell_active_complete';
                cell.classList.add(cls);
                cell.setAttribute('data-highlight', cls);
            } else {
                cell.removeAttribute('data-highlight');
            }
        });
    };
})();
</script>
</body>
</html>
"""


class TiledDialog(QDialog):
    def __init__(self, tile_data, parent=None, profile=None):
        super().__init__(parent)
        self.setWindowTitle("平铺对比")
        self.resize(1100, 750)
        self.setMinimumSize(600, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self._profile = profile
        self._tile_data = tile_data
        self._view = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self._profile:
            page = QWebEnginePage(self._profile, self)
        else:
            page = QWebEnginePage(self)

        self._view = QWebEngineView(self)
        self._view.setPage(page)

        html = TILED_HTML.replace("__AR3_TILE_DATA__", json.dumps(self._tile_data))
        self._view.setHtml(html, QUrl("about:blank"))

        layout.addWidget(self._view)

    def has_view(self):
        return self._view is not None

    def page(self):
        if self._view:
            return self._view.page()
        return None

    def run_js(self, js, callback=None):
        if self._view:
            self._view.page().runJavaScript(js, callback)
