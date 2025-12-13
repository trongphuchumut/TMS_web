# chatbot/fuzzy/criteria_parser.py
"""
Tách tiêu chí cho fuzzy từ câu hỏi người dùng.

Mục tiêu:
- AI trả về JSON có cấu trúc (kèm confidence)
- Parse JSON robust (AI hay trả kèm chữ)
- Chuẩn hóa/điền default để pipeline dùng ổn định
- HỖ TRỢ SWITCH MODEL: call_ai(prompt, model=...)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Tuple, Optional

from ..ai_client import call_ai


CRITERIA_SYSTEM_PROMPT = """
Bạn là trợ lý kỹ thuật cho hệ thống TMS (Tool Management System) và chuyên gia chọn TOOL/HOLDER theo FUZZY LOGIC.

Nhiệm vụ:
1) Đọc câu người dùng.
2) Phân loại target: "tool" | "holder" | "both".
3) Trích xuất các tiêu chí có thể dùng để chấm điểm fuzzy.
4) TRẢ VỀ DUY NHẤT 1 JSON object (không thêm chữ ngoài JSON).

Schema (field nào không có thì để null):
{
  "loai_thiet_bi": "tool" | "holder" | "both",
  "loai_gia_cong": string|null,        // vd: "khoan", "phay", "taro"
  "vat_lieu": string|null,             // vd: "C45", "SUS304", "nhom"
  "duong_kinh": number|null,           // mm
  "chieu_dai_lam_viec": number|null,   // mm
  "yeu_cau_be_mat": string|null,       // vd: "mịn", "thô", "Ra1.6"
  "do_chinh_xac": string|null,         // vd: "cao", "trung_binh", "thap"
  "uu_tien": {                         // ưu tiên trọng số
    "toc_do": "cao"|"trung_binh"|"thap"|null,
    "do_ben": "cao"|"trung_binh"|"thap"|null,
    "gia": "cao"|"trung_binh"|"thap"|null,
    "chat_luong_be_mat": "cao"|"trung_binh"|"thap"|null
  },
  "confidence": number                 // 0..1 độ chắc chắn của việc parse
}

Quy ước:
- Nếu người dùng nói rất chung chung ("tư vấn tool") thì confidence thấp (<=0.55).
- Nếu user nói rõ vật liệu + gia công thì confidence cao hơn.
""".strip()

import re

def extract_requested_qty(user_text: str) -> int | None:
    """
    Bắt số lượng user yêu cầu cho TOOL tiêu hao.
    Ví dụ: "cần 10 mũi khoan", "lấy 20 cái", "10 pcs"
    """
    t = (user_text or "").lower()

    m = re.search(r"\b(cần|can|lấy|lay|muốn|muon|yêu cầu|yeu cau)\s*(\d{1,5})\b", t)
    if m:
        q = int(m.group(2))
        return q if 1 <= q <= 10000 else None

    m = re.search(r"\b(\d{1,5})\s*(cái|cai|mũi|mui|dao|tool|pcs|pc)\b", t)
    if m:
        q = int(m.group(1))
        return q if 1 <= q <= 10000 else None

    return None


def detect_target(user_text: str) -> str | None:
    """
    Xác định user đang muốn tool hay holder.
    """
    t = (user_text or "").lower()
    is_holder = any(k in t for k in ("holder", "đồ gá", "do ga", "bầu kẹp", "bau kep", "h-"))
    is_tool = any(k in t for k in ("tool", "dao", "mũi", "mui", "endmill", "drill", "drl", "taro", "tap"))
    if is_holder and not is_tool:
        return "holder"
    if is_tool and not is_holder:
        return "tool"
    if is_holder and is_tool:
        return "both"
    return None

def _extract_first_json_object(text: str) -> str | None:
    """
    Tìm JSON object đầu tiên trong text (trường hợp AI lỡ trả thêm chữ).
    Heuristic: lấy block từ { đến } bao phủ rộng nhất.
    """
    if not text:
        return None
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    return m.group(0).strip()


def _normalize_priority(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    mapping = {
        "high": "cao",
        "medium": "trung_binh",
        "low": "thap",
        "cao": "cao",
        "trung binh": "trung_binh",
        "trung_binh": "trung_binh",
        "thap": "thap",
    }
    return mapping.get(s, s)


def _coerce_number(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            v = v.replace(",", ".")
            v = re.sub(r"[^0-9.\-]", "", v)
        return float(v)
    except Exception:
        return None


def _normalize_criteria(c: Dict[str, Any]) -> Dict[str, Any]:
    loai = (c.get("loai_thiet_bi") or "tool").strip().lower()
    if loai not in ("tool", "holder", "both"):
        loai = "tool"

    uu = c.get("uu_tien") or {}
    if not isinstance(uu, dict):
        uu = {}

    out = {
        "loai_thiet_bi": loai,
        "loai_gia_cong": c.get("loai_gia_cong"),
        "vat_lieu": c.get("vat_lieu"),
        "duong_kinh": _coerce_number(c.get("duong_kinh")),
        "chieu_dai_lam_viec": _coerce_number(c.get("chieu_dai_lam_viec")),
        "yeu_cau_be_mat": c.get("yeu_cau_be_mat"),
        "do_chinh_xac": c.get("do_chinh_xac"),
        "uu_tien": {
            "toc_do": _normalize_priority(uu.get("toc_do")),
            "do_ben": _normalize_priority(uu.get("do_ben")),
            "gia": _normalize_priority(uu.get("gia")),
            "chat_luong_be_mat": _normalize_priority(uu.get("chat_luong_be_mat")),
        },
        "confidence": float(c.get("confidence") or 0.5),
    }

    # Chuẩn hóa string rỗng -> None
    for k in ("loai_gia_cong", "vat_lieu", "yeu_cau_be_mat", "do_chinh_xac"):
        if out.get(k) is not None:
            out[k] = str(out[k]).strip()
            if out[k] == "":
                out[k] = None

    return out


def build_criteria_prompt(user_message: str) -> str:
    return f"{CRITERIA_SYSTEM_PROMPT}\n\nUSER_MESSAGE:\n{user_message}\n"


def call_ai_for_criteria(
    user_message: str,
    model: Optional[str] = None
) -> Tuple[dict | None, str, Exception | None]:
    """
    Trả (criteria_dict|None, raw_text, err|None)
    """
    prompt = build_criteria_prompt(user_message)

    # ✅ SWITCH MODEL: truyền model xuống call_ai
    raw = call_ai(prompt, model=model)

    try:
        # Nếu user_message đã là JSON (trong follow-up) thì ưu tiên parse luôn
        try:
            direct = json.loads(user_message)
            if isinstance(direct, dict):
                return _normalize_criteria(direct), user_message, None
        except Exception:
            pass

        js = _extract_first_json_object(raw) or raw
        criteria = json.loads(js)
        if not isinstance(criteria, dict):
            raise ValueError("criteria is not dict")
        return _normalize_criteria(criteria), raw, None

    except Exception as e:
        return None, raw, e
