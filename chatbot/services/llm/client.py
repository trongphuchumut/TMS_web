import json
import requests

def ollama_chat(model: str, prompt: str) -> str:
    """
    Gọi Ollama (local) / hoặc bạn đổi endpoint theo server bạn đang chạy.
    """
    url = "http://localhost:11434/api/generate"
    r = requests.post(url, json={
        "model": model,
        "prompt": prompt,
        "stream": False,
    }, timeout=60)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def build_prompt(template: str, **kwargs) -> str:
    s = template
    for k, v in kwargs.items():
        s = s.replace("{{" + k + "}}", str(v))
    return s
