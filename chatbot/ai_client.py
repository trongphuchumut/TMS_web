# chatbot/ai_client.py
from __future__ import annotations

import os
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# ✅ Frontend gửi: "local" | "cloud"
# ✅ Map ra model thật trong Ollama
MODEL_ALIAS = {
    "cloud": os.getenv("TMS_MODEL_CLOUD", "gpt-oss:120b-cloud"),
    "local": os.getenv("TMS_MODEL_LOCAL", "gemma3:4b"),
}

def resolve_model(model: str | None) -> str:
    """
    Nhận alias từ UI ("local"/"cloud") hoặc nhận trực tiếp tên model đầy đủ.
    """
    m = (model or "cloud").strip().lower()
    return MODEL_ALIAS.get(m, model or MODEL_ALIAS["cloud"])

def call_ai(prompt: str, model: str | None = None) -> str:
    """
    Gọi Ollama /api/generate.
    model: "local" | "cloud" | hoặc tên model đầy đủ (vd: "gemma3:4b")
    """
    payload = {
        "model": resolve_model(model),
        "prompt": prompt,
        "stream": False,
    }

    print("[AI] model:", payload["model"])
    print("[AI] prompt length:", len(prompt))

    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    except Exception as e:
        print("[AI] Connection error:", e)
        return f"Lỗi kết nối tới Ollama: {e}"

    print("[AI] HTTP status:", res.status_code)

    try:
        data = res.json()
    except ValueError:
        print("[AI] JSON parse error:", res.text[:200])
        return f"Ollama trả về không phải JSON: {res.text[:200]}"

    if "error" in data:
        print("[AI] Ollama error:", data["error"])
        return f"Lỗi từ Ollama: {data['error']}"

    reply = data.get("response", "")
    print("[AI] reply length:", len(reply))
    return (reply or "").strip()
