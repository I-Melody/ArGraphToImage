"""
JavaScript templates injected into QWebEngineView pages.
All templates must be self-contained (no external dependencies).
"""

DETECT_PAGE_STRUCTURE = """
(function() {
    var result = {
        page_type: 'unknown',
        reference_image: null,
        model_images: [],
        evaluation_groups: [],
        rank_items: [],
        toolbar_items: [],
        anchor_items: [],
        matched: false
    };

    // Detect: grid-item containers with id pattern "content_engine*"
    var gridItems = document.querySelectorAll('.grid-item[id*="content_engine"]');
    if (gridItems.length > 0) {
        result.page_type = 'tencent_label_workbench';
        result.matched = true;
    }

    // Extract grid items (reference + model images)
    gridItems.forEach(function(item) {
        var id = item.id || '';
        var title = '';
        var titleEl = item.querySelector('.item-title');
        if (titleEl) title = titleEl.textContent.trim();

        var imgEl = item.querySelector('img.img');
        var imgSrc = imgEl ? imgEl.src : '';

        var altImgs = item.querySelectorAll('img[alt]');
        var altMap = {};
        altImgs.forEach(function(ai) {
            if (ai.alt) altMap[ai.alt] = ai.src;
        });

        var entry = {
            id: id,
            title: title,
            image_src: imgSrc,
            alt_images: altMap
        };

        if (id.indexOf('ref_image') >= 0) {
            result.reference_image = entry;
        } else if (id.indexOf('model_') >= 0) {
            result.model_images.push(entry);
        }
    });

    // Extract evaluation groups (each dimension is exactly one .multiple-select
    // that contains checkbox options; remark-box form-items have none and are skipped)
    var evalGroups = document.querySelectorAll('.multiple-select');
    var groups = [];
    evalGroups.forEach(function(el) {
        var labelEl = el.querySelector('.ivu-form-item-label, label');
        if (!labelEl) return;
        var labelText = labelEl.textContent.trim();
        if (!labelText) return;

        var options = [];
        el.querySelectorAll('.checkboxItem').forEach(function(item) {
            var cb = item.querySelector('input[type="checkbox"]');
            options.push({
                value: cb ? cb.value : (item.textContent || '').trim(),
                checked: (item.className || '').indexOf('ivu-checkbox-wrapper-checked') >= 0
            });
        });
        if (options.length === 0) return;

        // Determine which model this belongs to (A-H prefix)
        var modelLetter = '';
        var match = labelText.match(/^([A-H])-/);
        if (match) modelLetter = match[1];

        // Find associated remark input (.customInput.horizontalLtr)
        // The remark box resides in a sibling subtree; the common ancestor is
        // the enclosing .t-col.t-col-6 that wraps both for the same dimension.
        var remarkText = '';
        var remarkFound = false;
        var commonParent = el;
        for (var k = 0; k < 10; k++) {
            commonParent = commonParent.parentElement;
            if (!commonParent) break;
            if ((commonParent.className || '').indexOf('t-col-6') >= 0) {
                var ri = commonParent.querySelector('.customInput.horizontalLtr');
                if (ri) {
                    remarkText = ri.textContent || '';
                    remarkFound = true;
                    break;
                }
            }
        }

        groups.push({
            label: labelText,
            model_letter: modelLetter,
            options: options,
            remark: remarkText,
            remark_found: remarkFound
        });
    });

    // Group evaluations by model letter
    var modelMap = {};
    groups.forEach(function(g) {
        if (!g.model_letter) return;
        if (!modelMap[g.model_letter]) {
            modelMap[g.model_letter] = [];
        }
        modelMap[g.model_letter].push(g);
    });

    for (var k in modelMap) {
        result.evaluation_groups.push({
            model_letter: k,
            dimensions: modelMap[k]
        });
    }

    // Extract rank items
    var rankItems = document.querySelectorAll('.rank-list-item');
    rankItems.forEach(function(item, idx) {
        var text = item.textContent.replace(/\\s/g, '').trim();
        result.rank_items.push({model: text, position: idx});
    });

    // Extract anchor navigation items
    var anchorLinks = document.querySelectorAll('.t-anchor__item-link');
    anchorLinks.forEach(function(link) {
        result.anchor_items.push(link.textContent.trim());
    });

    // Extract toolbar items
    var toolbarBtns = document.querySelectorAll('.z-level__item');
    toolbarBtns.forEach(function(btn) {
        var text = btn.textContent.trim();
        if (text) result.toolbar_items.push(text);
    });

    return JSON.stringify(result);
})();
"""

MONITOR_PAGE_CHANGES = """
(function() {
    if (window.__annotation_monitor_active) return 'already_active';
    window.__annotation_monitor_active = true;

    var observer = new MutationObserver(function(mutations) {
        var changes = [];
        mutations.forEach(function(m) {
            if (m.type === 'childList') {
                m.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && node.classList) {
                        if (node.classList.contains('grid-item') ||
                            node.classList.contains('multiple-select') ||
                            node.classList.contains('rank-list-item')) {
                            changes.push({
                                type: 'added',
                                classes: Array.from(node.classList),
                                id: node.id || ''
                            });
                        }
                    }
                });
                m.removedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && node.classList) {
                        if (node.classList.contains('grid-item') ||
                            node.classList.contains('multiple-select') ||
                            node.classList.contains('rank-list-item')) {
                            changes.push({
                                type: 'removed',
                                classes: Array.from(node.classList),
                                id: node.id || ''
                            });
                        }
                    }
                });
            }
            if (m.type === 'attributes' && m.attributeName === 'src') {
                changes.push({
                    type: 'attr_changed',
                    id: m.target.id || m.target.className,
                    attr: m.attributeName,
                    newValue: m.target.getAttribute(m.attributeName)
                });
            }
        });
        if (changes.length > 0) {
            window.__annotation_last_changes = JSON.stringify(changes);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['src', 'checked', 'value']
    });

    return 'monitoring_active';
})();
"""

GET_PAGE_CHANGES = """
(function() {
    var changes = window.__annotation_last_changes || '[]';
    window.__annotation_last_changes = '[]';
    return changes;
})();
"""

