# chatbot/ai_client.py
import requests


def call_ai(prompt: str) -> str:
    payload = {
        "model": "gpt-oss:120b-cloud",
        "prompt": prompt,
        "stream": False,
    }

    print("[AI] Sending prompt, length:", len(prompt))    # 👈 debug
    # print("[AI] Prompt preview:", prompt[:200])         # mở nếu cần soi prompt

    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=120,
        )
    except Exception as e:
        print("[AI] Connection error:", e)                # 👈 debug
        return f"Lỗi kết nối tới Ollama: {e}"

    print("[AI] HTTP status:", res.status_code)           # 👈 debug

    try:
        data = res.json()
    except ValueError:
        print("[AI] JSON parse error, raw text:", res.text[:200])  # 👈 debug
        return f"Ollama trả về không phải JSON: {res.text[:200]}"

    if "error" in data:
        print("[AI] Ollama error field:", data["error"])  # 👈 debug
        return f"Lỗi từ Ollama: {data['error']}"

    if "response" not in data:
        print("[AI] Missing 'response' field, data:", data)  # 👈 debug
        return f"Ollama không trả field 'response': {data}"

    reply = data["response"]
    print("[AI] Got reply length:", len(reply))           # 👈 debug
    # print("[AI] Reply preview:", reply[:200])

    return reply
