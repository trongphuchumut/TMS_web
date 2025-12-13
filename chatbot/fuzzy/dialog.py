# chatbot/fuzzy/dialog.py
"""
Quản lý hội thoại FUZZY (follow-up hỏi thêm thông tin).

Ý tưởng:
- Khi thiếu info -> pipeline trả need_more_info + criteria hiện tại
- Lưu vào session: fuzzy_state = {criteria, turns_left, last_question, last_missing}
- User trả lời -> parse criteria mới từ câu trả lời, merge vào criteria cũ
- Có cơ chế thoát + TTL để "làm mờ" ngữ cảnh tránh nhầm
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Tuple

from .criteria_parser import call_ai_for_criteria
from .pipeline import run_fuzzy_suggest


FUZZY_TTL_TURNS = 6  # sau 6 lượt không liên quan thì auto reset


def is_exit_message(text: str) -> bool:
    t = (text or "").strip().lower()
    exit_words = ("thoi", "thôi", "stop", "dung", "dừng", "huy", "hủy", "cancel", "khong can", "không cần")
    return any(w in t for w in exit_words)


def merge_criteria(old: dict, new: dict) -> dict:
    """
    Merge: field mới != None thì overwrite.
    """
    out = deepcopy(old or {})
    for k, v in (new or {}).items():
        if k == "uu_tien" and isinstance(v, dict):
            out.setdefault("uu_tien", {})
            for kk, vv in v.items():
                if vv is not None:
                    out["uu_tien"][kk] = vv
            continue
        if v is not None:
            out[k] = v
    # confidence: lấy max (vì merge)
    out["confidence"] = max(float(old.get("confidence", 0.5)), float(new.get("confidence", 0.5)))
    return out


def handle_fuzzy_followup(user_message: str, fuzzy_state: dict, debug: bool = False) -> dict:
    """
    fuzzy_state: {criteria: dict, turns_left: int, ...}
    """
    if is_exit_message(user_message):
        return {
            "status": "exit",
            "message": "Ok, mình tạm dừng phần FUZZY. Khi cần bạn mô tả lại yêu cầu gia công, mình tư vấn từ đầu nhé.",
            "criteria": fuzzy_state.get("criteria"),
            "meta": {"exit": True},
        }

    old = fuzzy_state.get("criteria") or {}

    # Parse tiêu chí từ câu trả lời follow-up
    new_criteria, raw, err = call_ai_for_criteria(user_message)

    if debug:
        print("[FUZZY_FOLLOWUP] old:", old)
        print("[FUZZY_FOLLOWUP] raw:", raw[:300])
        print("[FUZZY_FOLLOWUP] err:", err)
        print("[FUZZY_FOLLOWUP] new:", new_criteria)

    if not new_criteria:
        # Không parse được -> hỏi lại, nhưng giảm TTL để tránh loop
        turns_left = int(fuzzy_state.get("turns_left", FUZZY_TTL_TURNS)) - 1
        return {
            "status": "need_more_info",
            "message": "Mình chưa bắt được ý bạn ở phần bổ sung. Bạn trả lời ngắn theo mẫu giúp mình:\n"
                       "- Vật liệu: ...\n- Gia công: ...\n- ĐK (nếu có): ...",
            "criteria": old,
            "meta": {"turns_left": turns_left, "parse_error": str(err) if err else None},
        }

    merged = merge_criteria(old, new_criteria)

    # Chạy lại fuzzy với criteria merged: trick bằng cách đưa JSON trực tiếp
    result = run_fuzzy_suggest(json.dumps(merged, ensure_ascii=False), debug=debug)
    result["criteria"] = merged
    return result
