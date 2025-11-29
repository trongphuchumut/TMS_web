# chatbot/fuzzy/dialog.py
import json
from .pipeline import run_fuzzy_suggest, CRITICAL_FIELDS
from .criteria_parser import call_ai_for_criteria
from ..ai_client import call_ai


def merge_criteria_with_followup(old_criteria: dict, followup_message: str) -> dict:
    """
    Cách đơn giản: gọi AI lần nữa, yêu cầu trả về JSON tiêu chí mới
    dựa trên:
      - tiêu chí cũ
      - câu trả lời follow-up của user
    """

    prompt = (
        "Bạn là hệ thống cập nhật tiêu chí chọn tool/holder cho gia công.\n"
        "Đây là tiêu chí hiện tại (JSON):\n"
        f"{json.dumps(old_criteria, ensure_ascii=False)}\n\n"
        "Người dùng vừa cung cấp thêm thông tin bổ sung:\n"
        f"- \"{followup_message}\"\n\n"
        "Hãy trả về lại JSON tiêu chí ĐÃ CẬP NHẬT, giữ nguyên các field cũ nếu user không đổi.\n"
        "Chỉ trả JSON, không giải thích thêm."
    )

    raw = call_ai(prompt)
    try:
        new_criteria = json.loads(raw)
        return new_criteria
    except Exception:
        # nếu lỗi thì giữ nguyên (xấu nhất vẫn dùng old_criteria)
        return old_criteria


def continue_fuzzy_dialog(state: dict, followup_message: str, debug: bool = False) -> dict:
    """
    state: lưu trong session, dạng:
      {
        "criteria": {...},
      }
    followup_message: câu user vừa trả lời thêm.

    Trả về cùng struct như run_fuzzy_suggest:
      {status, message, criteria, missing_fields}
    """
    old_criteria = state.get("criteria") or {}
    new_criteria = merge_criteria_with_followup(old_criteria, followup_message)

    # chạy lại fuzzy nhưng với tiêu chí mới
    # để tái sử dụng pipeline, ta có 2 lựa chọn:
    #  1) gọi lại run_fuzzy_suggest với message gốc + followup gộp
    #  2) viết 1 hàm run_fuzzy_with_criteria(new_criteria)
    #
    # Ở đây cho đơn giản, ta giả lập "user_message" là bản tóm tắt tiêu chí mới.
    pseudo_user_message = f"(update) {json.dumps(new_criteria, ensure_ascii=False)}"

    result = run_fuzzy_suggest(pseudo_user_message, debug=debug)
    # ghi đè criteria bằng new_criteria (do run_fuzzy_suggest sẽ gọi AI lại)
    result["criteria"] = new_criteria
    return result
