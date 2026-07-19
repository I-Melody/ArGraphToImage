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
    if (window.__ar3_sync_observer_active) {
        window.__annotation_monitor_active = true;
        return 'delegated_to_sync_observer';
    }
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

    var _sev_cfg = ((window.__ar3_word_config || {}).severity) || {"轻度":["轻度不一致"],"中度":["中度不一致"],"重度":["重度不一致"]};
    var _sev_keys = Object.keys(_sev_cfg);
    var _sev_all = [];
    _sev_keys.forEach(function(k) { _sev_all = _sev_all.concat(_sev_cfg[k]); });
    var _sev_to_key = function(kw) {
        for (var i = 0; i < _sev_keys.length; i++) {
            if (_sev_cfg[_sev_keys[i]].indexOf(kw) >= 0) return _sev_keys[i];
        }
        return '';
    };
    var _sev_first = function(key) { return (_sev_cfg[key] || [])[0] || ''; };

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
    var _ar3_dim_scale_idx = (window.__ar3_saved_dim_scale_idx && window.__ar3_saved_dim_scale_idx.length === 5)
        ? window.__ar3_saved_dim_scale_idx.slice() : [2, 2, 2, 2, 2];
    var _ar3_dim_scale_listeners = [[], [], [], [], []];
    var _ar3_broadcasting_scale = false;
    var _ar3_set_dim_scale = function(dimIdx, sliderIdx) {
        if (dimIdx < 0 || dimIdx > 4) return;
        _ar3_dim_scale_idx[dimIdx] = sliderIdx;
        var _saveMode = (window.__ar3_slider_cfg || {}).mode || 'multi';
        if (_saveMode === 'multi') {
            window.__ar3_saved_dim_scale_idx = _ar3_dim_scale_idx.slice();
        }
        if (_ar3_broadcasting_scale) return;
        _ar3_broadcasting_scale = true;
        _ar3_dim_scale_listeners[dimIdx].forEach(function(fn) { fn(sliderIdx); });
        _ar3_broadcasting_scale = false;
    };

    // Image popups — pushed to a Python-polled queue (__ar3_popup_queue) rather than
    // calling window.open directly, so that regular link clicks (target="_blank") stay
    // in the same window (QWebEnginePage.createWindow returns self).
    window.__ar3_img_popups = window.__ar3_img_popups || {};
    function showImagePopup(key, src) {
        if (!src) return;
        window.__ar3_popup_queue = window.__ar3_popup_queue || [];
        window.__ar3_popup_queue.push(JSON.stringify({key: key, src: src}));
    }

    // ---- AI describe: single global button describes the reference image only.
    // Python drains window.__ar3_ai_queue and calls window.__ar3_ai_render(id, jsonStr).
    // Result is cached in window.__ar3_last_ai under '__ar3_ai_desc' and shown
    // in a fixed bar below the topBar — does NOT change with tab switching.
    window.__ar3_ai_queue = window.__ar3_ai_queue || [];
    if (typeof window.__ar3_last_ai !== 'object' || !window.__ar3_last_ai) window.__ar3_last_ai = {};
    var _ar3_task_sig = (function() { var im = refItem && refItem.querySelector('img.img'); return im ? im.src : ''; })();
    if (window.__ar3_ai_task_sig !== _ar3_task_sig) {
        window.__ar3_last_ai = {};
        window.__ar3_ai_task_sig = _ar3_task_sig;
    }
    var _ar3_ai_order = ['整体身份','整体形状与局部结构','颜色与材质','图案装饰logo商标','文字信息'];

    var _ar3_grab_img = function(img) {
        if (!img || !img.src) return null;
        try {
            var MAX = 2048;
            var nw = img.naturalWidth || img.width;
            var nh = img.naturalHeight || img.height;
            if (nw > MAX || nh > MAX) {
                var ratio = Math.min(MAX / nw, MAX / nh);
                nw = Math.round(nw * ratio);
                nh = Math.round(nh * ratio);
            }
            var c = document.createElement('canvas');
            c.width = nw;
            c.height = nh;
            c.getContext('2d').drawImage(img, 0, 0, nw, nh);
            return c.toDataURL('image/jpeg', 0.75);
        } catch (e) { return img.src; }
    };

    function _ar3_render_into(out, jsonStr) {
        var s = (typeof jsonStr === 'string') ? jsonStr : '';
        // Defensive strip: remove markdown fence markers if Python _extract_json failed.
        s = s.replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '');
        var res;
        try { res = JSON.parse(s); } catch (e) { res = {error: '返回解析失败'}; }
        if (res && res.error) { out.textContent = 'AI失败：' + res.error; out.style.color = '#e94560'; return; }
        out.style.color = '#a0a0b0';
        var html = '';
        _ar3_ai_order.forEach(function(k) {
            var v = res[k];
            if (v == null) return;
            if (typeof v === 'object') {
                html += '<div style="margin-bottom:6px;"><b style="color:#5c7cfa;">' + k + '</b>';
                if (v['描述'] != null) html += '<div>' + String(v['描述']) + '</div>';
                html += '</div>';
            } else {
                html += '<div style="margin-bottom:4px;"><b style="color:#5c7cfa;">' + k + '：</b>' + String(v) + '</div>';
            }
        });
        out.innerHTML = html || ('<pre style="white-space:pre-wrap;margin:0;">' + (res.raw || JSON.stringify(res)) + '</pre>');
    }

    window.__ar3_ai_render = function(id, jsonStr) {
        window.__ar3_last_ai[id] = jsonStr;
        var outs = document.querySelectorAll('.__ar3_ai_desc_out');
        for (var oi = 0; oi < outs.length; oi++) {
            _ar3_render_into(outs[oi], jsonStr);
        }
        var btns = document.querySelectorAll('.__ar3_ai_desc_btn');
        for (var bi = 0; bi < btns.length; bi++) {
            btns[bi].disabled = false;
            btns[bi].style.opacity = '1';
        }
        var pushBtns = document.querySelectorAll('.__ar3_ai_push_btn');
        for (var pi = 0; pi < pushBtns.length; pi++) {
            pushBtns[pi].disabled = false;
            pushBtns[pi].style.opacity = '1';
            pushBtns[pi].style.background = '#0f3460';
            pushBtns[pi].style.color = '#e0e0e0';
            pushBtns[pi].style.border = '1px solid #5c7cfa';
        }
    };

    function _ar3_make_ai_desc_section(getRefImg) {
        var AI_DESC_ID = '__ar3_ai_desc';
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:flex-start;gap:8px;margin-top:6px;';

        var btnWrap = document.createElement('div');
        btnWrap.style.cssText = 'flex-shrink:0;display:flex;flex-direction:column;align-items:center;gap:3px;';

        var modelLabel = document.createElement('span');
        modelLabel.style.cssText = 'font-size:10px;color:#5c7cfa;white-space:nowrap;';
        modelLabel.textContent = (window.__ar3_ai_model || 'glm-4.6v');
        btnWrap.appendChild(modelLabel);

        var btn = document.createElement('button');
        btn.className = '__ar3_ai_desc_btn';
        btn.textContent = 'AI描述';
        btn.title = '上传参考图，用AI描述参考图主体的各维度特征';
        btn.style.cssText = 'flex-shrink:0;background:#0f3460;color:#e0e0e0;border:1px solid #5c7cfa;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:13px;font-weight:bold;font-family:inherit;';
        btnWrap.appendChild(btn);

        var pushBtn = document.createElement('button');
        pushBtn.className = '__ar3_ai_push_btn';
        pushBtn.textContent = '推送AI';
        pushBtn.title = '将AI描述内容推入所有模型各维度的参考图备注栏（已有内容不影响）';
        pushBtn.disabled = true;
        pushBtn.style.cssText = 'flex-shrink:0;background:#1a1a2e;color:#808090;border:1px solid #2a2a4a;border-radius:4px;padding:5px 12px;cursor:pointer;font-size:12px;font-family:inherit;opacity:0.5;';
        pushBtn.onclick = function() {
            var result = window.__ar3_last_ai[AI_DESC_ID];
            if (!result) return;
            var data;
            try { data = JSON.parse(result); } catch (e) { return; }
            if (!data || data.error) return;
            var count = 0;
            Object.keys(evalByModel).forEach(function(letter) {
                (evalByModel[letter] || []).forEach(function(dim) {
                    if (!dim.__ar3_reasonInfo) return;
                    var ri = dim.__ar3_reasonInfo;
                    var dimIdx = parseInt((dim.__ar3_dimPrefix || '').split('-A')[1], 10);
                    if (isNaN(dimIdx) || dimIdx < 0 || dimIdx >= _ar3_ai_order.length) return;
                    var key = _ar3_ai_order[dimIdx];
                    var obj = data[key];
                    if (!obj || typeof obj !== 'object') return;
                    var desc = obj['描述'];
                    if (!desc || (ri.taA.value && ri.taA.value.trim())) return;
                    ri.taA.value = desc;
                    if (typeof _ar3_mark_dim_dirty === 'function') _ar3_mark_dim_dirty(dim);
                    count++;
                });
            });
            pushBtn.textContent = '推送AI ✓(' + count + ')';
            pushBtn.style.background = '#0e7a3a';
            pushBtn.style.color = '#e0e0e0';
            setTimeout(function() {
                pushBtn.textContent = '推送AI';
                pushBtn.style.background = '#0f3460';
                pushBtn.style.color = '#e0e0e0';
                pushBtn.style.border = '1px solid #5c7cfa';
            }, 2000);
        };
        btnWrap.appendChild(pushBtn);

        var out = document.createElement('div');
        out.className = '__ar3_ai_desc_out';
        out.style.cssText = 'flex:1;min-width:0;font-size:12px;color:#a0a0b0;white-space:pre-wrap;word-break:break-word;max-height:180px;overflow-y:auto;line-height:1.5;';

        if (window.__ar3_last_ai[AI_DESC_ID]) {
            _ar3_render_into(out, window.__ar3_last_ai[AI_DESC_ID]);
            pushBtn.disabled = false;
            pushBtn.style.opacity = '1';
            pushBtn.style.background = '#0f3460';
            pushBtn.style.color = '#e0e0e0';
            pushBtn.style.border = '1px solid #5c7cfa';
        }

        btn.onclick = function() {
            var refImg = getRefImg();
            var refRef = _ar3_grab_img(refImg);
            if (!refRef) { out.textContent = '缺少参考图'; return; }
            var allOuts = document.querySelectorAll('.__ar3_ai_desc_out');
            var allBtns = document.querySelectorAll('.__ar3_ai_desc_btn');
            var allPushBtns = document.querySelectorAll('.__ar3_ai_push_btn');
            for (var i = 0; i < allOuts.length; i++) {
                allOuts[i].style.color = '#a0a0b0';
                allOuts[i].textContent = 'AI描述中...';
            }
            for (var j = 0; j < allBtns.length; j++) {
                allBtns[j].disabled = true;
                allBtns[j].style.opacity = '0.6';
            }
            for (var k = 0; k < allPushBtns.length; k++) {
                allPushBtns[k].disabled = true;
                allPushBtns[k].style.opacity = '0.5';
                allPushBtns[k].textContent = '推送AI';
                allPushBtns[k].style.background = '#1a1a2e';
                allPushBtns[k].style.color = '#808090';
                allPushBtns[k].style.border = '1px solid #2a2a4a';
            }
            var queueItem = {id: AI_DESC_ID, ref: refRef};
            if (_ar3_preserve_text) queueItem.desc = _ar3_preserve_text;
            window.__ar3_ai_queue.push(queueItem);
        };

        wrap.appendChild(btnWrap);
        wrap.appendChild(out);
        return wrap;
    }

    var overlay = document.createElement('div');
    overlay.id = '__ar3_tab_overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;background:#1a1a2e;display:flex;flex-direction:column;font-family:"Microsoft YaHei",sans-serif;';

    var topBar = document.createElement('div');
    topBar.style.cssText = 'display:flex;align-items:stretch;background:#16213e;border-bottom:2px solid #2a2a4a;padding:2px 8px;flex-shrink:0;';
    var tabHeader = document.createElement('div');
    tabHeader.id = '__ar3_tab_header';
    tabHeader.style.cssText = 'display:flex;flex:1;gap:4px;';
    topBar.appendChild(tabHeader);
    var popupCloseBtn = document.createElement('button');
    popupCloseBtn.textContent = '关弹窗';
    popupCloseBtn.title = '关闭所有已打开的图片弹窗';
    popupCloseBtn.style.cssText = 'flex-shrink:0;align-self:center;margin-left:8px;background:#1a1a2e;color:#a0a0b0;border:1px solid #2a2a4a;border-radius:4px;padding:5px 12px;cursor:pointer;font-size:12px;font-family:inherit;';
    popupCloseBtn.onclick = function() {
        window.__ar3_popup_queue = window.__ar3_popup_queue || [];
        window.__ar3_popup_queue.push(JSON.stringify({key: '__close_all__', src: ''}));
    };
    topBar.appendChild(popupCloseBtn);
    var closeBtn = document.createElement('button');
    closeBtn.textContent = '返回原页面';
    closeBtn.style.cssText = 'flex-shrink:0;align-self:center;margin-left:8px;background:#e94560;color:#fff;border:none;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:12px;font-weight:bold;';
    closeBtn.onclick = function() { if (typeof window.__ar3_submit_all === 'function') window.__ar3_submit_all(); document.body.removeChild(overlay); window.__ar3_tabs = null; window.__ar3_overlay_just_closed = true; };
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
    var rankListRow = document.createElement('div');
    rankListRow.id = '__ar3_rank_list';
    rankListRow.style.cssText = 'display:flex;gap:4px;';
    var ranks = rankListItems.length ? rankListItems : ['模型A','模型B','模型C','模型D','模型E','模型F','模型G','模型H'];
    ranks.forEach(function(name, ri) {
        var color = rankColors[ri] || '#333';
        var slot = document.createElement('div');
        slot.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;background:#1a1a2e;border-radius:4px;padding:6px 4px;font-size:12px;color:#e0e0e0;border-bottom:3px solid ' + color + ';cursor:pointer;';
        var letter = (name.match(/模型([A-H])/) || [])[1] || '';
        slot.innerHTML = '<span style="font-weight:bold;color:' + color + ';">RANK ' + (ri + 1) + '</span>' +
            '<span class="__ar3_rank_model">模型' + letter + '</span>' +
            '<span class="__ar3_rank_chars" style="font-size:11px;opacity:0.8;">' + _ar3_model_chars(letter) + '</span>';
        slot.setAttribute('data-rank-model', letter);
        slot.addEventListener('click', function(e) {
            var l = (e.currentTarget.getAttribute('data-rank-model') || '').toUpperCase();
            if (l && tabs[l]) _ar3_activate_tab(l);
        });
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

    // Count dimensions marked 不一致 (轻度/中度/重度 → btnDefs value '不一致') for a model.
    var _ar3_incons_count = function(L) {
        var dims = evalByModel[L] || [];
        var c = 0;
        dims.forEach(function(d) {
            var ri = d.__ar3_reasonInfo;
            if (!ri || !ri.getActiveIdx) return;
            var idx = ri.getActiveIdx();
            var def = idx >= 0 ? ri.btnDefs[idx] : null;
            if (def && def.value === '不一致') c++;
        });
        return c;
    };

    var _ar3_do_sort = function() {
        if (typeof window.__ar3_submit_all === 'function') window.__ar3_submit_all();
        var scheme = window.__ar3_sort_scheme || 'score';
        var scored = modelLetters.map(function(L) {
            return {
                letter: L,
                score: (typeof modelScores[L] === 'number' ? modelScores[L] : 0),
                incons: _ar3_incons_count(L)
            };
        });
        if (scheme === 'inconsistency') {
            // Fewer 不一致 ranks higher; ties broken by higher score.
            scored.sort(function(a, b) {
                if (a.incons !== b.incons) return a.incons - b.incons;
                return b.score - a.score;
            });
        } else {
            scored.sort(function(a, b) { return b.score - a.score; });
        }
        // Dense ranking (1,1,2,3...) — matches how the original page numbers ties.
        var _ar3_same = function(a, b) {
            return (scheme === 'inconsistency')
                ? (a.incons === b.incons && a.score === b.score)
                : (a.score === b.score);
        };
        var rankCounter = 0;
        scored.forEach(function(s, i) {
            if (i === 0 || !_ar3_same(s, scored[i - 1])) rankCounter++;
            s.rank = rankCounter;
        });
        rankListRow.innerHTML = '';
        scored.forEach(function(s) {
            var color = rankColors[s.rank - 1] || '#333';
            var detail = (scheme === 'inconsistency')
                ? ('不一致' + s.incons + ' · ' + (s.score / 100).toFixed(2) + '分')
                : ((s.score / 100).toFixed(2) + '分');
            var slot = document.createElement('div');
            slot.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;background:#1a1a2e;border-radius:4px;padding:5px 4px;font-size:12px;color:#e0e0e0;border-bottom:3px solid ' + color + ';cursor:pointer;';
            slot.innerHTML = '<span style="font-weight:bold;color:' + color + ';">RANK ' + s.rank + '</span>' +
                '<span class="__ar3_rank_model">模型' + s.letter + '</span>' +
                '<span class="__ar3_rank_chars" style="font-size:11px;opacity:0.8;">' + _ar3_model_chars(s.letter) + '</span>' +
                '<span style="opacity:0.7;font-size:11px;">' + detail + '</span>';
            slot.setAttribute('data-rank-model', s.letter);
            slot.addEventListener('click', function(e) {
                var l = (e.currentTarget.getAttribute('data-rank-model') || '').toUpperCase();
                if (l && tabs[l]) _ar3_activate_tab(l);
            });
            rankListRow.appendChild(slot);
        });
        _ar3_apply_rank_to_original(scored);
        _ar3_refresh_rank_highlight();
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

    var _ar3_preserve_text = '';
    try {
        var pdContainer = document.getElementById('engine0_default_item_preserve_description');
        if (pdContainer) {
            var tc = pdContainer.querySelector('.text-content');
            if (tc) _ar3_preserve_text = (tc.textContent || '').trim();
        }
    } catch (e) {}

    window.__ar3_dirty_models = new Set();
    var _ar3_mark_dim_dirty = function(d) {
        d.__ar3_dirty = true;
        var prefix = d.__ar3_dimPrefix || '';
        var m = prefix.match(/^([A-H])-/);
        if (m) window.__ar3_dirty_models.add(m[1]);
    };

    modelLetters.forEach(function(letter, idx) {
        var tabBtn = document.createElement('div');
        tabBtn.id = '__ar3_tab_btn_' + letter;
        tabBtn.setAttribute('data-model', letter);
        var _active_bg = '#e0a030', _active_text = '#1a1a2e';
        tabBtn.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;background:' + (idx === 0 ? _active_bg : 'transparent') + ';border:3px solid ' + (idx === 0 ? _active_bg : 'transparent') + ';padding:6px 8px;cursor:pointer;min-width:0;';
        var tabLabel = document.createElement('span');
        tabLabel.textContent = letter;
        tabLabel.style.cssText = 'font-size:14px;font-weight:bold;color:' + (idx === 0 ? _active_text : '#e0a030') + ';line-height:1.2;';
        tabBtn.appendChild(tabLabel);
        var tabSlots = document.createElement('span');
        tabSlots.className = '__ar3_tab_slots';
        tabSlots.textContent = '[ , , , , ]';
        tabSlots.style.cssText = 'font-size:12px;font-weight:bold;color:' + (idx === 0 ? _active_text : '#e0a030') + ';line-height:1.2;white-space:nowrap;';
        tabBtn.appendChild(tabSlots);
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
            ri.onclick = function(e) { e.stopPropagation(); showImagePopup('ref_image', ri.src); };
            refBox.appendChild(ri);
        }
        refCol.appendChild(refBox);

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
            mi.onclick = (function(ltr) { return function(e) { e.stopPropagation(); showImagePopup('model_' + ltr, mi.src); }; })(letter);
            modelBox.appendChild(mi);
        }
        modelCol.appendChild(modelBox);
        modelCol.appendChild(_ar3_make_ai_desc_section(function() {
            return refItem ? refItem.querySelector('img.img') : null;
        }));
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
        submitBtn.textContent = '提交全部';
        submitBtn.title = '将所有已编辑标签的修改一次性填入原页面 (Ctrl+Enter)';
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
            dims.forEach(function(d) {
                var isDone = _ar3_dim_done(d);
                if (isDone) done++;
                if (d.__ar3_card) {
                    d.__ar3_card.style.borderRight = isDone ? 'none' : '3px solid #e0a030';
                }
            });
            var total = dims.length;
            progressLabel.textContent = '已填 ' + done + '/' + total;
            progressLabel.style.color = (done === total && total > 0) ? '#0e9a4a' : '#e0a030';
            if (tabs[letter]) {
                tabs[letter].incomplete = (total > 0 && done < total);
                if (tabs[letter].btn) {
                    var b = tabs[letter].btn;
                    var mark = (total > 0 && done === total) ? ' ✓' : ' (' + done + '/' + total + ')';
                    var lbl = b.querySelector('span');
                    if (lbl) lbl.textContent = letter + mark;
                }
                if (typeof _ar3_restyle_tab === 'function') _ar3_restyle_tab(letter);
            }
            if (typeof _ar3_refresh_rank_highlight === 'function') _ar3_refresh_rank_highlight();
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
            if (typeof window.__ar3_submit_all === 'function') window.__ar3_submit_all();
            var totalDone = 0, totalAll = 0;
            Object.keys(tabs).forEach(function(l) {
                var st = (tabs[l].updateProgress && tabs[l].updateProgress()) || {done: 0, total: 5};
                totalDone += st.done;
                totalAll += st.total;
            });
            if (totalDone < totalAll) {
                submitBtn.textContent = '已提交(缺' + (totalAll - totalDone) + ')';
                submitBtn.style.background = '#7a5a0e';
            } else {
                submitBtn.textContent = '已提交';
                submitBtn.style.background = '#0e7a3a';
            }
            setTimeout(function() { submitBtn.textContent = '提交全部'; submitBtn.style.background = '#0f3460'; }, 1200);
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
                    var prevFocus = document.activeElement;
                    var imeActive = dim.__ar3_composing;
                    var inCooldown = dim.__ar3_compose_cool && Date.now() < dim.__ar3_compose_cool;
                    var anyImeActive = window.__ar3_ime_until && Date.now() < window.__ar3_ime_until;
                    if (imeActive || inCooldown || anyImeActive) {
                        if (retries < 30) { setTimeout(function() { _ar3_compose_reason(retries + 1, clearOnly); }, 100); }
                        return;
                    }
                    original.focus();
                    original.innerText = text;
                    try {
                        original.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText'}));
                    } catch(e) {
                        original.dispatchEvent(new Event('input', {bubbles: true}));
                    }
                    original.dispatchEvent(new Event('blur', {bubbles: true}));
                    if (prevFocus && prevFocus !== original && prevFocus !== document.body) {
                        try { prevFocus.focus(); } catch(e) {}
                    }
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
                var _gmRe = new RegExp('生成图[：:][\\\\s\\\\S]*?(?=' + _sev_all.join('|') + '|$)');
                var gm = raw.match(_gmRe);
                if (gm) parsed.genText = gm[0].replace(/^生成图[：:]\\s*/, '').trim();
                for (var si = 0; si < _sev_all.length; si++) {
                    if (raw.indexOf(_sev_all[si]) >= 0) { parsed.severity = _sev_all[si]; break; }
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

            var _ar3_a2_panel = null;
            var _ar3_a2_depth_slider = null;
            var _ar3_a2_vivid_slider = null;
            var _ar3_a2_light_slider = null;
            var _ar3_a2_warmth_slider = null;
            var _ar3_a2_color_input = null;
            var _ar3_a2_extra_input = null;
            var _ar3_a2_compose = function() {
                if (dimIdx !== 2 || !_ar3_a2_panel) return;
                var _depth = parseInt(_ar3_a2_depth_slider.value, 10);
                var _vivid = parseInt(_ar3_a2_vivid_slider.value, 10);
                var _light = parseInt(_ar3_a2_light_slider.value, 10);
                var _warmth = parseInt(_ar3_a2_warmth_slider.value, 10);
                var _color = (_ar3_a2_color_input.value || '').trim();
                var _extra = (_ar3_a2_extra_input.value || '').trim();
                var _activeIdx = (dim.__ar3_reasonInfo && dim.__ar3_reasonInfo.getActiveIdx) ? dim.__ar3_reasonInfo.getActiveIdx() : -1;
                if (_activeIdx < 1 || _activeIdx > 3) return;
                var _sev = _activeIdx;
                var _texts = [];
                var _deep = {
                    dark: {1:'整体颜色较深',2:'整体颜色深',3:'整体颜色很深'},
                    light:{1:'整体颜色较浅',2:'整体颜色浅',3:'整体颜色很浅'}
                };
                var _vividMap = {
                    vivid:{1:'色彩较艳丽',2:'色彩艳丽',3:'色彩很艳丽'},
                    soft:{1:'色彩较柔和',2:'色彩柔和',3:'色彩很柔和'}
                };
                var _lightMap = {
                    bright:{1:'打光较亮',2:'打光亮',3:'打光很亮'},
                    dark:{1:'打光较暗',2:'打光暗',3:'打光很暗'}
                };
                var _warmthMap = {
                    cool:{1:'色调轻度偏冷',2:'色调偏冷',3:'色调明显偏冷'},
                    warm:{1:'色调轻度偏暖',2:'色调偏暖',3:'色调明显偏暖'}
                };
                if (_depth === 0) { if (_deep.dark[_sev]) _texts.push(_deep.dark[_sev]); }
                else if (_depth === 2) { if (_deep.light[_sev]) _texts.push(_deep.light[_sev]); }
                if (_vivid === 0) { if (_vividMap.vivid[_sev]) _texts.push(_vividMap.vivid[_sev]); }
                else if (_vivid === 2) { if (_vividMap.soft[_sev]) _texts.push(_vividMap.soft[_sev]); }
                if (_light === 0) { if (_lightMap.bright[_sev]) _texts.push(_lightMap.bright[_sev]); }
                else if (_light === 2) { if (_lightMap.dark[_sev]) _texts.push(_lightMap.dark[_sev]); }
                if (_warmth === 0) { if (_warmthMap.cool[_sev]) _texts.push(_warmthMap.cool[_sev]); }
                else if (_warmth === 2) { if (_warmthMap.warm[_sev]) _texts.push(_warmthMap.warm[_sev]); }
                if (_color) _texts.push('颜色偏' + _color);
                var _result = _texts.length > 0 ? _texts.join('。') + '。' : '';
                if (_extra) _result += _extra;
                if (_result) { taB.value = _result; _ar3_mark_dim_dirty(dim); _ar3_update_progress(); }
            };
            var _ar3_a2_make_panel = function() {
                if (_ar3_a2_panel) return _ar3_a2_panel;
                var p = document.createElement('div');
                p.className = '__ar3_a2_panel';
                p.style.cssText = 'display:none;margin-bottom:8px;padding:8px 10px;background:#12122a;border:1px solid #2a2a4a;border-radius:4px;font-size:12px;';

                var row = document.createElement('div');
                row.style.cssText = 'display:flex;align-items:flex-end;gap:12px;';

                var _make_column = function(leftLabel, rightLabel) {
                    var col = document.createElement('div');
                    col.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:2px;';
                    var labTop = document.createElement('span');
                    labTop.textContent = leftLabel;
                    labTop.style.cssText = 'color:#e0e0e0;font-size:11px;font-weight:bold;';
                    col.appendChild(labTop);
                    var s = document.createElement('input');
                    s.type = 'range';
                    s.min = '0'; s.max = '2'; s.value = '1'; s.step = '1';
                    s.style.cssText = '-webkit-appearance:slider-vertical;writing-mode:bt-lr;width:18px;height:70px;accent-color:#e94560;cursor:pointer;margin:4px 0;';
                    s.addEventListener('input', _ar3_a2_compose);
                    col.appendChild(s);
                    var labBot = document.createElement('span');
                    labBot.textContent = rightLabel;
                    labBot.style.cssText = 'color:#a0a0b0;font-size:11px;font-weight:bold;';
                    col.appendChild(labBot);
                    return {col: col, slider: s};
                };

                var _c1 = _make_column('深', '浅');
                _ar3_a2_depth_slider = _c1.slider;
                row.appendChild(_c1.col);

                var _c2 = _make_column('艳', '柔');
                _ar3_a2_vivid_slider = _c2.slider;
                row.appendChild(_c2.col);

                var _c3 = _make_column('亮', '暗');
                _ar3_a2_light_slider = _c3.slider;
                row.appendChild(_c3.col);

                var _c4 = _make_column('冷', '暖');
                _ar3_a2_warmth_slider = _c4.slider;
                row.appendChild(_c4.col);

                var colorCol = document.createElement('div');
                colorCol.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:2px;';
                var cl = document.createElement('span');
                cl.textContent = '色彩';
                cl.style.cssText = 'color:#a0a0b0;font-size:11px;';
                colorCol.appendChild(cl);
                _ar3_a2_color_input = document.createElement('input');
                _ar3_a2_color_input.type = 'text';
                _ar3_a2_color_input.placeholder = '红/蓝/绿';
                _ar3_a2_color_input.style.cssText = 'width:58px;padding:3px 5px;font-size:11px;border:1px solid #2a2a4a;border-radius:4px;background:#1a1a2e;color:#e0e0e0;outline:none;font-family:inherit;text-align:center;';
                _ar3_a2_color_input.addEventListener('input', _ar3_a2_compose);
                colorCol.appendChild(_ar3_a2_color_input);
                colorCol.appendChild(document.createElement('span'));
                row.appendChild(colorCol);

                var extraCol = document.createElement('div');
                extraCol.style.cssText = 'display:flex;flex-direction:column;flex:1;gap:2px;';
                var el = document.createElement('span');
                el.textContent = '额外说明';
                el.style.cssText = 'color:#a0a0b0;font-size:11px;';
                extraCol.appendChild(el);
                _ar3_a2_extra_input = document.createElement('input');
                _ar3_a2_extra_input.type = 'text';
                _ar3_a2_extra_input.placeholder = '追加文字到描述末尾';
                _ar3_a2_extra_input.style.cssText = 'width:100%;padding:5px 8px;font-size:12px;min-height:28px;border:1px solid #2a2a4a;border-radius:4px;background:#1a1a2e;color:#e0e0e0;outline:none;font-family:inherit;';
                _ar3_a2_extra_input.addEventListener('input', _ar3_a2_compose);
                extraCol.appendChild(_ar3_a2_extra_input);
                row.appendChild(extraCol);

                p.appendChild(row);
                _ar3_a2_panel = p;
                return p;
            };

            // ---- Consolidated 5-button row ----
            var sevRow = document.createElement('div');
            sevRow.style.cssText = 'display:flex;gap:4px;';

            var _sc = window.__ar3_scores || {};
            var btnDefs = [
                {label: '一致', severity: '', value: '一致', score: 0},
                {label: '轻度', severity: _sev_first('轻度'), value: '不一致', score: (typeof _sc.light === 'number' ? _sc.light : -100)},
                {label: '中度', severity: _sev_first('中度'), value: '不一致', score: (typeof _sc.moderate === 'number' ? _sc.moderate : -301)},
                {label: '重度', severity: _sev_first('重度'), value: '不一致', score: (typeof _sc.severe === 'number' ? _sc.severe : -710)},
                {label: '不适用', severity: '', value: '不适用', score: 0}
            ];

            // Determine initial active state (read from wrapper class, not input.checked)
            var selectedVal = _ar3_selected_option(dim);

            var activeIdx = -1;
            if (selectedVal === '不一致') {
                var _sk = _sev_to_key(parsed.severity);
                if (_sk === '轻度') activeIdx = 1;
                else if (_sk === '重度') activeIdx = 3;
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

            // Recompute this dim's score from its current slider index. Mode-aware:
            // 乘算 (multi) — multiply autoScore; 加算 (add) — add offset. Only multi
            // mode broadcasts to same-index dims on other tabs.
            var _ar3_apply_adj = function() {
                dim.__ar3_adjIdx = parseInt(slider.value, 10);
                var cfg = window.__ar3_slider_cfg || {};
                var mode = cfg.mode || 'multi';
                if (mode === 'add') {
                    var adds = cfg.add || [30, 10, 0, -10, -30];
                    var adj = (typeof adds[dim.__ar3_adjIdx] === 'number') ? adds[dim.__ar3_adjIdx] : 0;
                    // Ensure integer type (SpinBox values are int, but serialized may be float).
                    adj = Math.round(adj);
                    dim.__ar3_score = dim.__ar3_autoScore + adj;
                    var adjTxt = (adj >= 0 ? '+' : '') + (adj / 100).toFixed(2);
                    adjLabel.textContent = adjTxt + '→' + (dim.__ar3_score / 100).toFixed(2);
                } else {
                    var mults = cfg.multi || [0.1, 0.5, 1, 2, 10];
                    var mult = (typeof mults[dim.__ar3_adjIdx] === 'number') ? mults[dim.__ar3_adjIdx] : 1;
                    dim.__ar3_score = Math.trunc(dim.__ar3_autoScore * mult);
                    adjLabel.textContent = '×' + mult + '→' + (dim.__ar3_score / 100).toFixed(2);
                }
                _ar3_update_score();
            };
            // User dragged this slider → apply locally. Only broadcast in multi mode.
            slider.addEventListener('input', function() {
                _ar3_apply_adj();
                var cfg2 = window.__ar3_slider_cfg || {};
                if ((cfg2.mode || 'multi') === 'multi' && dimIdx >= 0 && dimIdx <= 4) {
                    _ar3_set_dim_scale(dimIdx, parseInt(slider.value, 10));
                }
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

            var _ar3_set_active = function(idx, noPropagate) {                // Guard against recursive re-entry from sync observer
                if (dim.__ar3_settingActive) return;
                dim.__ar3_settingActive = true;

                activeIdx = idx;
                var def = btnDefs[idx];
                reasonBox.setAttribute('data-severity', def.severity);
                // Read score dynamically so that settings changes take effect immediately.
                var _sc2 = window.__ar3_scores || {};
                var _scoreKeys = [null, 'light', 'moderate', 'severe', null];
                var _dynamicScore = (_scoreKeys[idx] ? _sc2[_scoreKeys[idx]] : def.score);
                if (typeof _dynamicScore !== 'number') _dynamicScore = def.score;
                dim.__ar3_autoScore = _dynamicScore;
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
                if (_ar3_a2_panel) {
                    var _a2On = window.__ar3_auto_fill_a2 && dimIdx === 2;
                    fieldRowB.style.display = (_a2On && showReason) ? 'none' : (showReason ? '' : 'none');
                    _ar3_a2_panel.style.display = (_a2On && showReason) ? 'block' : 'none';
                }

                // Update button styles
                sevBtns.forEach(function(b, i) {
                    var sel = i === idx;
                    b.style.border = '1px solid ' + (sel ? '#e94560' : '#2a2a4a');
                    b.style.background = sel ? '#3a1a2e' : '#1a1a2e';
                    b.style.color = sel ? '#e94560' : '#a0a0b0';
                });

                if (idx >= 1 && idx <= 3 && taB && !taB.value.trim()) {
                    var _fillMap = {
                        0: {enabled: 'auto_fill_model', texts: {1: '商品款式有所不同', 2: '商品款式不同', 3: '商品款式完全不同'}},
                        3: {enabled: 'auto_fill_a3', texts: {1: '图案有轻微差异', 2: '图案不一致和扭曲', 3: '图案缺失和严重不同'}},
                        4: {enabled: 'auto_fill_a4', texts: {1: '文字有轻微差异', 2: '文字不一致和扭曲', 3: '文字缺失和严重不同'}}
                    };
                    var _fm = _fillMap[dimIdx];
                    if (_fm && window['__ar3_' + _fm.enabled]) {
                        var _txt = _fm.texts[idx];
                        if (_txt) { taB.value = _txt; if (typeof _ar3_mark_dim_dirty === 'function') _ar3_mark_dim_dirty(dim); }
                    }
                }
                if (window.__ar3_auto_fill_a2 && dimIdx === 2 && typeof _ar3_a2_compose === 'function') _ar3_a2_compose();

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
                if (typeof _ar3_update_tab_slots === 'function') _ar3_update_tab_slots(letter);
                setTimeout(function() { dim.__ar3_settingActive = false; }, 300);
            };

            var sevBtns = [];
            btnDefs.forEach(function(def, i) {
                var btn = document.createElement('button');
                btn.textContent = def.label;
                btn.className = '__ar3_sev_btn';
                btn.setAttribute('data-sev-idx', String(i));
                btn.style.cssText = 'flex:1;padding:5px 4px;font-size:12px;border:1px solid ' + (i === activeIdx ? '#e94560' : '#2a2a4a') + ';border-radius:4px;background:' + (i === activeIdx ? '#3a1a2e' : '#1a1a2e') + ';color:' + (i === activeIdx ? '#e94560' : '#a0a0b0') + ';cursor:pointer;font-family:inherit;';
                sevRow.appendChild(btn);
                sevBtns.push(btn);
            });
            card.addEventListener('click', function(e) {
                var btn = e.target.closest('.__ar3_sev_btn');
                if (!btn) return;
                var idx = parseInt(btn.getAttribute('data-sev-idx'), 10);
                if (idx >= 0) _ar3_set_active(idx);
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
                                if (ta && !ta.value) { ta.value = text; _ar3_mark_dim_dirty(other); count++; }
                            }
                        });
                    });
                    pushBtn.textContent = '已推送(' + count + ')';
                    setTimeout(function() { pushBtn.textContent = '推送'; }, 1000);
                };
            })(letter);

            // ---- 强制推送: same as 推送 but ALWAYS overwrites (even non-empty). ----
            var forceBtn = document.createElement('button');
            forceBtn.textContent = '强制';
            forceBtn.title = '强制覆盖：无论是否已有内容都替换';
            forceBtn.style.cssText = 'flex-shrink:0;align-self:flex-start;background:#3a1a2e;color:#e94560;border:1px solid #e94560;border-radius:4px;padding:5px 8px;cursor:pointer;font-size:11px;font-weight:bold;font-family:inherit;white-space:nowrap;';
            (function(forceBtnRef) {
                forceBtnRef.onclick = function() {
                    var text = taA.value;
                    if (!text) {
                        forceBtnRef.textContent = '无内容';
                        setTimeout(function() { forceBtnRef.textContent = '强制'; }, 1200);
                        return;
                    }
                    var count = 0;
                    Object.keys(evalByModel).forEach(function(otherL) {
                        if (otherL === letter) return;
                        (evalByModel[otherL] || []).forEach(function(other) {
                            var mm = (other.__ar3_dimPrefix || '').match(/(\\d+)$/);
                            if (mm && parseInt(mm[1], 10) === dimIdx && other.__ar3_reasonInfo) {
                                var ta = other.__ar3_reasonInfo.taA;
                                if (ta) { ta.value = text; _ar3_mark_dim_dirty(other); count++; }
                            }
                        });
                    });
                    forceBtnRef.textContent = '已覆盖(' + count + ')';
                    setTimeout(function() { forceBtnRef.textContent = '强制'; }, 1000);
                };
            })(forceBtn);


            var inputsWrap = document.createElement('div');
            inputsWrap.style.cssText = 'display:flex;gap:6px;align-items:stretch;';

            var btnCol = document.createElement('div');
            btnCol.style.cssText = 'display:flex;flex-direction:column;gap:4px;flex-shrink:0;';
            btnCol.appendChild(pushBtn);
            btnCol.appendChild(forceBtn);

            inputsWrap.appendChild(btnCol);
            inputsWrap.appendChild(inputsCol);

            reasonBox.appendChild(inputsWrap);
            reasonBox.appendChild(_ar3_a2_make_panel());
            card.appendChild(sevRow);
            card.appendChild(reasonBox);

            // Typing only marks the field dirty; the original page is written
            // ONLY when the tab-level 提交本页 button is clicked (avoids the
            // write->observer->overwrite loop that was interrupting input).
            // During IME composition, defer progress/label updates to compositionend
            // to avoid DOM writes interfering with the IME session.
            taA.addEventListener('input', function() { _ar3_mark_dim_dirty(dim); if (!dim.__ar3_composing && typeof _ar3_update_progress === 'function') _ar3_update_progress(); });
            taB.addEventListener('input', function() { _ar3_mark_dim_dirty(dim); if (!dim.__ar3_composing && typeof _ar3_update_progress === 'function') _ar3_update_progress(); });
            taA.addEventListener('compositionstart', function() { dim.__ar3_composing = true; window.__ar3_ime_until = Date.now() + 120000; });
            taA.addEventListener('compositionend', function() {
                dim.__ar3_composing = false;
                _ar3_mark_dim_dirty(dim);
                dim.__ar3_compose_cool = Date.now() + 200;
                window.__ar3_ime_until = Date.now() + 200;
                if (typeof _ar3_update_progress === 'function') _ar3_update_progress();
            });
            taB.addEventListener('compositionstart', function() { dim.__ar3_composing = true; window.__ar3_ime_until = Date.now() + 120000; });
            taB.addEventListener('compositionend', function() {
                dim.__ar3_composing = false;
                _ar3_mark_dim_dirty(dim);
                dim.__ar3_compose_cool = Date.now() + 200;
                window.__ar3_ime_until = Date.now() + 200;
                if (typeof _ar3_update_progress === 'function') _ar3_update_progress();
            });

            // Initial visibility: show only for 不一致 (一致/不适用 hide the inputs)
            var initShow = (btnDefs[Math.max(0, activeIdx)].value === '不一致');
            reasonBox.style.display = initShow ? 'block' : 'none';
            if (_ar3_a2_panel) {
                var _a2OnInit = window.__ar3_auto_fill_a2 && dimIdx === 2;
                fieldRowB.style.display = (_a2OnInit && initShow) ? 'none' : (initShow ? '' : 'none');
                _ar3_a2_panel.style.display = (_a2OnInit && initShow) ? 'block' : 'none';
            }

            dim.__ar3_reasonInfo = {box: reasonBox, taA: taA, taB: taB, compose: _ar3_compose_reason, setActive: _ar3_set_active, btnDefs: btnDefs, submit: function() { _ar3_compose_reason(0, false); }, getActiveIdx: function() { return activeIdx; }};

            rightSide.appendChild(card);
        });

        panel.appendChild(rightSide);
        tabContent.appendChild(panel);
        tabs[letter] = {btn: tabBtn, panel: panel, refImg: ri, modelImg: mi, updateProgress: _ar3_update_progress, dims: dims};
        _ar3_update_score();
    });

    modelLetters.forEach(function(l) { _ar3_update_tab_slots(l); });

    var _ar3_active_letter = modelLetters.length ? modelLetters[0] : '';
    var _ar3_focus_dim_idx = 0;

    // Style a single tab button: active gets the red underline; an inactive tab with
    // unfinished dimensions is highlighted (amber text + underline) to flag it.
    function _ar3_restyle_tab(letter) {
        var t = tabs[letter];
        if (!t || !t.btn) return;
        var active = (letter === _ar3_active_letter);
        var incomplete = !!t.incomplete;
        if (active) {
            if (incomplete) {
                t.btn.style.background = '#e0a030';
                t.btn.style.border = '3px solid #e0a030';
            } else {
                t.btn.style.background = '#d0d0d0';
                t.btn.style.border = '3px solid #d0d0d0';
            }
            _set_tab_color(t.btn, '#1a1a2e');
        } else if (incomplete) {
            t.btn.style.background = 'transparent';
            t.btn.style.border = '3px solid transparent';
            t.btn.style.borderBottom = '3px solid #e0a030';
            _set_tab_color(t.btn, '#e0a030');
        } else {
            t.btn.style.background = 'transparent';
            t.btn.style.border = '3px solid transparent';
            _set_tab_color(t.btn, '#d0d0d0');
        }
    }

    function _set_tab_color(btn, color) {
        var spans = btn.querySelectorAll('span');
        for (var i = 0; i < spans.length; i++) spans[i].style.color = color;
    }

    function _ar3_dim_char(dim) {
        if (!dim || !dim.__ar3_reasonInfo) return '-';
        var idx = dim.__ar3_reasonInfo.getActiveIdx();
        if (idx < 0) return '-';
        if (idx === 0) return '0';
        if (idx === 4) return '\u00d7';
        return String(idx);
    }

    function _ar3_model_chars(letter) {
        var dims = (evalByModel[letter] || []).slice().sort(function(a, b) {
            return (a.__ar3_dimPrefix || '').localeCompare(b.__ar3_dimPrefix || '');
        });
        var chars = [];
        for (var i = 0; i < 5; i++) {
            var ch = i < dims.length ? _ar3_dim_char(dims[i]) : '-';
            chars.push(ch);
        }
        return '[ ' + chars.join(', ') + ' ]';
    }

    function _ar3_update_tab_slots(letter) {
        var t = tabs[letter];
        if (!t || !t.btn) return;
        var slotEl = t.btn.querySelector('.__ar3_tab_slots');
        if (slotEl) slotEl.textContent = _ar3_model_chars(letter);
        var rankChars = rankListRow.querySelector('[data-rank-model="' + letter + '"] .__ar3_rank_chars');
        if (rankChars) rankChars.textContent = _ar3_model_chars(letter);
        var rankModel = rankListRow.querySelector('[data-rank-model="' + letter + '"] .__ar3_rank_model');
        if (rankModel) rankModel.style.color = t.incomplete ? '#e0a030' : '#e0e0e0';
    }

    function _ar3_refresh_rank_highlight() {
        var slots = rankListRow.querySelectorAll('[data-rank-model]');
        for (var i = 0; i < slots.length; i++) {
            var l = slots[i].getAttribute('data-rank-model') || '';
            var t = tabs[l] || {};
            if (l && l.toUpperCase() === _ar3_active_letter) {
                var color = t.incomplete ? '#e0a030' : '#d0d0d0';
                slots[i].style.outline = '2px solid ' + color;
                slots[i].style.outlineOffset = '2px';
                slots[i].style.background = '#2a2a4e';
            } else {
                slots[i].style.outline = 'none';
                slots[i].style.outlineOffset = '0px';
                slots[i].style.background = '#1a1a2e';
            }
            var rm = slots[i].querySelector('.__ar3_rank_model');
            if (rm) rm.style.color = t.incomplete ? '#e0a030' : '#e0e0e0';
            var rc = slots[i].querySelector('.__ar3_rank_chars');
            if (rc && l) rc.textContent = _ar3_model_chars(l);
        }
    }

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
        if (typeof window.__ar3_submit_all === 'function') window.__ar3_submit_all();
        _ar3_active_letter = letter;
        Object.keys(tabs).forEach(function(l) {
            tabs[l].panel.style.display = 'none';
            _ar3_restyle_tab(l);
        });
        tabs[letter].panel.style.display = 'flex';
        if (!keepFocus) _ar3_focus_dim_idx = 0;

        _ar3_highlight_focus();
        _ar3_refresh_rank_highlight();
    }

    tabHeader.addEventListener('click', function(e) {
        var btn = e.target.closest('[data-model]');
        if (!btn) return;
        _ar3_activate_tab(btn.getAttribute('data-model'));
    });

    // ---- Keyboard shortcuts (skip while typing in a textarea/contenteditable) ----
    // A~H / ←→ : switch model tab | ↑↓ : move focused dimension |
    // 1~5 : set severity of focused dimension | Ctrl+Enter : 提交本页
    window.addEventListener('keydown', function(e) {
        if (!document.getElementById('__ar3_tab_overlay')) return;

        if (e.isComposing) return;

        var ae = document.activeElement;
        var typing = ae && (ae.tagName === 'TEXTAREA' || ae.tagName === 'INPUT' || ae.isContentEditable);

        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (typeof window.__ar3_submit_all === 'function') window.__ar3_submit_all();
            return;
        }

        // Leave all other modifier combos (Ctrl/Cmd/Alt) to the browser so that
        // copy (Ctrl+C) / paste (Ctrl+V) / undo (Ctrl+Z) etc. keep working.
        if (e.ctrlKey || e.metaKey || e.altKey) return;

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

    var _ar3_sync_cache_inputs = document.querySelectorAll('.customInput.horizontalLtr');
    var _ar3_sync_cache_ms = document.querySelectorAll('.multiple-select');
    var syncObserver = new MutationObserver(function(mutations) {
        var hasChildList = false;
        var hasRelevant = false;
        var monitorChanges = [];
        for (var i = 0; i < mutations.length; i++) {
            var mt = mutations[i];
            if (mt.target && overlay.contains(mt.target)) continue;
            hasRelevant = true;
            if (mt.type === 'childList') {
                hasChildList = true;
                mt.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && node.classList && (node.classList.contains('grid-item') || node.classList.contains('multiple-select') || node.classList.contains('rank-list-item'))) {
                        monitorChanges.push({type: 'added', classes: Array.from(node.classList), id: node.id || ''});
                    }
                });
                mt.removedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && node.classList && (node.classList.contains('grid-item') || node.classList.contains('multiple-select') || node.classList.contains('rank-list-item'))) {
                        monitorChanges.push({type: 'removed', classes: Array.from(node.classList), id: node.id || ''});
                    }
                });
            }
            if (mt.type === 'attributes' && (mt.attributeName === 'src' || mt.attributeName === 'checked' || mt.attributeName === 'value')) {
                monitorChanges.push({type: 'attr_changed', id: mt.target.id || mt.target.className, attr: mt.attributeName, newValue: mt.target.getAttribute(mt.attributeName)});
            }
        }
        if (monitorChanges.length > 0) {
            window.__annotation_last_changes = JSON.stringify(monitorChanges);
            if (!window.__annotation_monitor_active) window.__annotation_monitor_active = true;
        }
        if (!hasRelevant) return;
        if (hasChildList) {
            _ar3_sync_cache_inputs = document.querySelectorAll('.customInput.horizontalLtr');
            _ar3_sync_cache_ms = document.querySelectorAll('.multiple-select');
        }
        if (typeof _ar3_sync_timer !== 'undefined' && _ar3_sync_timer !== null) {
            clearTimeout(_ar3_sync_timer);
        }
        _ar3_sync_timer = setTimeout(_ar3_run_sync, 200);
    });

    function _ar3_run_sync() {
        _ar3_sync_timer = null;
        var _syncInputs = _ar3_sync_cache_inputs;
        var _syncMS = _ar3_sync_cache_ms;
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
        // Sync remark inputs from original -> overlay.
        // Skip entirely while any IME composition is active — writing to
        // textarea.value mid-composition forces premature commit (pinyin leak).
        if (window.__ar3_ime_until && Date.now() < window.__ar3_ime_until) return;
        Object.keys(evalByModel).forEach(function(letter) {
            (evalByModel[letter] || []).forEach(function(dim) {
                if (!dim.__ar3_reasonInfo) return;
                var ri = dim.__ar3_reasonInfo;
                // Find original CI by text marker "prefix+不一致" or "prefix+备注"
                var prefix = dim.__ar3_dimPrefix || '';
                if (!prefix) return;
                var allInputs = _syncInputs;
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
                // Also skip during IME composition: programmatic value assignment
                // on a composing textarea forces composition to commit prematurely
                // (pinyin can leak into the final text).
                if (dim.__ar3_dirty || dim.__ar3_composing || (document.activeElement === ri.taA || document.activeElement === ri.taB)) return;

                // Find corresponding MS to read checkbox state (by label text)
                var allMS = _syncMS;
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
                var _gmRe2 = new RegExp('生成图[：:][\\\\s\\\\S]*?(?=' + _sev_all.join('|') + '|$)');
                var gm = raw.match(_gmRe2);
                ri.taB.value = gm ? gm[0].replace(/^生成图[：:]\\s*/, '').trim() : '';
                var foundSev = '';
                for (var si = 0; si < _sev_all.length; si++) {
                    if (raw.indexOf(_sev_all[si]) >= 0) { foundSev = _sev_all[si]; break; }
                }
                // Map severity to button index (0=一致,1=轻度,2=中度,3=重度,4=不适用)
                // Use FRESH DOM query (dim may have been replaced by Vue re-render)
                var sevIdx = -1;
                if (freshDim) {
                    var cbVal = _ar3_selected_option(freshDim);
                    if (cbVal === '一致') {
                        sevIdx = 0;
                    } else if (cbVal === '不一致') {
                        var _sk2 = _sev_to_key(foundSev);
                        if (_sk2 === '轻度') sevIdx = 1;
                        else if (_sk2 === '重度') sevIdx = 3;
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
    }
    syncObserver.observe(document.body, {subtree: true, attributes: true, characterData: true, childList: true, attributeFilter: ['src', 'class', 'checked', 'value']});
    window.__ar3_sync_observer_active = true;

    window.__ar3_tabs = tabs;
    window.__ar3_model_items = modelItems;
    window.__ar3_ref_item = refItem;
    window.__ar3_rank_list = rankListRow;

    // Submit EVERY tab's dimensions into the original page (used on 返回原页面/解析).
    window.__ar3_submit_all = function() {
        if (window.__ar3_dirty_models.size === 0) return;
        window.__ar3_dirty_models.forEach(function(l) {
            (tabs[l].dims || []).forEach(function(d) {
                if (d.__ar3_reasonInfo && d.__ar3_reasonInfo.submit) { d.__ar3_reasonInfo.submit(); d.__ar3_dirty = false; }
            });
        });
        window.__ar3_dirty_models.clear();
    };

    if (_ar3_active_letter) { _ar3_activate_tab(_ar3_active_letter, true); }
    Object.keys(tabs).forEach(function(l) { _ar3_restyle_tab(l); });

    return JSON.stringify({status: 'transformed', count: modelLetters.length, models: modelLetters});
})();
"""
REMOVE_TABBED_LAYOUT = """
(function() {
    var overlay = document.getElementById('__ar3_tab_overlay');
    if (overlay) {
        if (typeof window.__ar3_submit_all === 'function') {
            try { window.__ar3_submit_all(); } catch (e) {}
        }
        overlay.parentNode.removeChild(overlay);
        window.__ar3_tabs = null;
        window.__ar3_model_items = null;
        window.__ar3_ref_item = null;
        window.__ar3_rank_list = null;
        if (typeof _ar3_sync_timer !== 'undefined' && _ar3_sync_timer !== null) {
            clearTimeout(_ar3_sync_timer);
            _ar3_sync_timer = null;
        }
        return 'removed';
    }
    return 'not_found';
})();
"""

APPLY_TILED_LAYOUT = """
(function() {
    if (document.getElementById('__ar3_tile_overlay') || document.getElementById('__ar3_tab_overlay')) {
        return JSON.stringify({status: 'already_transformed', mode: 'tiled', count: 0});
    }

    var gridItems = document.querySelectorAll('.grid-item[id*="content_engine"]');
    if (gridItems.length === 0) {
        return JSON.stringify({status: 'no_grid_found', mode: 'tiled', count: 0});
    }

    var refItem = null, modelItems = [];
    gridItems.forEach(function(item) {
        if (item.id.indexOf('ref_image') >= 0) refItem = item;
        else if (item.id.indexOf('model_') >= 0) modelItems.push(item);
    });

    function queuePopup(key, src) {
        if (!src) return;
        window.__ar3_popup_queue = window.__ar3_popup_queue || [];
        window.__ar3_popup_queue.push(JSON.stringify({key: key, src: src}));
    }

    var overlay = document.createElement('div');
    overlay.id = '__ar3_tile_overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;background:#1a1a2e;display:flex;flex-direction:column;font-family:"Microsoft YaHei",sans-serif;';

    var topBar = document.createElement('div');
    topBar.style.cssText = 'display:flex;align-items:center;background:#16213e;border-bottom:2px solid #2a2a4a;padding:6px 12px;flex-shrink:0;gap:8px;';
    var title = document.createElement('span');
    title.textContent = '图片平铺';
    title.style.cssText = 'flex:1;color:#e0e0e0;font-size:14px;font-weight:bold;';
    topBar.appendChild(title);
    var popupCloseBtn = document.createElement('button');
    popupCloseBtn.textContent = '关弹窗';
    popupCloseBtn.title = '关闭所有已打开的图片弹窗';
    popupCloseBtn.style.cssText = 'flex-shrink:0;background:#1a1a2e;color:#a0a0b0;border:1px solid #2a2a4a;border-radius:4px;padding:5px 12px;cursor:pointer;font-size:12px;font-family:inherit;';
    popupCloseBtn.onclick = function() {
        window.__ar3_popup_queue = window.__ar3_popup_queue || [];
        window.__ar3_popup_queue.push(JSON.stringify({key: '__close_all__', src: ''}));
    };
    topBar.appendChild(popupCloseBtn);
    var closeBtn = document.createElement('button');
    closeBtn.textContent = '返回原页面';
    closeBtn.style.cssText = 'flex-shrink:0;background:#e94560;color:#fff;border:none;border-radius:4px;padding:5px 14px;cursor:pointer;font-size:12px;font-weight:bold;';
    closeBtn.onclick = function() {
        document.body.removeChild(overlay);
        window.__ar3_overlay_just_closed = true;
    };
    topBar.appendChild(closeBtn);
    overlay.appendChild(topBar);

    var grid = document.createElement('div');
    grid.id = '__ar3_tile_grid';
    grid.style.cssText = 'flex:1;display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:1fr;gap:8px;padding:8px;overflow-y:auto;min-height:0;';
    overlay.appendChild(grid);

    var draggedCell = null;

    // In-cell zoom/pan: wheel = zoom, right-button drag = pan (only when zoomed).
    // Pan listeners live on the overlay so they are removed together with it.
    var panState = null;
    overlay.addEventListener('contextmenu', function(e) { e.preventDefault(); });
    overlay.addEventListener('mousemove', function(e) {
        if (!panState) return;
        panState.z.tx = panState.baseTx + (e.clientX - panState.startX);
        panState.z.ty = panState.baseTy + (e.clientY - panState.startY);
        panState.z.apply();
    });
    overlay.addEventListener('mouseup', function(e) {
        if (e.button === 2) panState = null;
    });

    function makeCell(labelText, key, src, accent) {
        var cell = document.createElement('div');
        cell.style.cssText = 'position:relative;display:flex;align-items:center;justify-content:center;background:#16213e;border-radius:8px;overflow:hidden;min-height:120px;border:1px solid ' + (accent ? '#e94560' : '#2a2a4a') + ';';
        var label = document.createElement('span');
        label.textContent = labelText;
        label.style.cssText = 'position:absolute;top:6px;left:10px;z-index:1;color:' + (accent ? '#e94560' : '#a0a0b0') + ';font-size:12px;font-weight:bold;background:rgba(26,26,46,0.7);padding:2px 8px;border-radius:4px;';
        cell.appendChild(label);
        var btnRow = document.createElement('div');
        btnRow.style.cssText = 'position:absolute;top:6px;right:8px;z-index:2;display:flex;gap:4px;align-items:center;';
        cell.appendChild(btnRow);
        var viewBtn = document.createElement('button');
        viewBtn.className = '__ar3_tile_view_btn';
        viewBtn.textContent = '窗口查看';
        viewBtn.title = '在独立窗口中查看此图片';
        viewBtn.draggable = false;
        viewBtn.style.cssText = 'background:#0f3460;color:#e0e0e0;border:1px solid #5c7cfa;border-radius:4px;padding:3px 10px;cursor:pointer;font-size:12px;font-family:inherit;';
        viewBtn.onclick = function(e) { e.stopPropagation(); queuePopup(key, src); };
        btnRow.appendChild(viewBtn);
        if (src) {
            var img = document.createElement('img');
            img.src = src;
            img.draggable = false;
            img.style.cssText = 'max-width:100%;max-height:100%;object-fit:contain;transform-origin:center center;';
            cell.appendChild(img);

            var resetBtn = document.createElement('button');
            resetBtn.className = '__ar3_tile_reset_btn';
            resetBtn.textContent = '\u21bb';
            resetBtn.title = '恢复原始大小、位置和方向';
            resetBtn.draggable = false;
            resetBtn.style.cssText = 'position:absolute;bottom:8px;right:8px;z-index:2;display:none;width:30px;height:30px;background:rgba(15,52,96,0.45);color:rgba(224,224,224,0.8);border:1px solid rgba(92,124,250,0.45);border-radius:15px;cursor:pointer;font-size:15px;line-height:1;font-family:inherit;';
            resetBtn.onmouseenter = function() { resetBtn.style.background = 'rgba(92,124,250,0.75)'; resetBtn.style.color = '#fff'; };
            resetBtn.onmouseleave = function() { resetBtn.style.background = 'rgba(15,52,96,0.45)'; resetBtn.style.color = 'rgba(224,224,224,0.8)'; };
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
            cell.__ar3_zoom = zoom;

            resetBtn.onclick = function(e) { e.stopPropagation(); zoom.reset(); };

            function makeGhostBtn(text, title, cls) {
                var b = document.createElement('button');
                b.className = cls;
                b.textContent = text;
                b.title = title;
                b.draggable = false;
                b.style.cssText = 'width:26px;height:26px;padding:0;background:rgba(15,52,96,0.45);color:rgba(224,224,224,0.8);border:1px solid rgba(92,124,250,0.45);border-radius:13px;cursor:pointer;font-size:13px;line-height:1;font-family:inherit;';
                b.onmouseenter = function() { b.style.background = 'rgba(92,124,250,0.75)'; b.style.color = '#fff'; };
                b.onmouseleave = function() { b.style.background = 'rgba(15,52,96,0.45)'; b.style.color = 'rgba(224,224,224,0.8)'; };
                return b;
            }

            var mirrorBtn = makeGhostBtn('\u21c4', '水平翻转', '__ar3_tile_mirror_btn');
            mirrorBtn.onclick = function(e) { e.stopPropagation(); zoom.mir = !zoom.mir; zoom.apply(); };
            var rotLBtn = makeGhostBtn('\u21b6', '向左旋转 15\u00b0', '__ar3_tile_rotl_btn');
            rotLBtn.onclick = function(e) { e.stopPropagation(); zoom.rot -= 15; zoom.apply(); };
            var rotRBtn = makeGhostBtn('\u21b7', '向右旋转 15\u00b0', '__ar3_tile_rotr_btn');
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

    // Model cells reorder via HTML5 drag; the ref cell is fixed at slot 0 and the
    // CSS grid reflow makes remaining cells shift into the freed slot automatically.
    function makeDraggable(cell) {
        cell.draggable = true;
        cell.style.cursor = 'grab';
        cell.addEventListener('dragstart', function(e) {
            draggedCell = cell;
            cell.style.opacity = '0.4';
            if (e.dataTransfer) {
                e.dataTransfer.effectAllowed = 'move';
                try { e.dataTransfer.setData('text/plain', cell.getAttribute('data-tile-model') || ''); } catch (err) {}
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

    var refSrc = '';
    if (refItem) {
        var refImg = refItem.querySelector('img.img');
        refSrc = refImg ? refImg.src : '';
    }
    var refCell = makeCell('参考图', 'ref_image', refSrc, true);
    refCell.setAttribute('data-tile-ref', '1');
    grid.appendChild(refCell);

    var count = 0;
    modelItems.forEach(function(item) {
        var m = item.id.match(/model_([A-H])$/);
        if (!m) return;
        var letter = m[1];
        var img = item.querySelector('img.img');
        var cell = makeCell('模型' + letter, 'model_' + letter, img ? img.src : '', false);
        cell.setAttribute('data-tile-model', letter);
        makeDraggable(cell);
        grid.appendChild(cell);
        count++;
    });

    // Bottom rank bar — mirrors the original page's current rank order (display
    // only for now; no sorting logic in tiled mode yet).
    var rankColors = [];
    document.querySelectorAll('.rank-title').forEach(function(el) {
        rankColors.push(el.style.backgroundColor || '');
    });
    var rankListItems = [];
    document.querySelectorAll('.rank-list-item').forEach(function(el) {
        rankListItems.push((el.childNodes[0] || {}).textContent || '');
    });
    var bottomBar = document.createElement('div');
    bottomBar.id = '__ar3_tile_rank_bar';
    bottomBar.style.cssText = 'flex-shrink:0;background:#16213e;border-top:2px solid #2a2a4a;padding:8px 12px 10px;display:flex;gap:4px;';
    var ranks = rankListItems.length ? rankListItems : ['模型A','模型B','模型C','模型D','模型E','模型F','模型G','模型H'];
    ranks.forEach(function(name, ri) {
        var color = rankColors[ri] || '#333';
        var letter = (name.match(/模型([A-H])/) || [])[1] || '';
        var slot = document.createElement('div');
        slot.className = '__ar3_tile_rank_slot';
        slot.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;background:#1a1a2e;border-radius:4px;padding:6px 4px;font-size:12px;color:#e0e0e0;border-bottom:3px solid ' + color + ';';
        slot.innerHTML = '<span style="font-weight:bold;color:' + color + ';">RANK ' + (ri + 1) + '</span>' +
            '<span>' + (letter ? '模型' + letter : name) + '</span>';
        bottomBar.appendChild(slot);
    });
    overlay.appendChild(bottomBar);

    document.body.appendChild(overlay);
    return JSON.stringify({status: 'transformed', mode: 'tiled', count: count});
})();
"""

REMOVE_TILED_LAYOUT = """
(function() {
    var overlay = document.getElementById('__ar3_tile_overlay');
    if (overlay) {
        overlay.parentNode.removeChild(overlay);
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
DRAIN_POPUP_QUEUE = """
(function() {
    var q = window.__ar3_popup_queue || [];
    if (q.length === 0) return '[]';
    var items = [];
    while (q.length > 0) items.push(q.shift());
    return '[' + items.join(',') + ']';
})();
"""

POLL_QUEUES = """
(function() {
    var aiQ = window.__ar3_ai_queue || [];
    var aiItems = [];
    while (aiQ.length > 0) { var r = aiQ.shift(); aiItems.push(JSON.stringify(r)); }
    var popQ = window.__ar3_popup_queue || [];
    var popItems = [];
    while (popQ.length > 0) popItems.push(popQ.shift());
    var closed = !!window.__ar3_overlay_just_closed;
    window.__ar3_overlay_just_closed = false;
    return JSON.stringify({ai: '[' + aiItems.join(',') + ']', popup: '[' + popItems.join(',') + ']', overlayClosed: closed});
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