APPLY_TABBED_LAYOUT = """
(function() {
    if (document.getElementById('__ar3_tab_overlay')) {
        return JSON.stringify({status: 'already_transformed', count: 0});
    }

    var gridItems = document.querySelectorAll('.grid-item[id*="content_engine"]');
    if (gridItems.length === 0) {
        return JSON.stringify({status: 'no_grid_found', count: 0});
    }

    if (!document.getElementById('__ar3_styles')) {
        var sty = document.createElement('style');
        sty.id = '__ar3_styles';
        sty.textContent = '.__ar3_dim_card{background:#16213e;border-radius:6px;padding:10px 14px;margin-bottom:10px}' +
            '.__ar3_dim_title{color:#a0a0b0;font-size:13px;margin-bottom:8px}' +
            '.__ar3_dim_opts{display:flex;gap:16px;flex-wrap:wrap}' +
            '.__ar3_cb_label{display:flex;align-items:center;gap:5px;color:#e0e0e0;font-size:13px;cursor:pointer}' +
            '.__ar3_cb_label input{accent-color:#e94560}' +
            '.__ar3_reason_box{display:none;margin-top:8px}' +
            '.__ar3_reason_box .__ar3_reason_input{width:100%;min-height:56px;max-height:160px;overflow-y:auto;background:#12122a;color:#e0e0e0;border:1px solid #2a2a4a;border-radius:4px;padding:6px 8px;font-size:13px;line-height:1.5;box-sizing:border-box;white-space:pre-wrap;word-break:break-word;outline:none}' +
            '.__ar3_reason_box .__ar3_reason_input:focus{border-color:#5c7cfa}' +
            '.__ar3_reason_box .__ar3_reason_input:empty:before{content:attr(data-placeholder);color:#606080}' +
            '.__ar3_img_side{width:100%;height:100%;position:relative;cursor:pointer;overflow:hidden;border-radius:8px;background:#16213e;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:160px}' +
            '.__ar3_img_side img{max-width:100%;max-height:100%;object-fit:contain;border-radius:4px;transition:transform 0.2s}' +
            '.__ar3_img_side:hover img{transform:scale(1.02)}' +
            '.__ar3_img_label{color:#a0a0b0;font-size:12px;padding:6px 0;position:absolute;top:4px;left:10px}';
        document.head.appendChild(sty);
    }

    var refItem = null, modelItems = [];
    gridItems.forEach(function(item) {
        if (item.id.indexOf('ref_image') >= 0) refItem = item;
        else if (item.id.indexOf('model_') >= 0) modelItems.push(item);
    });

    // Source of truth for a selected option is the wrapper class
    // 'ivu-checkbox-wrapper-checked', NOT input.checked (which is unset in the DOM).
    var _ar3_selected_option = function(msEl) {
        if (!msEl) return '';
        var items = msEl.querySelectorAll('.checkboxItem');
        for (var i = 0; i < items.length; i++) {
            if ((items[i].className || '').indexOf('ivu-checkbox-wrapper-checked') >= 0) {
                var inp = items[i].querySelector('input[type="checkbox"]');
                if (inp && inp.value) return inp.value;
                return (items[i].textContent || '').trim();
            }
        }
        return '';
    };

    // Drive the original iView checkbox group toward a single selected value by
    // simulating REAL clicks (setting input.checked does not update Vue state).
    // One mismatched item is toggled per pass, then we re-query after Vue's async
    // re-render (which replaces nodes / updates wrapper classes) until it settles.
    var _ar3_apply_option = function(msEl, targetValue, pass) {
        pass = pass || 0;
        if (pass > 5 || !msEl) return;
        var items = msEl.querySelectorAll('.checkboxItem');
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var inp = it.querySelector('input[type="checkbox"]');
            var val = (inp && inp.value) ? inp.value : (it.textContent || '').trim();
            var isChecked = (it.className || '').indexOf('ivu-checkbox-wrapper-checked') >= 0;
            var want = (val === targetValue);
            if (want !== isChecked) {
                (inp || it).click();
                setTimeout(function() { _ar3_apply_option(msEl, targetValue, pass + 1); }, 60);
                return;
            }
        }
    };

    var evalByModel = {};
    document.querySelectorAll('.multiple-select').forEach(function(el) {
        var labelEl = el.querySelector('.ivu-form-item-label, label');
        if (!labelEl) return;
        var labelText = labelEl.textContent.trim();
        var match = labelText.match(/^([A-H])-/);
        if (!match) return;
        var letter = match[1];
        if (!evalByModel[letter]) evalByModel[letter] = [];
        evalByModel[letter].push(el);
    });

    var rankColors = [];
    document.querySelectorAll('.rank-title').forEach(function(el) {
        rankColors.push(el.style.backgroundColor || '');
    });

    var rankListItems = [];
    document.querySelectorAll('.rank-list-item').forEach(function(el) {
        rankListItems.push((el.childNodes[0] || {}).textContent || '');
    });

    var modelScores = {};

    // Shared per-dimension scale multiplier (by dimension index 0..4). Changing the
    // slider on any tab applies the same multiplier to that dimension across ALL tabs.
    var _ar3_adj_mults = [0.1, 0.5, 1, 2, 10];
    var _ar3_dim_scale_idx = [2, 2, 2, 2, 2];
    var _ar3_dim_scale_listeners = [[], [], [], [], []];
    var _ar3_broadcasting_scale = false;
    var _ar3_set_dim_scale = function(dimIdx, sliderIdx) {
        if (dimIdx < 0 || dimIdx > 4) return;
        _ar3_dim_scale_idx[dimIdx] = sliderIdx;
        if (_ar3_broadcasting_scale) return;
        _ar3_broadcasting_scale = true;
        _ar3_dim_scale_listeners[dimIdx].forEach(function(fn) { fn(sliderIdx); });
        _ar3_broadcasting_scale = false;
    };

    // Lightbox — remove any stale one from a previous APPLY so we never end up with
    // duplicate #__ar3_lightbox nodes (which caused a black screen with no image).
    var _oldLb = document.getElementById('__ar3_lightbox');
    if (_oldLb && _oldLb.parentNode) _oldLb.parentNode.removeChild(_oldLb);

    var lightbox = document.createElement('div');
    lightbox.id = '__ar3_lightbox';
    lightbox.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100%;height:100%;z-index:100000;background:rgba(0,0,0,0.9);cursor:zoom-out;align-items:center;justify-content:center;overflow:hidden;';
    var lightboxImg = document.createElement('img');
    lightboxImg.id = '__ar3_lightbox_img';
    lightboxImg.style.cssText = 'max-width:95%;max-height:95%;object-fit:contain;border-radius:6px;box-shadow:0 0 40px rgba(0,0,0,0.6);transform-origin:center center;cursor:grab;';
    lightbox.appendChild(lightboxImg);
    // Click background to close; clicking the image itself does not close (so you can zoom/drag).
    lightbox.onclick = function() { lightbox.style.display = 'none'; };
    lightboxImg.onclick = function(e) { e.stopPropagation(); };
    document.body.appendChild(lightbox);

    var _ar3_lb_scale = 1, _ar3_lb_tx = 0, _ar3_lb_ty = 0;
    var _ar3_lb_dragging = false, _ar3_lb_startX = 0, _ar3_lb_startY = 0;
    function _ar3_lb_apply() {
        lightboxImg.style.transform = 'translate(' + _ar3_lb_tx + 'px,' + _ar3_lb_ty + 'px) scale(' + _ar3_lb_scale + ')';
    }
    function closeLightbox() { lightbox.style.display = 'none'; }
    function showLightbox(src) {
        lightboxImg.src = src;
        _ar3_lb_scale = 1; _ar3_lb_tx = 0; _ar3_lb_ty = 0;
        _ar3_lb_apply();
        lightbox.style.display = 'flex';
    }
    // Scroll wheel zooms the enlarged image.
    lightbox.addEventListener('wheel', function(e) {
        e.preventDefault();
        _ar3_lb_scale *= (e.deltaY < 0 ? 1.15 : 1 / 1.15);
        if (_ar3_lb_scale < 0.2) _ar3_lb_scale = 0.2;
        if (_ar3_lb_scale > 12) _ar3_lb_scale = 12;
        _ar3_lb_apply();
    }, {passive: false});
    // Drag to pan the enlarged image. mousedown on the image starts a drag; the
    // background click-to-close is suppressed while/after dragging.
    lightboxImg.addEventListener('mousedown', function(e) {
        e.preventDefault(); e.stopPropagation();
        _ar3_lb_dragging = true;
        _ar3_lb_startX = e.clientX - _ar3_lb_tx;
        _ar3_lb_startY = e.clientY - _ar3_lb_ty;
        lightboxImg.style.cursor = 'grabbing';
    });
    window.addEventListener('mousemove', function(e) {
        if (!_ar3_lb_dragging) return;
        _ar3_lb_tx = e.clientX - _ar3_lb_startX;
        _ar3_lb_ty = e.clientY - _ar3_lb_startY;
        _ar3_lb_apply();
    });
    window.addEventListener('mouseup', function() {
        if (_ar3_lb_dragging) { _ar3_lb_dragging = false; lightboxImg.style.cursor = 'grab'; }
    });
    // ESC exits the enlarged view.
    window.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && lightbox.style.display !== 'none') {
            e.preventDefault(); e.stopPropagation();
            closeLightbox();
        }
    }, true);

    // ---- AI compare: one button per tab uploads BOTH 参考图 + 模型图 and asks the
    // model to describe their per-dimension DIFFERENCES. Python drains
    // window.__ar3_ai_queue and calls window.__ar3_ai_render(id, jsonStr).
    // Cached raw results per request id (e.g. '__ar3_ai_cmp_A') live in window.__ar3_last_ai.
    window.__ar3_ai_queue = window.__ar3_ai_queue || [];
    if (typeof window.__ar3_last_ai !== 'object' || !window.__ar3_last_ai) window.__ar3_last_ai = {};
    // Task signature = current reference-image src. If it changed since the previous
    // overlay build, the cached comparisons belong to a previous 题目 → drop them so a
    // new question does NOT auto-fill with the last question's AI content.
    var _ar3_task_sig = (function() { var im = refItem && refItem.querySelector('img.img'); return im ? im.src : ''; })();
    if (window.__ar3_ai_task_sig !== _ar3_task_sig) {
        window.__ar3_last_ai = {};
        window.__ar3_ai_task_sig = _ar3_task_sig;
    }
    window.__ar3_fill_btns = [];
    window.__ar3_refresh_fill_btns = function() {
        window.__ar3_fill_btns.forEach(function(f) { if (f && f.update) f.update(); });
    };
    var _ar3_ai_order = ['整体身份','整体形状与局部结构','颜色与材质','图案装饰logo商标','文字信息'];

    var _ar3_get_ai = function(reqId) {
        var raw = window.__ar3_last_ai[reqId];
        if (!raw) return null;
        try { return JSON.parse(raw); } catch (e) { return null; }
    };

    var _ar3_grab_img = function(img) {
        if (!img || !img.src) return null;
        try {
            var c = document.createElement('canvas');
            c.width = img.naturalWidth || img.width;
            c.height = img.naturalHeight || img.height;
            c.getContext('2d').drawImage(img, 0, 0);
            return c.toDataURL('image/jpeg', 0.9);
        } catch (e) { return img.src; }
    };

    function _ar3_render_into(out, jsonStr) {
        var res;
        try { res = JSON.parse(jsonStr); } catch (e) { res = {error: '返回解析失败'}; }
        if (res && res.error) { out.textContent = 'AI失败：' + res.error; out.style.color = '#e94560'; return; }
        out.style.color = '#a0a0b0';
        var html = '';
        _ar3_ai_order.forEach(function(k) {
            var v = res[k];
            if (v == null) return;
            if (typeof v === 'object') {
                html += '<div style="margin-bottom:6px;"><b style="color:#5c7cfa;">' + k + '</b>';
                if (v['参考图'] != null) html += '<div>参考图：' + String(v['参考图']) + '</div>';
                if (v['生成图'] != null) html += '<div>生成图：' + String(v['生成图']) + '</div>';
                if (v['差异'] != null) html += '<div style="color:#e0a030;">差异：' + String(v['差异']) + '</div>';
                html += '</div>';
            } else {
                html += '<div style="margin-bottom:4px;"><b style="color:#5c7cfa;">' + k + '：</b>' + String(v) + '</div>';
            }
        });
        out.innerHTML = html || ('<pre style="white-space:pre-wrap;margin:0;">' + (res.raw || JSON.stringify(res)) + '</pre>');
    }

    window.__ar3_ai_render = function(id, jsonStr) {
        window.__ar3_last_ai[id] = jsonStr;
        if (typeof window.__ar3_refresh_fill_btns === 'function') window.__ar3_refresh_fill_btns();
        var out = document.getElementById(id);
        if (!out) return;
        if (out.__ar3_btn) { out.__ar3_btn.disabled = false; out.__ar3_btn.style.opacity = '1'; }
        _ar3_render_into(out, jsonStr);
    };

    // Comparison button/output for one tab (参考图 vs that model图).
    function _ar3_make_ai_cmp_row(letter, getRefImg, getModelImg) {
        var reqId = '__ar3_ai_cmp_' + letter;
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:flex-start;gap:8px;margin-top:6px;';
        var btn = document.createElement('button');
        btn.textContent = 'AI对比';
        btn.title = '同时上传参考图与模型图，用智谱AI(GLM-4.6V)对比两图差异';
        btn.style.cssText = 'flex-shrink:0;background:#0f3460;color:#e0e0e0;border:1px solid #5c7cfa;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:13px;font-weight:bold;font-family:inherit;';
        var out = document.createElement('div');
        out.id = reqId;
        out.className = '__ar3_ai_out';
        out.style.cssText = 'flex:1;min-width:0;font-size:12px;color:#a0a0b0;white-space:pre-wrap;word-break:break-word;max-height:180px;overflow-y:auto;line-height:1.5;';
        out.__ar3_btn = btn;
        if (window.__ar3_last_ai[reqId]) { _ar3_render_into(out, window.__ar3_last_ai[reqId]); }
        btn.onclick = function() {
            var refImg = getRefImg(), modImg = getModelImg();
            var refRef = _ar3_grab_img(refImg), modRef = _ar3_grab_img(modImg);
            if (!refRef || !modRef) { out.textContent = '缺少参考图或模型图'; return; }
            out.style.color = '#a0a0b0'; out.textContent = 'AI对比中...';
            btn.disabled = true; btn.style.opacity = '0.6';
            window.__ar3_ai_queue.push({id: reqId, ref: refRef, model: modRef});
        };
        wrap.appendChild(btn);
        wrap.appendChild(out);
        return wrap;
    }

    var overlay = document.createElement('div');
    overlay.id = '__ar3_tab_overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;background:#1a1a2e;display:flex;flex-direction:column;font-family:"Microsoft YaHei",sans-serif;';

    var topBar = document.createElement('div');
    topBar.style.cssText = 'display:flex;align-items:center;background:#16213e;border-bottom:2px solid #2a2a4a;padding:0 8px;flex-shrink:0;min-height:42px;';
    var tabHeader = document.createElement('div');
    tabHeader.id = '__ar3_tab_header';
    tabHeader.style.cssText = 'display:flex;flex:1;overflow-x:auto;';
    topBar.appendChild(tabHeader);
    var closeBtn = document.createElement('button');
    closeBtn.textContent = '返回原页面';
    closeBtn.style.cssText = 'flex-shrink:0;margin-left:8px;background:#e94560;color:#fff;border:none;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:12px;font-weight:bold;';
    closeBtn.onclick = function() { document.body.removeChild(overlay); if (lightbox.parentNode) lightbox.parentNode.removeChild(lightbox); window.__ar3_tabs = null; };
    topBar.appendChild(closeBtn);
    overlay.appendChild(topBar);

    var tabContent = document.createElement('div');
    tabContent.id = '__ar3_tab_content';
    tabContent.style.cssText = 'flex:1;display:flex;overflow:hidden;min-height:0;';
    overlay.appendChild(tabContent);

    var bottomBar = document.createElement('div');
    bottomBar.id = '__ar3_rank_bar';
    bottomBar.style.cssText = 'flex-shrink:0;background:#16213e;border-top:2px solid #2a2a4a;padding:8px 12px 10px;display:flex;align-items:stretch;gap:10px;';

    var rankCols = document.createElement('div');
    rankCols.style.cssText = 'flex:1;min-width:0;';
    var rankTitleRow = document.createElement('div');
    rankTitleRow.style.cssText = 'display:flex;gap:4px;margin-bottom:8px;';
    var labels = ['RANK 1','RANK 2','RANK 3','RANK 4','RANK 5','RANK 6','RANK 7','RANK 8'];
    labels.forEach(function(lbl, i) {
        var badge = document.createElement('span');
        badge.textContent = lbl;
        badge.style.cssText = 'flex:1;text-align:center;padding:4px 0;border-radius:4px;font-size:12px;font-weight:bold;color:#fff;background:' + (rankColors[i] || '#333') + ';';
        rankTitleRow.appendChild(badge);
    });
    rankCols.appendChild(rankTitleRow);
    var rankListRow = document.createElement('div');
    rankListRow.id = '__ar3_rank_list';
    rankListRow.style.cssText = 'display:flex;gap:4px;';
    var ranks = rankListItems.length ? rankListItems : ['模型A','模型B','模型C','模型D','模型E','模型F','模型G','模型H'];
    ranks.forEach(function(name) {
        var slot = document.createElement('div');
        slot.style.cssText = 'flex:1;display:flex;align-items:center;justify-content:center;gap:4px;background:#1a1a2e;border-radius:4px;padding:6px 4px;font-size:12px;color:#e0e0e0;';
        slot.innerHTML = '<span style="transform:rotate(90deg);opacity:0.4;font-size:10px;">|||</span> ' + name;
        rankListRow.appendChild(slot);
    });
    rankCols.appendChild(rankListRow);
    bottomBar.appendChild(rankCols);

    // ---- 排序 button: rank models by in-app score (desc); ties share a rank ----
    // The original page's rank list (.rank[last]) is 8 fixed .rank-content "buckets"
    // aligned with the RANK1..8 titles. A tie = multiple .rank-list-item in the SAME
    // bucket; trailing buckets become empty.
    //
    // The source of truth is a Vue 2 component `z-drag-sort_card` with $data.list =
    // array of 8 arrays (one per bucket) of model objects {idx,label,value}. A pure DOM
    // move is reverted when the page re-renders (e.g. on 确认), so we mutate that model
    // directly. DOM move is kept as a fallback when the Vue instance can't be reached.
    var _ar3_find_sort_card = function() {
        var groups = document.querySelectorAll('.rank');
        if (groups.length < 2) return null;
        var listRank = groups[groups.length - 1];
        var bucket = listRank.children[0];
        var vm = bucket && bucket.__vue__;
        for (var up = 0; up < 8 && vm; up++) {
            if (vm.$data && Array.isArray(vm.$data.list) && vm.$data.list.length && Array.isArray(vm.$data.list[0])) {
                return vm;
            }
            vm = vm.$parent;
        }
        return null;
    };

    var _ar3_letter_of = function(model) {
        var lab = (model && (model.label || model.name || model.title || model.value)) + '';
        var m = lab.match(/([A-H])(?!.*[A-H])/);
        return m ? m[1] : '';
    };

    var _ar3_apply_rank_dom = function(scored) {
        try {
            var rankGroups = document.querySelectorAll('.rank');
            if (rankGroups.length < 2) return;
            var listRank = rankGroups[rankGroups.length - 1];
            var buckets = listRank.children;
            if (!buckets || buckets.length === 0) return;
            var byLetter = {};
            listRank.querySelectorAll('.rank-list-item').forEach(function(it) {
                var m = (it.textContent || '').match(/模型([A-H])/);
                if (m) byLetter[m[1]] = it;
            });
            scored.forEach(function(s) {
                var it = byLetter[s.letter];
                var bucket = buckets[s.rank - 1];
                if (it && bucket && it.parentElement !== bucket) bucket.appendChild(it);
            });
        } catch (e) {}
    };

    var _ar3_apply_rank_to_original = function(scored) {
        try {
            var card = _ar3_find_sort_card();
            if (!card) { _ar3_apply_rank_dom(scored); return; }
            var oldList = card.$data.list;
            var n = oldList.length;
            // map letter -> model object (preserve original object identity/fields)
            var byLetter = {};
            oldList.forEach(function(arr) {
                (arr || []).forEach(function(model) {
                    var L = _ar3_letter_of(model);
                    if (L) byLetter[L] = model;
                });
            });
            var newList = [];
            for (var i = 0; i < n; i++) newList.push([]);
            scored.forEach(function(s) {
                var model = byLetter[s.letter];
                var bi = s.rank - 1;
                if (model && bi >= 0 && bi < n) newList[bi].push(model);
            });
            card.list = newList;            // reactive reassign (Vue 2 detects this)
            if (card.$forceUpdate) card.$forceUpdate();
        } catch (e) {
            _ar3_apply_rank_dom(scored);
        }
    };

    var _ar3_do_sort = function() {
        var scored = modelLetters.map(function(L) {
            return {letter: L, score: (typeof modelScores[L] === 'number' ? modelScores[L] : 0)};
        });
        scored.sort(function(a, b) { return b.score - a.score; });
        // Dense ranking (1,1,2,3...) — matches how the original page numbers ties.
        var rankCounter = 0;
        scored.forEach(function(s, i) {
            if (i === 0 || s.score !== scored[i - 1].score) rankCounter++;
            s.rank = rankCounter;
        });
        rankListRow.innerHTML = '';
        scored.forEach(function(s) {
            var color = rankColors[s.rank - 1] || '#333';
            var slot = document.createElement('div');
            slot.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;background:#1a1a2e;border-radius:4px;padding:5px 4px;font-size:12px;color:#e0e0e0;border-bottom:3px solid ' + color + ';';
            slot.innerHTML = '<span style="font-weight:bold;color:' + color + ';">RANK ' + s.rank + '</span>' +
                '<span>模型' + s.letter + '</span>' +
                '<span style="opacity:0.7;font-size:11px;">' + (s.score / 100).toFixed(2) + '分</span>';
            rankListRow.appendChild(slot);
        });
        _ar3_apply_rank_to_original(scored);
    };

    var sortBtn = document.createElement('button');
    sortBtn.id = '__ar3_sort_btn';
    sortBtn.textContent = '排序';
    sortBtn.title = '根据评分从高到低自动排序（同分同名次）';
    sortBtn.style.cssText = 'flex-shrink:0;align-self:center;background:#e94560;color:#fff;border:none;border-radius:4px;padding:8px 18px;cursor:pointer;font-size:13px;font-weight:bold;white-space:nowrap;';
    sortBtn.onclick = _ar3_do_sort;
    bottomBar.appendChild(sortBtn);

    overlay.appendChild(bottomBar);

    var modelLetters = [];
    modelItems.forEach(function(item) {
        var m = item.id.match(/model_([A-H])$/);
        if (m) modelLetters.push(m[1]);
    });
    modelLetters.sort();

    var tabs = {};
    modelLetters.forEach(function(letter, idx) {
        var tabBtn = document.createElement('button');
        tabBtn.id = '__ar3_tab_btn_' + letter;
        tabBtn.textContent = '模型' + letter;
        tabBtn.style.cssText = 'background:' + (idx === 0 ? '#1a1a2e' : 'transparent') + ';color:' + (idx === 0 ? '#e94560' : '#a0a0b0') + ';border:none;border-bottom:' + (idx === 0 ? '2px solid #e94560' : '2px solid transparent') + ';padding:8px 18px;cursor:pointer;font-size:13px;white-space:nowrap;';
        tabBtn.setAttribute('data-model', letter);
        tabHeader.appendChild(tabBtn);

        var panel = document.createElement('div');
        panel.id = '__ar3_panel_' + letter;
        panel.style.cssText = 'flex:1;display:' + (idx === 0 ? 'flex' : 'none') + ';height:100%;overflow:hidden;flex-direction:row;';

        // Column 1 — 参考图
        var refCol = document.createElement('div');
        refCol.style.cssText = 'flex:1;min-width:0;display:flex;flex-direction:column;padding:10px;gap:4px;overflow-y:auto;border-right:1px solid #2a2a4a;';
        var refBox = document.createElement('div');
        refBox.className = '__ar3_img_side';
        refBox.innerHTML = '<span class="__ar3_img_label">参考图</span>';
        var ri = null;
        if (refItem) {
            ri = document.createElement('img');
            var refImg = refItem.querySelector('img.img');
            ri.src = refImg ? refImg.src : '';
            ri.setAttribute('data-sync', 'ref_image');
            ri.onclick = function(e) { e.stopPropagation(); showLightbox(ri.src); };
            refBox.appendChild(ri);
        }
        refCol.appendChild(refBox);

        // ---- Preserve-description block under the reference image ----
        var _ar3_preserve_text = '';
        try {
            var pdContainer = document.getElementById('engine0_default_item_preserve_description');
            if (pdContainer) {
                var tc = pdContainer.querySelector('.text-content');
                if (tc) _ar3_preserve_text = (tc.textContent || '').trim();
            }
        } catch (e) {}
        if (_ar3_preserve_text) {
            var pdBlock = document.createElement('div');
            pdBlock.style.cssText = 'margin-top:6px;padding:8px 10px;background:#16213e;border:1px solid #2a2a4a;border-radius:6px;font-size:12px;color:#a0a0b0;line-height:1.6;white-space:pre-wrap;word-break:break-word;max-height:140px;overflow-y:auto;';
            var pdTitle = document.createElement('div');
            pdTitle.textContent = '题目描述';
            pdTitle.style.cssText = 'font-size:11px;color:#5c7cfa;font-weight:bold;margin-bottom:4px;';
            pdBlock.appendChild(pdTitle);
            var pdText = document.createElement('div');
            pdText.textContent = _ar3_preserve_text;
            pdBlock.appendChild(pdText);
            refCol.appendChild(pdBlock);
        }

        panel.appendChild(refCol);

        // Column 2 — 模型图
        var modelCol = document.createElement('div');
        modelCol.style.cssText = 'flex:1;min-width:0;display:flex;flex-direction:column;padding:10px;gap:4px;overflow-y:auto;border-right:1px solid #2a2a4a;';
        var modelBox = document.createElement('div');
        modelBox.className = '__ar3_img_side';
        modelBox.innerHTML = '<span class="__ar3_img_label">模型' + letter + '</span>';
        var mi = null;
        var currentModelItem = null;
        modelItems.forEach(function(item) { if (item.id.indexOf('model_' + letter) >= 0) currentModelItem = item; });
        if (currentModelItem) {
            mi = document.createElement('img');
            var modelImg = currentModelItem.querySelector('img.img');
            mi.src = modelImg ? modelImg.src : '';
            mi.setAttribute('data-sync', 'model_' + letter);
            mi.onclick = function(e) { e.stopPropagation(); showLightbox(mi.src); };
            modelBox.appendChild(mi);
        }
        modelCol.appendChild(modelBox);
        modelCol.appendChild(_ar3_make_ai_cmp_row(
            letter,
            (function(imgEl) { return function() { return imgEl; }; })(ri),
            (function(imgEl) { return function() { return imgEl; }; })(mi)));
        panel.appendChild(modelCol);

        // Column 3 — 评价
        var rightSide = document.createElement('div');
        rightSide.style.cssText = 'flex:1;min-width:0;padding:10px 14px;overflow-y:auto;background:#12122a;';
        var evalHeader = document.createElement('div');
        evalHeader.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #2a2a4a;';
        var evalTitle = document.createElement('div');
        evalTitle.textContent = '评价 - 模型' + letter;
        evalTitle.style.cssText = 'color:#e0e0e0;font-size:14px;font-weight:bold;flex-shrink:0;';

        var progressLabel = document.createElement('div');
        progressLabel.className = '__ar3_progress_label';
        progressLabel.style.cssText = 'font-size:12px;color:#a0a0b0;white-space:nowrap;';

        var headerRight = document.createElement('div');
        headerRight.style.cssText = 'display:flex;align-items:center;gap:8px;flex-shrink:0;';

        // Tab-level submit button (left of the score badge) — writes EVERY dimension
        // of this model into the original page in one click (replaces per-dim 确定).
        var submitBtn = document.createElement('button');
        submitBtn.className = '__ar3_submit_btn';
        submitBtn.textContent = '提交本页';
        submitBtn.title = '将本模型所有维度的内容一次性填入原页面 (Ctrl+Enter)';
        submitBtn.style.cssText = 'background:#0f3460;color:#e0e0e0;border:1px solid #5c7cfa;border-radius:4px;padding:4px 14px;cursor:pointer;font-size:13px;font-weight:bold;font-family:inherit;white-space:nowrap;';

        var scoreBadge = document.createElement('div');
        scoreBadge.className = '__ar3_score_badge';
        scoreBadge.style.cssText = 'font-size:13px;font-weight:bold;color:#e94560;background:#3a1a2e;border:1px solid #e94560;border-radius:4px;padding:3px 10px;white-space:nowrap;';
        headerRight.appendChild(submitBtn);
        headerRight.appendChild(scoreBadge);
        evalHeader.appendChild(evalTitle);
        evalHeader.appendChild(progressLabel);
        evalHeader.appendChild(headerRight);
        rightSide.appendChild(evalHeader);

        var dims = evalByModel[letter] || [];

        // A dimension counts as "done" once a severity is selected; if it is 不一致
        // it also needs both 参考图/生成图 descriptions filled.
        var _ar3_dim_done = function(d) {
            if (!d.__ar3_reasonInfo) return false;
            var idx = d.__ar3_reasonInfo.getActiveIdx ? d.__ar3_reasonInfo.getActiveIdx() : -1;
            if (idx < 0) return false;
            var def = d.__ar3_reasonInfo.btnDefs[idx];
            if (def && def.value === '不一致') {
                return !!(d.__ar3_reasonInfo.taA.value.trim() && d.__ar3_reasonInfo.taB.value.trim());
            }
            return true;
        };

        var _ar3_update_progress = function() {
            var done = 0;
            dims.forEach(function(d) { if (_ar3_dim_done(d)) done++; });
            var total = dims.length;
            progressLabel.textContent = '已填 ' + done + '/' + total;
            progressLabel.style.color = (done === total && total > 0) ? '#0e9a4a' : '#e0a030';
            if (tabs[letter] && tabs[letter].btn) {
                var b = tabs[letter].btn;
                var mark = (total > 0 && done === total) ? ' ✓' : ' (' + done + '/' + total + ')';
                b.textContent = '模型' + letter + mark;
            }
            return {done: done, total: total};
        };

        var _ar3_update_score = function() {
            var total = 0;
            dims.forEach(function(d) {
                total += (typeof d.__ar3_score === 'number' ? d.__ar3_score : 0);
            });
            scoreBadge.textContent = '评分：' + (total / 100).toFixed(2);
            modelScores[letter] = total;
            _ar3_update_progress();
        };

        submitBtn.onclick = function() {
            dims.forEach(function(d) {
                if (!d.__ar3_reasonInfo || !d.__ar3_reasonInfo.submit) return;
                d.__ar3_reasonInfo.submit();
                d.__ar3_dirty = false;
            });
            var st = _ar3_update_progress();
            if (st.done < st.total) {
                submitBtn.textContent = '已提交(缺' + (st.total - st.done) + ')';
                submitBtn.style.background = '#7a5a0e';
            } else {
                submitBtn.textContent = '已提交';
                submitBtn.style.background = '#0e7a3a';
            }
            setTimeout(function() { submitBtn.textContent = '提交本页'; submitBtn.style.background = '#0f3460'; }, 1200);
        };

        dims.forEach(function(dim) {
            var card = document.createElement('div');
            card.className = '__ar3_dim_card';
            dim.__ar3_card = card;

            var labelEl = dim.querySelector('.ivu-form-item-label, label');
            var dimLabel = labelEl ? labelEl.textContent.trim() : '';

            var dimHeader = document.createElement('div');
            dimHeader.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;';
            var dimTitle = document.createElement('div');
            dimTitle.textContent = dimLabel;
            dimTitle.className = '__ar3_dim_title';
            dimTitle.style.marginBottom = '0';
            dimHeader.appendChild(dimTitle);
            card.appendChild(dimHeader);

            // ---- Find original remark input by matching dimension label prefix ----
            dim.__ar3_dimPrefix = '';
            (function() {
                var labelEl = dim.querySelector('.ivu-form-item-label, label');
                if (labelEl) {
                    var m = labelEl.textContent.trim().match(/^([A-H]-A\\d+)/);
                    if (m) dim.__ar3_dimPrefix = m[1];
                }
            })();

            var _ar3_find_original_input = function(dimEl) {
                var prefix = dimEl.__ar3_dimPrefix || '';
                if (!prefix) return null;
                var marker = prefix + '不一致';
                var allInputs = document.querySelectorAll('.customInput.horizontalLtr');
                // First pass: search for "prefix+不一致" in ancestor text (limited depth)
                for (var i = 0; i < allInputs.length; i++) {
                    var p = allInputs[i];
                    for (var j = 0; j < 5; j++) {
                        p = p.parentElement;
                        if (!p) break;
                        if ((p.textContent || '').indexOf(marker) >= 0) return allInputs[i];
                    }
                }
                // Second pass: search for "prefix+备注"
                marker = prefix + '备注';
                for (var i = 0; i < allInputs.length; i++) {
                    var p = allInputs[i];
                    for (var j = 0; j < 5; j++) {
                        p = p.parentElement;
                        if (!p) break;
                        if ((p.textContent || '').indexOf(marker) >= 0) return allInputs[i];
                    }
                }
                return null;
            };

            // ---- Compose: overlay -> original page ----
            var _ar3_compose_reason = function(retries, clearOnly) {
                retries = retries || 0;
                var text;
                if (clearOnly) {
                    text = '';
                } else {
                    var severity = reasonBox.getAttribute('data-severity') || '';
                    text = '参考图：' + taA.value + '\\n生成图：' + taB.value + '\\n' + severity;
                }
                var original = _ar3_find_original_input(dim);
                if (original) {
                    // Contenteditable div driven by iView/Vue — focus + innerText +
                    // InputEvent is needed to trigger v-model update (textContent alone
                    // does not fire React/Vue change detection on this element type).
                    original.focus();
                    original.innerText = text;
                    try {
                        original.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText'}));
                    } catch(e) {
                        original.dispatchEvent(new Event('input', {bubbles: true}));
                    }
                    original.dispatchEvent(new Event('blur', {bubbles: true}));
                } else if (retries < 5) {
                    setTimeout(function() { _ar3_compose_reason(retries + 1, clearOnly); }, 100);
                }
            };

            // Parse existing original text (format: "参考图：... | 生成图：... | ...")
            var parsed = {refText: '', genText: '', severity: ''};
            var initOriginal = _ar3_find_original_input(dim);
            if (initOriginal) {
                var raw = initOriginal.textContent || '';
                var rm = raw.match(/参考图[：:][\\s\\S]*?(?=生成图[：:]|$)/);
                if (rm) parsed.refText = rm[0].replace(/^参考图[：:]\\s*/, '').trim();
                var gm = raw.match(/生成图[：:][\\s\\S]*?(?=轻度不一致|中度不一致|重度不一致|$)/);
                if (gm) parsed.genText = gm[0].replace(/^生成图[：:]\\s*/, '').trim();
                var sevs = ['轻度不一致','中度不一致','重度不一致'];
                for (var si = 0; si < sevs.length; si++) {
                    if (raw.indexOf(sevs[si]) >= 0) { parsed.severity = sevs[si]; break; }
                }
            }

            var reasonBox = document.createElement('div');
            reasonBox.className = '__ar3_reason_box';

            // ---- Input A: 参考图 ----
            var fieldRowA = document.createElement('div');
            fieldRowA.style.cssText = 'margin-bottom:6px;';
            var lblA = document.createElement('span');
            lblA.textContent = '参考图：';
            lblA.style.cssText = 'color:#a0a0b0;font-size:12px;margin-right:6px;display:inline-block;width:48px;';
            var taA = document.createElement('textarea');
            taA.className = '__ar3_ref_input';
            taA.value = parsed.refText;
            taA.placeholder = '描述参考图...';
            taA.style.cssText = 'width:100%;min-height:36px;padding:4px 8px;font-size:13px;border:1px solid #2a2a4a;border-radius:4px;background:#1a1a2e;color:#e0e0e0;outline:none;resize:vertical;font-family:inherit;';
            fieldRowA.appendChild(lblA);
            fieldRowA.appendChild(taA);

            // ---- Input B: 生成图 ----
            var fieldRowB = document.createElement('div');
            fieldRowB.style.cssText = 'margin-bottom:8px;';
            var lblB = document.createElement('span');
            lblB.textContent = '生成图：';
            lblB.style.cssText = 'color:#a0a0b0;font-size:12px;margin-right:6px;display:inline-block;width:48px;';
            var taB = document.createElement('textarea');
            taB.className = '__ar3_gen_input';
            taB.value = parsed.genText;
            taB.placeholder = '描述生成图...';
            taB.style.cssText = 'width:100%;min-height:36px;padding:4px 8px;font-size:13px;border:1px solid #2a2a4a;border-radius:4px;background:#1a1a2e;color:#e0e0e0;outline:none;resize:vertical;font-family:inherit;';
            fieldRowB.appendChild(lblB);
            fieldRowB.appendChild(taB);

            // ---- Consolidated 5-button row ----
            var sevRow = document.createElement('div');
            sevRow.style.cssText = 'display:flex;gap:4px;';

            var btnDefs = [
                {label: '一致', severity: '', value: '一致', score: 0},
                {label: '轻度', severity: '轻度不一致', value: '不一致', score: -100},
                {label: '中度', severity: '中度不一致', value: '不一致', score: -301},
                {label: '重度', severity: '重度不一致', value: '不一致', score: -710},
                {label: '不适用', severity: '', value: '不适用', score: 0}
            ];

            // Determine initial active state (read from wrapper class, not input.checked)
            var selectedVal = _ar3_selected_option(dim);

            var activeIdx = -1;
            if (selectedVal === '不一致') {
                if (parsed.severity === '轻度不一致') activeIdx = 1;
                else if (parsed.severity === '重度不一致') activeIdx = 3;
                else activeIdx = 2; // default to 中度
            } else if (selectedVal === '一致') {
                activeIdx = 0;
            } else if (selectedVal === '不适用') {
                activeIdx = 4;
            }
            dim.__ar3_score = (activeIdx >= 0 ? btnDefs[activeIdx].score : 0);

            var dimIdx = -1;
            (function() { var mm = (dim.__ar3_dimPrefix || '').match(/(\\d+)$/); if (mm) dimIdx = parseInt(mm[1], 10); })();

            // Auto score (×100 integer) from severity × a manual fine-tune multiplier.
            // Slider has 5 ticks: ×0.1 / ×0.5 / ×1 / ×2 / ×10 (default middle = ×1).
            // The product is truncated toward zero to stay an integer (×100 scheme).
            // The chosen multiplier is SHARED across all tabs for the same dimension
            // index via _ar3_dim_scale_idx/_ar3_set_dim_scale.
            dim.__ar3_autoScore = dim.__ar3_score;
            var _initScaleIdx = (dimIdx >= 0 && dimIdx <= 4) ? _ar3_dim_scale_idx[dimIdx] : 2;
            dim.__ar3_adjIdx = _initScaleIdx;

            var sliderWrap = document.createElement('div');
            sliderWrap.style.cssText = 'display:flex;align-items:center;gap:6px;flex-shrink:0;';
            var slider = document.createElement('input');
            slider.type = 'range';
            slider.min = '0'; slider.max = '4'; slider.step = '1'; slider.value = String(_initScaleIdx);
            slider.className = '__ar3_dim_slider';
            slider.title = '微调本项评分（×0.1 / ×0.5 / ×1 / ×2 / ×10）· 同维度全标签统一';
            slider.style.cssText = 'width:78px;accent-color:#e94560;cursor:pointer;';
            var adjLabel = document.createElement('span');
            adjLabel.style.cssText = 'font-size:11px;color:#e94560;font-weight:bold;min-width:78px;text-align:right;white-space:nowrap;';

            // Recompute this dim's score from its current slider index (no broadcast).
            var _ar3_apply_adj = function() {
                dim.__ar3_adjIdx = parseInt(slider.value, 10);
                var mult = _ar3_adj_mults[dim.__ar3_adjIdx];
                if (typeof mult !== 'number') mult = 1;
                dim.__ar3_score = Math.trunc(dim.__ar3_autoScore * mult);
                adjLabel.textContent = '×' + mult + '→' + (dim.__ar3_score / 100).toFixed(2);
                _ar3_update_score();
            };
            // User dragged this slider → apply locally then broadcast to same-index dims.
            slider.addEventListener('input', function() {
                _ar3_apply_adj();
                if (dimIdx >= 0 && dimIdx <= 4) _ar3_set_dim_scale(dimIdx, parseInt(slider.value, 10));
            });
            // Another tab changed this dimension's scale → sync our slider + score.
            if (dimIdx >= 0 && dimIdx <= 4) {
                _ar3_dim_scale_listeners[dimIdx].push(function(sliderIdx) {
                    slider.value = String(sliderIdx);
                    _ar3_apply_adj();
                });
            }
            sliderWrap.appendChild(slider);
            sliderWrap.appendChild(adjLabel);
            dimHeader.appendChild(sliderWrap);
            _ar3_apply_adj();

            // Fill taA/taB from the AI comparison result (nested per-dimension object
            // with 参考图/生成图 fields). emptyOnly: keep existing text; skipHidden: only
            // act when the reason box is visible (used by auto-fill on tab switch).
            var _ar3_fill_from_ai = function(emptyOnly, skipHidden) {
                if (skipHidden && reasonBox.style.display === 'none') return false;
                var key = _ar3_ai_order[dimIdx];
                if (!key) return false;
                var cmp = _ar3_get_ai('__ar3_ai_cmp_' + letter);
                var obj = cmp ? cmp[key] : null;
                if (!obj || typeof obj !== 'object') return false;
                var did = false;
                if (obj['参考图'] != null && (!emptyOnly || !taA.value)) { taA.value = obj['参考图']; did = true; }
                if (obj['生成图'] != null && (!emptyOnly || !taB.value)) { taB.value = obj['生成图']; did = true; }
                if (did) dim.__ar3_dirty = true;
                return did;
            };

            var _ar3_set_active = function(idx, noPropagate) {
                // Guard against recursive re-entry from sync observer
                if (dim.__ar3_settingActive) return;
                dim.__ar3_settingActive = true;

                activeIdx = idx;
                var def = btnDefs[idx];
                reasonBox.setAttribute('data-severity', def.severity);
                dim.__ar3_autoScore = def.score;
                // Keep the shared per-dimension scale multiplier (do NOT reset to ×1).
                var _keepIdx = (dimIdx >= 0 && dimIdx <= 4) ? _ar3_dim_scale_idx[dimIdx] : dim.__ar3_adjIdx;
                if (slider) { slider.value = String(_keepIdx); _ar3_apply_adj(); } else { dim.__ar3_score = Math.trunc(def.score * (_ar3_adj_mults[_keepIdx] || 1)); _ar3_update_score(); }

                // Update original checkboxes — search by label prefix
                var allMS = document.querySelectorAll('.multiple-select');
                var curDim = null;
                for (var mi = 0; mi < allMS.length; mi++) {
                    var lbl = allMS[mi].querySelector('.ivu-form-item-label, label');
                    if (lbl && lbl.textContent.trim().indexOf(dim.__ar3_dimPrefix) === 0) {
                        curDim = allMS[mi];
                        break;
                    }
                }
                if (curDim) {
                    _ar3_apply_option(curDim, def.value);
                }

                // Show/hide reason box (hidden for 一致 and 不适用)
                var showReason = (def.value === '不一致');
                reasonBox.style.display = showReason ? 'block' : 'none';

                // Update button styles
                sevBtns.forEach(function(b, i) {
                    var sel = i === idx;
                    b.style.border = '1px solid ' + (sel ? '#e94560' : '#2a2a4a');
                    b.style.background = sel ? '#3a1a2e' : '#1a1a2e';
                    b.style.color = sel ? '#e94560' : '#a0a0b0';
                });

                // Compose: clear for 一致/不适用, write text for 轻度/中度/重度
                // Delay to let iView's async tick create/remove the contenteditable div
                var shouldClear = (def.value === '一致' || def.value === '不适用');
                setTimeout(function() { _ar3_compose_reason(0, shouldClear); }, 300);

                // Propagate 不适用 to the same dimension of every other model (one-key).
                if (def.value === '不适用' && !noPropagate && dimIdx >= 0) {
                    Object.keys(evalByModel).forEach(function(otherL) {
                        if (otherL === letter) return;
                        (evalByModel[otherL] || []).forEach(function(other) {
                            var mm = (other.__ar3_dimPrefix || '').match(/(\\d+)$/);
                            if (mm && parseInt(mm[1], 10) === dimIdx && other.__ar3_reasonInfo && other.__ar3_reasonInfo.setActive) {
                                other.__ar3_reasonInfo.setActive(4, true);
                            }
                        });
                    });
                }

                // Release guard after a tick
                setTimeout(function() { dim.__ar3_settingActive = false; }, 300);
            };

            var sevBtns = [];
            btnDefs.forEach(function(def, i) {
                var btn = document.createElement('button');
                btn.textContent = def.label;
                btn.style.cssText = 'flex:1;padding:5px 4px;font-size:12px;border:1px solid ' + (i === activeIdx ? '#e94560' : '#2a2a4a') + ';border-radius:4px;background:' + (i === activeIdx ? '#3a1a2e' : '#1a1a2e') + ';color:' + (i === activeIdx ? '#e94560' : '#a0a0b0') + ';cursor:pointer;font-family:inherit;';
                btn.addEventListener('click', function() { _ar3_set_active(i); });
                sevRow.appendChild(btn);
                sevBtns.push(btn);
            });
            reasonBox.setAttribute('data-severity', btnDefs[Math.max(0, activeIdx)].severity || '');

            // Layout: the two inputs on the left, a single 确定 button on their right.
            var inputsCol = document.createElement('div');
            inputsCol.style.cssText = 'flex:1;min-width:0;';
            inputsCol.appendChild(fieldRowA);
            inputsCol.appendChild(fieldRowB);

            // ---- 推送 button: push THIS dimension's 参考图 text into the same
            // dimension's EMPTY 参考图 box in every other tab (model). ----
            var pushBtn = document.createElement('button');
            pushBtn.textContent = '推送';
            pushBtn.title = '把本项参考图文本推送到其它标签中为空的对应参考图输入框';
            pushBtn.style.cssText = 'flex-shrink:0;align-self:flex-start;background:#1a1a2e;color:#5c7cfa;border:1px solid #5c7cfa;border-radius:4px;padding:5px 8px;cursor:pointer;font-size:11px;font-weight:bold;font-family:inherit;white-space:nowrap;';
            (function(ltr) {
                pushBtn.onclick = function() {
                    var text = taA.value;
                    if (!text) {
                        pushBtn.textContent = '无内容';
                        setTimeout(function() { pushBtn.textContent = '推送'; }, 1200);
                        return;
                    }
                    var count = 0;
                    Object.keys(evalByModel).forEach(function(otherL) {
                        if (otherL === ltr) return;
                        (evalByModel[otherL] || []).forEach(function(other) {
                            var mm = (other.__ar3_dimPrefix || '').match(/(\\d+)$/);
                            if (mm && parseInt(mm[1], 10) === dimIdx && other.__ar3_reasonInfo) {
                                var ta = other.__ar3_reasonInfo.taA;
                                if (ta && !ta.value) { ta.value = text; other.__ar3_dirty = true; count++; }
                            }
                        });
                    });
                    pushBtn.textContent = '已推送(' + count + ')';
                    setTimeout(function() { pushBtn.textContent = '推送'; }, 1000);
                };
            })(letter);


            var inputsWrap = document.createElement('div');
            inputsWrap.style.cssText = 'display:flex;gap:6px;align-items:stretch;';
            inputsWrap.appendChild(pushBtn);
            inputsWrap.appendChild(inputsCol);

            reasonBox.appendChild(inputsWrap);
            card.appendChild(sevRow);
            card.appendChild(reasonBox);

            // Typing only marks the field dirty; the original page is written
            // ONLY when the tab-level 提交本页 button is clicked (avoids the
            // write->observer->overwrite loop that was interrupting input).
            taA.addEventListener('input', function() { dim.__ar3_dirty = true; if (typeof _ar3_update_progress === 'function') _ar3_update_progress(); });
            taB.addEventListener('input', function() { dim.__ar3_dirty = true; if (typeof _ar3_update_progress === 'function') _ar3_update_progress(); });

            // Initial visibility: show only for 不一致 (一致/不适用 hide the inputs)
            var initShow = (btnDefs[Math.max(0, activeIdx)].value === '不一致');
            reasonBox.style.display = initShow ? 'block' : 'none';

            dim.__ar3_reasonInfo = {box: reasonBox, taA: taA, taB: taB, compose: _ar3_compose_reason, setActive: _ar3_set_active, fillFromAi: _ar3_fill_from_ai, btnDefs: btnDefs, submit: function() { _ar3_compose_reason(0, false); }, getActiveIdx: function() { return activeIdx; }};

            rightSide.appendChild(card);
        });

        panel.appendChild(rightSide);
        tabContent.appendChild(panel);
        tabs[letter] = {btn: tabBtn, panel: panel, refImg: ri, modelImg: mi, updateProgress: _ar3_update_progress, dims: dims};
        _ar3_update_score();
    });

    var _ar3_active_letter = modelLetters.length ? modelLetters[0] : '';
    var _ar3_focus_dim_idx = 0;

    function _ar3_highlight_focus() {
        Object.keys(tabs).forEach(function(l) {
            (tabs[l].dims || []).forEach(function(d) {
                if (d.__ar3_card) d.__ar3_card.style.outline = 'none';
            });
        });
        var dims = tabs[_ar3_active_letter] && tabs[_ar3_active_letter].dims || [];
        if (_ar3_focus_dim_idx < 0) _ar3_focus_dim_idx = 0;
        if (_ar3_focus_dim_idx >= dims.length) _ar3_focus_dim_idx = dims.length - 1;
        var d = dims[_ar3_focus_dim_idx];
        if (d && d.__ar3_card) {
            d.__ar3_card.style.outline = '2px solid #5c7cfa';
            d.__ar3_card.scrollIntoView({block: 'nearest'});
        }
    }

    function _ar3_activate_tab(letter, keepFocus) {
        if (!tabs[letter]) return;
        Object.keys(tabs).forEach(function(l) {
            tabs[l].btn.style.background = 'transparent';
            tabs[l].btn.style.color = '#a0a0b0';
            tabs[l].btn.style.borderBottom = '2px solid transparent';
            tabs[l].panel.style.display = 'none';
        });
        var btn = tabs[letter].btn;
        btn.style.background = '#1a1a2e';
        btn.style.color = '#e94560';
        btn.style.borderBottom = '2px solid #e94560';
        tabs[letter].panel.style.display = 'flex';
        _ar3_active_letter = letter;
        if (!keepFocus) _ar3_focus_dim_idx = 0;

        // Auto-fill this tab's visible inputs from AI results (empty fields only)
        (evalByModel[letter] || []).forEach(function(d) {
            if (d.__ar3_reasonInfo && d.__ar3_reasonInfo.fillFromAi) d.__ar3_reasonInfo.fillFromAi(true, true);
        });
        _ar3_highlight_focus();
    }

    tabHeader.addEventListener('click', function(e) {
        var btn = e.target.closest('button[data-model]');
        if (!btn) return;
        _ar3_activate_tab(btn.getAttribute('data-model'));
    });

    // ---- Keyboard shortcuts (skip while typing in a textarea/contenteditable) ----
    // A~H / ←→ : switch model tab | ↑↓ : move focused dimension |
    // 1~5 : set severity of focused dimension | Ctrl+Enter : 提交本页
    window.addEventListener('keydown', function(e) {
        if (!document.getElementById('__ar3_tab_overlay')) return;
        if (document.getElementById('__ar3_lightbox') &&
            document.getElementById('__ar3_lightbox').style.display !== 'none') return;

        var ae = document.activeElement;
        var typing = ae && (ae.tagName === 'TEXTAREA' || ae.tagName === 'INPUT' || ae.isContentEditable);

        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            var t = tabs[_ar3_active_letter];
            if (t && t.dims) {
                t.dims.forEach(function(d) {
                    if (d.__ar3_reasonInfo && d.__ar3_reasonInfo.submit) { d.__ar3_reasonInfo.submit(); d.__ar3_dirty = false; }
                });
                if (t.updateProgress) t.updateProgress();
            }
            return;
        }

        if (typing) return;

        var order = modelLetters;
        var pos = order.indexOf(_ar3_active_letter);
        var key = e.key;

        if (key === 'ArrowRight') {
            e.preventDefault();
            if (pos < order.length - 1) _ar3_activate_tab(order[pos + 1]);
        } else if (key === 'ArrowLeft') {
            e.preventDefault();
            if (pos > 0) _ar3_activate_tab(order[pos - 1]);
        } else if (key === 'ArrowDown') {
            e.preventDefault();
            _ar3_focus_dim_idx++;
            _ar3_highlight_focus();
        } else if (key === 'ArrowUp') {
            e.preventDefault();
            _ar3_focus_dim_idx--;
            _ar3_highlight_focus();
        } else if (/^[a-hA-H]$/.test(key)) {
            var L = key.toUpperCase();
            if (tabs[L]) { e.preventDefault(); _ar3_activate_tab(L); }
        } else if (/^[1-5]$/.test(key)) {
            e.preventDefault();
            var dims = tabs[_ar3_active_letter] && tabs[_ar3_active_letter].dims || [];
            var d = dims[_ar3_focus_dim_idx];
            if (d && d.__ar3_reasonInfo && d.__ar3_reasonInfo.setActive) {
                d.__ar3_reasonInfo.setActive(parseInt(key, 10) - 1);
            }
        }
    }, true);

    document.body.appendChild(overlay);

    var syncObserver = new MutationObserver(function() {
        if (refItem) {
            var newRefSrc = refItem.querySelector('img.img');
            var srcVal = newRefSrc ? newRefSrc.src : '';
            Object.keys(tabs).forEach(function(l) {
                if (tabs[l].refImg && tabs[l].refImg.src !== srcVal) {
                    tabs[l].refImg.src = srcVal;
                }
            });
        }
        modelItems.forEach(function(item) {
            var m = item.id.match(/model_([A-H])$/);
            if (!m) return;
            var letter = m[1], tab = tabs[letter];
            if (!tab || !tab.modelImg) return;
            var si = item.querySelector('img.img');
            if (si && tab.modelImg.src !== si.src) {
                tab.modelImg.src = si.src;
            }
        });
        // Sync remark inputs from original -> overlay
        Object.keys(evalByModel).forEach(function(letter) {
            (evalByModel[letter] || []).forEach(function(dim) {
                if (!dim.__ar3_reasonInfo) return;
                var ri = dim.__ar3_reasonInfo;
                // Find original CI by text marker "prefix+不一致" or "prefix+备注"
                var prefix = dim.__ar3_dimPrefix || '';
                if (!prefix) return;
                var allInputs = document.querySelectorAll('.customInput.horizontalLtr');
                var origInput = null;
                var marker = prefix + '不一致';
                for (var ai = 0; ai < allInputs.length; ai++) {
                    var p = allInputs[ai];
                    for (var aj = 0; aj < 5; aj++) {
                        p = p.parentElement;
                        if (!p) break;
                        if ((p.textContent || '').indexOf(marker) >= 0) { origInput = allInputs[ai]; break; }
                    }
                    if (origInput) break;
                }
                if (!origInput) {
                    marker = prefix + '备注';
                    for (var ai = 0; ai < allInputs.length; ai++) {
                        var p = allInputs[ai];
                        for (var aj = 0; aj < 5; aj++) {
                            p = p.parentElement;
                            if (!p) break;
                            if ((p.textContent || '').indexOf(marker) >= 0) { origInput = allInputs[ai]; break; }
                        }
                        if (origInput) break;
                    }
                }
                if (!origInput) return;

                // Skip sync for dimensions the user is currently editing —
                // otherwise each write-then-observer cycle clobbers the textareas.
                if (dim.__ar3_dirty || (document.activeElement === ri.taA || document.activeElement === ri.taB)) return;

                // Find corresponding MS to read checkbox state (by label text)
                var allMS = document.querySelectorAll('.multiple-select');
                var freshDim = null;
                for (var mi = 0; mi < allMS.length; mi++) {
                    var lbl = allMS[mi].querySelector('.ivu-form-item-label, label');
                    if (lbl && lbl.textContent.trim().indexOf(prefix) === 0) {
                        freshDim = allMS[mi];
                        break;
                    }
                }

                var raw = origInput.textContent || '';
                if (raw === ri._lastSyncedRaw) return;
                ri._lastSyncedRaw = raw;
                var rm = raw.match(/参考图[：:][\\s\\S]*?(?=生成图[：:]|$)/);
                ri.taA.value = rm ? rm[0].replace(/^参考图[：:]\\s*/, '').trim() : '';
                var gm = raw.match(/生成图[：:][\\s\\S]*?(?=轻度不一致|中度不一致|重度不一致|$)/);
                ri.taB.value = gm ? gm[0].replace(/^生成图[：:]\\s*/, '').trim() : '';
                var sevs = ['轻度不一致','中度不一致','重度不一致'];
                var foundSev = '';
                for (var si = 0; si < sevs.length; si++) {
                    if (raw.indexOf(sevs[si]) >= 0) { foundSev = sevs[si]; break; }
                }
                // Map severity to button index (0=一致,1=轻度,2=中度,3=重度,4=不适用)
                // Use FRESH DOM query (dim may have been replaced by Vue re-render)
                var sevIdx = -1;
                if (freshDim) {
                    var cbVal = _ar3_selected_option(freshDim);
                    if (cbVal === '一致') {
                        sevIdx = 0;
                    } else if (cbVal === '不一致') {
                        if (foundSev === '轻度不一致') sevIdx = 1;
                        else if (foundSev === '重度不一致') sevIdx = 3;
                        else sevIdx = 2;
                    } else if (cbVal === '不适用') {
                        sevIdx = 4;
                    }
                }
                if (sevIdx < 0) return; // Can't determine state, skip
                if (ri.setActive && sevIdx !== ri._activeIdx) {
                    ri._activeIdx = sevIdx;
                    ri.setActive(sevIdx, true);
                }
            });
        });
    });
    syncObserver.observe(document.body, {subtree: true, attributes: true, characterData: true, attributeFilter: ['src']});

    window.__ar3_tabs = tabs;
    window.__ar3_model_items = modelItems;
    window.__ar3_ref_item = refItem;
    window.__ar3_rank_list = rankListRow;

    if (_ar3_active_letter) _ar3_highlight_focus();

    return JSON.stringify({status: 'transformed', count: modelLetters.length, models: modelLetters});
})();
"""
REMOVE_TABBED_LAYOUT = """
(function() {
    var overlay = document.getElementById('__ar3_tab_overlay');
    if (overlay) {
        overlay.parentNode.removeChild(overlay);
        var lb = document.getElementById('__ar3_lightbox');
        if (lb && lb.parentNode) lb.parentNode.removeChild(lb);
        window.__ar3_tabs = null;
        window.__ar3_model_items = null;
        window.__ar3_ref_item = null;
        window.__ar3_rank_list = null;
        return 'removed';
    }
    return 'not_found';
})();
"""

