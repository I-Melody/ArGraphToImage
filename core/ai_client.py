import os
import json
import base64
import urllib.request
import urllib.error
from PyQt6.QtCore import QObject, pyqtSignal

API_KEY = None
MODEL = "glm-4.6v"

_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def _load_key():
    global API_KEY
    if API_KEY is not None:
        return API_KEY
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api.log")
    try:
        with open(path, "r") as f:
            API_KEY = f.read().strip()
    except Exception:
        API_KEY = ""
    return API_KEY


class AiClient(QObject):
    describe_done = pyqtSignal(str, str)

    _PROMPT = (
        "请对这张图片进行结构化分析，返回严格的JSON（不要markdown代码块，纯JSON）：\n"
        '{\n'
        '  "整体身份": "一句话描述图中主体是什么",\n'
        '  "整体形状与局部结构": "描述整体轮廓形状、关键部位的结构特征",\n'
        '  "颜色与材质": "描述主要颜色、材质质感",\n'
        '  "图案装饰logo商标": "描述图案、logo、商标等装饰，无则填无",\n'
        '  "文字信息": "描述图中出现的文字，无则填无"\n'
        "}\n"
        "使用中文。"
    )

    def describe(self, request_id, image_src):
        import threading
        t = threading.Thread(target=self._run, args=(request_id, image_src), daemon=True)
        t.start()

    def _run(self, request_id, image_src):
        result = self._call_api(image_src)
        self.describe_done.emit(request_id, result)

    def _call_api(self, image_src):
        key = _load_key()
        if not key:
            return json.dumps({"error": "api.log 未找到或为空"}, ensure_ascii=False)

        if image_src.startswith("data:"):
            parts = image_src.split(",", 1)
            if len(parts) == 2:
                image_ref = parts[1]
            else:
                image_ref = image_src
        else:
            image_ref = image_src

        content = [{"type": "text", "text": self._PROMPT}]
        if image_src.startswith("data:"):
            content.append({
                "type": "image_url",
                "image_url": {"url": image_src}
            })
        else:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_ref}
            })

        body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": content}]})
        req = urllib.request.Request(_BASE, data=body.encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + key)
        try:
            resp = urllib.request.urlopen(req, timeout=90)
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
