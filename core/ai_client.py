import os
import json
import base64
import urllib.request
import urllib.error
from PyQt6.QtCore import QObject, pyqtSignal
from config import manager as config

API_KEY = None
MODEL = "glm-4.6v"

_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def set_key(key):
    global API_KEY
    API_KEY = (key or "").strip()


def _load_key():
    global API_KEY
    if API_KEY:
        return API_KEY
    API_KEY = (config.get("api.api_key", "") or "").strip()
    return API_KEY


class AiClient(QObject):
    describe_done = pyqtSignal(str, str)

    _PROMPT = (
        "你将看到两张商品图片：第一张是「参考图」，第二张是「生成图」。\n"
        "只描述图片中的商品主体的物理属性，完全忽略背景、桌面、地面、拍摄环境、肢体等非主体元素。\n"
        "只描述你实际看到的客观事实性内容（形状、结构、颜色、材质、文字、图案等），"
        "使用具体、可核对的描述；不要做任何主观判断、评价、优劣比较或推测。"
        "只聚焦于两图主体中有差异的部分。描述要详细，要包含细节。因光线造成的颜色差异要被描述。\n"
        "请从以下5个维度详细对比两张图主体的差异之处，返回严格的JSON（不要markdown代码块，纯JSON）。\n"
        "每个维度对应一个对象，含三个字符串字段：\"参考图\"（该维度下参考图主体的客观描述）、"
        "\"生成图\"（该维度下生成图主体的客观描述）、\"差异\"（两者在客观事实上的具体不同，"
        "若无差异填「无明显差异」）。\n"
        "格式如下：\n"
        '{\n'
        '  "整体身份": {"参考图": "", "生成图": "", "差异": ""},\n'
        '  "整体形状与局部结构": {"参考图": "", "生成图": "", "差异": ""},\n'
        '  "颜色与材质": {"参考图": "", "生成图": "", "差异": ""},\n'
        '  "图案装饰logo商标": {"参考图": "", "生成图": "", "差异": ""},\n'
        '  "文字信息": {"参考图": "", "生成图": "", "差异": ""}\n'
        "}\n"
        "使用中文，描述具体细致、只陈述事实。"
    )

    def compare(self, request_id, ref_src, model_src):
        import threading
        t = threading.Thread(target=self._run, args=(
            request_id, ref_src, model_src), daemon=True)
        t.start()

    def _run(self, request_id, ref_src, model_src):
        result = self._call_api(ref_src, model_src)
        self.describe_done.emit(request_id, result)

    @staticmethod
    def _image_part(src):
        # Zhipu accepts a URL or base64 in image_url.url; for data: URIs pass the base64.
        if src.startswith("data:"):
            parts = src.split(",", 1)
            url = parts[1] if len(parts) == 2 else src
        else:
            url = src
        return {"type": "image_url", "image_url": {"url": url}}

    def _call_api(self, ref_src, model_src):
        key = _load_key()
        if not key:
            return json.dumps({"error": "未设置API Key（请在设置中填写）"}, ensure_ascii=False)
        if not ref_src or not model_src:
            return json.dumps({"error": "缺少参考图或模型图"}, ensure_ascii=False)

        content = [
            {"type": "text", "text": self._PROMPT},
            self._image_part(ref_src),
            self._image_part(model_src),
        ]

        body = json.dumps({"model": MODEL, "messages": [
                          {"role": "user", "content": content}]})
        req = urllib.request.Request(_BASE, data=body.encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + key)
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            msg = data.get("choices", [{}])[0].get(
                "message", {}).get("content", "")
            return self._extract_json(msg)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @staticmethod
    def _extract_json(text):
        import re
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