SYNC_OVERLAY_IMAGES = """
(function() {
    if (!window.__ar3_model_items || !window.__ar3_tabs) return 'no_overlay';

    var updates = 0;
    window.__ar3_model_items.forEach(function(item) {
        var match = item.id.match(/model_([A-H])$/);
        if (!match) return;
        var letter = match[1];
        var panel = window.__ar3_tabs[letter] && window.__ar3_tabs[letter].panel;
        if (!panel) return;

        var modelImg = item.querySelector('img.img');
        var overlayImgs = panel.querySelectorAll('img');
        var found = false;
        overlayImgs.forEach(function(oi) {
            if (oi.src === modelImg.src) return;
            if (oi.dataset.sync === 'model_' + letter) {
                oi.src = modelImg.src;
                updates++;
                found = true;
            }
        });
    });

    return JSON.stringify({updates: updates});
})();
"""

EVALUATION_STATE_TO_PYTHON = """
(function() {
    var states = [];
    var evalGroups = document.querySelectorAll('.multiple-select');
    evalGroups.forEach(function(el) {
        var labelEl = el.querySelector('.ivu-form-item-label, label');
        if (!labelEl) return;
        var labelText = labelEl.textContent.trim();
        if (!labelText) return;

        var checked = [];
        el.querySelectorAll('.checkboxItem').forEach(function(item) {
            if ((item.className || '').indexOf('ivu-checkbox-wrapper-checked') < 0) return;
            var cb = item.querySelector('input[type="checkbox"]');
            checked.push(cb && cb.value ? cb.value : (item.textContent || '').trim());
        });

        states.push({
            label: labelText,
            checked: checked
        });
    });
    return JSON.stringify(states);
})();
"""

