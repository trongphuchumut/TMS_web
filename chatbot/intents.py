# chatbot/intents.py
"""
Intent detection cho chatbot TMS.

Yêu cầu:
- Trả về (intent, confidence, reason)
- Hỗ trợ switch model: detect_intent(..., model=...)
- Khi confidence thấp -> views sẽ hỏi xác nhận (tránh nhảy sai luồng)
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Tuple, Optional

from .ai_client import call_ai


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


INTENT_SYSTEM = """
Bạn là bộ phân loại ý định cho chatbot TMS.
Chỉ có 4 intent:
- "smalltalk_faq": chào hỏi, hỏi linh tinh, hỏi hệ thống hoạt động thế nào
- "search_device": tìm kiếm 1 thiết bị/công cụ cụ thể trong DB (theo mã, tên)
- "fuzzy_suggest": yêu cầu đề xuất theo FUZZY LOGIC (chọn tool/holder phù hợp)
- "clarify": không chắc / cần hỏi lại

Trả về DUY NHẤT 1 JSON:
{
  "intent": "...",
  "confidence": 0..1,
  "reason": "ngắn gọn 1 câu"
}

Quy ước:
- Nếu câu chứa "đề xuất", "gợi ý", "phù hợp", "chọn giúp", "fuzzy" -> ưu tiên fuzzy_suggest.
- Nếu chứa mã thiết bị (vd: DRL-, H-, TOOL-, HOLDER-) hoặc hỏi "tìm", "search" -> search_device.
- Nếu rất ngắn, chung chung -> confidence thấp.
""".strip()


def _extract_json(text: str) -> str | None:
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return m.group(0).strip() if m else None


def detect_intent(user_message: str, model: Optional[str] = None) -> Tuple[str, float, str]:
    """
    model: tên model UI gửi lên (gpt-oss / gemma3 / llama3 / mistral ...)
    """
    msg = user_message or ""
    prompt = f"{INTENT_SYSTEM}\n\nUSER_MESSAGE:\n{msg}\n"

    # ✅ SWITCH MODEL: truyền model xuống call_ai
    raw = call_ai(prompt, model=model)

    try:
        js = _extract_json(raw) or raw
        obj = json.loads(js)
        intent = (obj.get("intent") or "clarify").strip()
        conf = float(obj.get("confidence") or 0.5)
        reason = str(obj.get("reason") or "").strip()
    except Exception:
        # fallback rule-based nhẹ
        m = normalize(msg)
        if any(k in m for k in ["fuzzy", "goi y", "de xuat", "phu hop", "chon giup"]):
            return "fuzzy_suggest", 0.55, "rule_fuzzy"
        if any(k in m for k in ["tim", "search", "ma ", "mã", "drl", "h-", "tool", "holder"]):
            return "search_device", 0.55, "rule_search"
        return "clarify", 0.4, "parse_fail"

    if intent not in ("smalltalk_faq", "search_device", "fuzzy_suggest", "clarify"):
        intent = "clarify"
    conf = 0.0 if conf < 0 else (1.0 if conf > 1 else conf)
    return intent, conf, reason
