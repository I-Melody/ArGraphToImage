import os
import re
import json
import base64
import logging
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal
from config import manager as config

_log = logging.getLogger("ai_client")

API_KEY = None
MODEL = "glm-4.6v"

AVAILABLE_MODELS = ["glm-4.6v", "glm-4.6v-flash"]

_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def set_key(key):
    global API_KEY
    API_KEY = (key or "").strip()


def set_model(model):
    global MODEL
    model = (model or "").strip()
    if model in AVAILABLE_MODELS:
        MODEL = model
        _log.info(f"AI model set to: {MODEL}")
    else:
        _log.warning(f"Unknown AI model: {model}, keeping {MODEL}")


def _load_model():
    global MODEL
    m = config.get("api.ai_model", "") or ""
    if m in AVAILABLE_MODELS:
        MODEL = m
    return MODEL


def _load_key():
    global API_KEY
    if API_KEY:
        return API_KEY
    API_KEY = (config.get("api.api_key", "") or "").strip()
    return API_KEY


class AiClient(QObject):
    describe_done = pyqtSignal(str, str)

    _pool = ThreadPoolExecutor(max_workers=2)

    _PROMPT_BASE = (
        "你将看到一张商品图片「参考图」。\n"
        "只描述图片中的商品主体的物理属性，完全忽略背景、桌面、地面、拍摄环境、肢体等非主体元素。\n"
        "只描述你实际看到的客观事实性内容（形状、结构、颜色、材质、文字、图案等），"
        "使用具体、可核对的描述；不要做任何主观判断、评价或推测。"
        "描述要详细，要包含细节。\n"
        "请严格从以下5个维度描述参考图主体，5个维度必须全部包含、互相不可重叠：\n"
        "1. 整体身份（该商品是什么品类、品类下的细分类别）\n"
        "2. 整体形状与局部结构（外形轮廓、内部结构、各部分的形状和位置关系）\n"
        "3. 颜色与材质（主色调、各部分颜色、材质感觉）\n"
        "4. 图案装饰logo商标（图案、花纹、logo、商标的位置和形态，无则填「无」）\n"
        "5. 文字信息（包装或主体上文字的内容、字体、颜色、位置，无则填「无」）\n"
        "返回严格的JSON（不要markdown代码块，纯JSON）。每个维度一个对象，含一个字符串字段\"描述\"。\n"
        "格式如下：\n"
        '{\n'
        '  "整体身份": {"描述": ""},\n'
        '  "整体形状与局部结构": {"描述": ""},\n'
        '  "颜色与材质": {"描述": ""},\n'
        '  "图案装饰logo商标": {"描述": ""},\n'
        '  "文字信息": {"描述": ""}\n'
        "}\n"
        "使用中文，描述具体细致、只陈述事实。"
    )

    def describe(self, request_id, ref_src, desc=None):
        _log.info(f"AI describe requested: id={request_id} model={MODEL}")
        self._pool.submit(self._run_describe, request_id, ref_src, desc)

    def _run_describe(self, request_id, ref_src, desc=None):
        result = self._call_api(ref_src, desc)
        self.describe_done.emit(request_id, result)

    @staticmethod
    def _image_part(src):
        if src.startswith("data:"):
            parts = src.split(",", 1)
            url = parts[1] if len(parts) == 2 else src
        else:
            url = src
        return {"type": "image_url", "image_url": {"url": url}}

    def _call_api(self, ref_src, desc=None):
        key = _load_key()
        if not key:
            return json.dumps({"error": "未设置API Key（请在设置中填写）"}, ensure_ascii=False)
        if not ref_src:
            return json.dumps({"error": "缺少参考图"}, ensure_ascii=False)

        _load_model()

        prompt = self._PROMPT_BASE
        if desc:
            desc = (desc or '').strip()
            if len(desc) > 2000:
                desc = desc[:2000] + '…'
            prompt = "【题目描述】（供参考，帮助你判断商品品类和关键特征）\n" + desc + "\n\n" + self._PROMPT_BASE

        content = [
            {"type": "text", "text": prompt},
            self._image_part(ref_src),
        ]
        body = json.dumps({"model": MODEL, "messages": [
                          {"role": "user", "content": content}]})
        body_bytes = body.encode("utf-8")
        _log.info(f"Sending AI describe request: model={MODEL} len={len(body_bytes)}")

        req = urllib.request.Request(_BASE, data=body_bytes)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + key)
        try:
            resp = urllib.request.urlopen(req, timeout=180)
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            _log.info("AI describe response received")
            return self._extract_json(msg)
        except urllib.error.HTTPError as e:
            _log.error(f"AI API HTTP {e.code}: {e.reason}")
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                _log.error(f"AI API error body: {err_body[:500]}")
            except Exception:
                pass
            return json.dumps({"error": f"HTTP {e.code}: {e.reason}"}, ensure_ascii=False)
        except Exception as e:
            _log.error(f"AI API call failed: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @staticmethod
    def _extract_json(text):
        if not text:
            return json.dumps({"raw": ""}, ensure_ascii=False)
        s = text.strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if m:
            s = m.group(1).strip()
        try:
            json.loads(s)
            return s
        except Exception:
            pass
        i, j = s.find("{"), s.rfind("}")
        if 0 <= i < j:
            cand = s[i:j + 1]
            try:
                json.loads(cand)
                return cand
            except Exception:
                pass
        return json.dumps({"raw": text.strip()}, ensure_ascii=False)
