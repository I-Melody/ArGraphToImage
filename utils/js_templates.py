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

    var lightbox = document.createElement('div');
    lightbox.id = '__ar3_lightbox';
    lightbox.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100%;height:100%;z-index:100000;background:rgba(0,0,0,0.9);cursor:pointer;align-items:center;justify-content:center;';
    lightbox.innerHTML = '<img id="__ar3_lightbox_img" style="max-width:95%;max-height:95%;object-fit:contain;border-radius:6px;box-shadow:0 0 40px rgba(0,0,0,0.6);">';
    lightbox.onclick = function() { lightbox.style.display = 'none'; };
    document.body.appendChild(lightbox);

    function showLightbox(src) {
        document.getElementById('__ar3_lightbox_img').src = src;
        lightbox.style.display = 'flex';
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
    closeBtn.onclick = function() { document.body.removeChild(overlay); window.__ar3_tabs = null; };
    topBar.appendChild(closeBtn);
    overlay.appendChild(topBar);

    var tabContent = document.createElement('div');
    tabContent.id = '__ar3_tab_content';
    tabContent.style.cssText = 'flex:1;display:flex;overflow:hidden;min-height:0;';
    overlay.appendChild(tabContent);

    var bottomBar = document.createElement('div');
    bottomBar.id = '__ar3_rank_bar';
    bottomBar.style.cssText = 'flex-shrink:0;background:#16213e;border-top:2px solid #2a2a4a;padding:8px 12px 10px;';
    var rankTitleRow = document.createElement('div');
    rankTitleRow.style.cssText = 'display:flex;gap:4px;margin-bottom:8px;';
    var labels = ['RANK 1','RANK 2','RANK 3','RANK 4','RANK 5','RANK 6','RANK 7','RANK 8'];
    labels.forEach(function(lbl, i) {
        var badge = document.createElement('span');
        badge.textContent = lbl;
        badge.style.cssText = 'flex:1;text-align:center;padding:4px 0;border-radius:4px;font-size:12px;font-weight:bold;color:#fff;background:' + (rankColors[i] || '#333') + ';';
        rankTitleRow.appendChild(badge);
    });
    bottomBar.appendChild(rankTitleRow);
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
    bottomBar.appendChild(rankListRow);
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
        panel.appendChild(modelCol);

        // Column 3 — 评价
        var rightSide = document.createElement('div');
        rightSide.style.cssText = 'flex:1;min-width:0;padding:10px 14px;overflow-y:auto;background:#12122a;';
        var evalTitle = document.createElement('div');
        evalTitle.textContent = '评价 - 模型' + letter;
        evalTitle.style.cssText = 'color:#e0e0e0;font-size:14px;font-weight:bold;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #2a2a4a;';
        rightSide.appendChild(evalTitle);

        var dims = evalByModel[letter] || [];
        dims.forEach(function(dim) {
            var card = document.createElement('div');
            card.className = '__ar3_dim_card';

            var labelEl = dim.querySelector('.ivu-form-item-label, label');
            var dimLabel = labelEl ? labelEl.textContent.trim() : '';

            var dimTitle = document.createElement('div');
            dimTitle.textContent = dimLabel;
            dimTitle.className = '__ar3_dim_title';
            card.appendChild(dimTitle);

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
                {label: '一致', severity: '', value: '一致'},
                {label: '轻度', severity: '轻度不一致', value: '不一致'},
                {label: '中度', severity: '中度不一致', value: '不一致'},
                {label: '重度', severity: '重度不一致', value: '不一致'},
                {label: '不适用', severity: '', value: '不适用'}
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

            var _ar3_set_active = function(idx) {
                // Guard against recursive re-entry from sync observer
                if (dim.__ar3_settingActive) return;
                dim.__ar3_settingActive = true;

                activeIdx = idx;
                var def = btnDefs[idx];
                reasonBox.setAttribute('data-severity', def.severity);

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

                // Show/hide reason box
                var showReason = (def.value === '不一致' || def.value === '不适用');
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

            reasonBox.appendChild(sevRow);
            reasonBox.appendChild(fieldRowA);
            reasonBox.appendChild(fieldRowB);
            card.appendChild(sevRow);
            card.appendChild(reasonBox);

            // Bind inputs — rescan original each time before writing
            taA.addEventListener('input', function() {
                _ar3_compose_reason();
            });
            taB.addEventListener('input', function() {
                _ar3_compose_reason();
            });

            // Initial visibility: show if 不一致 or 不適用
            var initShow = (btnDefs[Math.max(0, activeIdx)].value === '不一致' || btnDefs[Math.max(0, activeIdx)].value === '不适用');
            reasonBox.style.display = initShow ? 'block' : 'none';

            dim.__ar3_reasonInfo = {box: reasonBox, taA: taA, taB: taB, compose: _ar3_compose_reason, setActive: _ar3_set_active, btnDefs: btnDefs};

            rightSide.appendChild(card);
        });

        panel.appendChild(rightSide);
        tabContent.appendChild(panel);
        tabs[letter] = {btn: tabBtn, panel: panel, refImg: ri, modelImg: mi};
    });

    tabHeader.addEventListener('click', function(e) {
        var btn = e.target.closest('button[data-model]');
        if (!btn) return;
        var letter = btn.getAttribute('data-model');
        Object.keys(tabs).forEach(function(l) {
            tabs[l].btn.style.background = 'transparent';
            tabs[l].btn.style.color = '#a0a0b0';
            tabs[l].btn.style.borderBottom = '2px solid transparent';
            tabs[l].panel.style.display = 'none';
        });
        btn.style.background = '#1a1a2e';
        btn.style.color = '#e94560';
        btn.style.borderBottom = '2px solid #e94560';
        tabs[letter].panel.style.display = 'flex';
    });

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
                    ri.setActive(sevIdx);
                }
            });
        });
    });
    syncObserver.observe(document.body, {subtree: true, attributes: true, characterData: true, attributeFilter: ['src']});

    window.__ar3_tabs = tabs;
    window.__ar3_model_items = modelItems;
    window.__ar3_ref_item = refItem;
    window.__ar3_rank_list = rankListRow;

    return JSON.stringify({status: 'transformed', count: modelLetters.length, models: modelLetters});
})();
"""
REMOVE_TABBED_LAYOUT = """
(function() {
    var overlay = document.getElementById('__ar3_tab_overlay');
    if (overlay) {
        overlay.parentNode.removeChild(overlay);
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