SCAN_PAGE_FOR_TEXT = """
(function() {
    var target = '__TARGET__';
    if (!target) return JSON.stringify({target: '', matches: [], total: 0});

    var results = [];
    var allElements = document.querySelectorAll('*');

    allElements.forEach(function(el) {
        // Skip script, style, svg internals
        var tag = el.tagName.toLowerCase();
        if (tag === 'script' || tag === 'style' || tag === 'svg' || tag === 'path') return;

        var foundIn = [];

        // Check text content (only direct text nodes)
        if (el.textContent && el.textContent.indexOf(target) >= 0) {
            foundIn.push('textContent');
        }

        // Check value (inputs, textareas)
        if ((tag === 'input' || tag === 'textarea') && el.value && el.value.indexOf(target) >= 0) {
            foundIn.push('value');
        }

        // Check placeholder
        if (el.placeholder && el.placeholder.indexOf(target) >= 0) {
            foundIn.push('placeholder');
        }

        if (foundIn.length === 0) return;

        // Build ancestor chain (up to 5 levels)
        var chain = [];
        var p = el.parentElement;
        for (var i = 0; i < 5 && p; i++) {
            var ptag = p.tagName.toLowerCase();
            var pcls = p.className && typeof p.className === 'string'
                ? p.className.replace(/\\s+/g, ' ').trim().substring(0, 60)
                : '';
            var pid = p.id || '';
            chain.push({tag: ptag, cls: pcls, id: pid});
            p = p.parentElement;
        }

        results.push({
            tag: tag,
            id: el.id || '',
            classList: el.className && typeof el.className === 'string'
                ? el.className.replace(/\\s+/g, ' ').trim()
                : '',
            foundIn: foundIn.join(', '),
            text: (el.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 200),
            value: (tag === 'input' || tag === 'textarea') ? (el.value || '') : '',
            parentChain: chain
        });
    });

    return JSON.stringify({target: target, matches: results, total: results.length});
})();
"""

DRAIN_AI_QUEUE = """
(function() {
    var q = window.__ar3_ai_queue || [];
    if (q.length === 0) return '[]';
    var items = [];
    while (q.length > 0) {
        var r = q.shift();
        items.push(JSON.stringify(r));
    }
    return '[' + items.join(',') + ']';
})();
"""

CAPTURE_RANK_STRUCTURE = """
(function() {
    function norm(s) { return (s || '').replace(/\\s+/g, '').trim(); }
    var out = {rank_group_count: 0, groups: []};
    var groups = document.querySelectorAll('.rank');
    out.rank_group_count = groups.length;
    for (var g = 0; g < groups.length; g++) {
        var rank = groups[g];
        var info = {group_index: g, class: rank.className, child_count: rank.children.length, contents: []};
        for (var i = 0; i < rank.children.length; i++) {
            var rc = rank.children[i];
            var title = rc.querySelector('.rank-title');
            var items = rc.querySelectorAll('.rank-list-item');
            var itemTexts = [];
            for (var k = 0; k < items.length; k++) {
                itemTexts.push(norm(items[k].textContent).replace(/[^\\u4e00-\\u9fa5A-H0-9]/g, ''));
            }
            info.contents.push({
                idx: i,
                tag: rc.tagName.toLowerCase(),
                class: rc.className,
                title: title ? norm(title.textContent) : null,
                item_count: items.length,
                items: itemTexts
            });
        }
        out.groups.push(info);
    }
    // Vue hooks that might expose the underlying draggable model
    var probe = document.querySelector('.rank-list-item');
    if (probe) {
        var p = probe;
        var found = [];
        for (var d = 0; d < 6 && p; d++) {
            found.push({
                depth: d,
                tag: p.tagName ? p.tagName.toLowerCase() : '?',
                class: (typeof p.className === 'string') ? p.className : '',
                has__vue__: !!p.__vue__,
                has__vueParentComponent: !!p.__vueParentComponent,
                has__vnode: !!p.__vnode
            });
            p = p.parentElement;
        }
        out.vue_probe = found;
    }

    // Deep dump of the Vue 2 component driving the draggable buckets (read-only).
    function _summ(v) {
        try {
            if (v === null || v === undefined) return v;
            var t = typeof v;
            if (t !== 'object') return (t === 'function') ? '<fn>' : v;
            if (Array.isArray(v)) {
                return {__array_len: v.length, sample: v.slice(0, 8).map(function(x) {
                    if (x && typeof x === 'object') return {__keys: Object.keys(x).slice(0, 12), name: x.name || x.label || x.title || x.model || x.text};
                    return x;
                })};
            }
            return {__keys: Object.keys(v).slice(0, 25)};
        } catch (e) { return '<err>'; }
    }
    try {
        var rgs = document.querySelectorAll('.rank');
        if (rgs.length >= 2) {
            var lastRank = rgs[rgs.length - 1];
            var bucket0 = lastRank.children[0];
            var vm = bucket0 && bucket0.__vue__;
            if (vm) {
                var vmInfo = {
                    tag: vm.$options && vm.$options._componentTag,
                    dataKeys: vm.$data ? Object.keys(vm.$data) : [],
                    propKeys: vm.$options && vm.$options.propsData ? Object.keys(vm.$options.propsData) : [],
                    list: _summ(vm.list),
                    value: _summ(vm.value),
                    modelValue: _summ(vm.modelValue)
                };
                // walk up parents looking for an array-of-arrays (the 8 buckets model)
                var chain = [];
                var cur = vm;
                for (var up = 0; up < 5 && cur; up++) {
                    var dk = cur.$data ? Object.keys(cur.$data) : [];
                    var arrs = {};
                    dk.forEach(function(k) {
                        var val = cur.$data[k];
                        if (Array.isArray(val)) arrs[k] = _summ(val);
                    });
                    chain.push({depth: up, tag: cur.$options && cur.$options._componentTag, dataKeys: dk, arrays: arrs});
                    cur = cur.$parent;
                }
                vmInfo.parent_chain = chain;
                out.vue_model = vmInfo;
            } else {
                out.vue_model = {note: 'bucket0.__vue__ not found'};
            }
        }
    } catch (e) { out.vue_model = {error: String(e)}; }
    return JSON.stringify(out, null, 2);
})();
"""
