# chatbot/fuzzy/criteria_parser.py
import json

from ..ai_client import call_ai


CRITERIA_SYSTEM_PROMPT = (
    "Bạn là chuyên gia chọn công cụ cắt và holder cho gia công cơ khí.\n"
    "Người dùng sẽ mô tả nhu cầu (vật liệu, loại gia công, độ chính xác, ưu tiên...).\n"
    "Hãy phân tích và TRẢ VỀ JSON, ví dụ:\n"
    "{\n"
    '  "loai_thiet_bi": "tool" hoặc "holder" hoặc "both",\n'
    '  "vat_lieu": "S45C",\n'
    '  "loai_gia_cong": "phay mat phang",\n'
    '  "uu_tien_do_ben": "cao/trung binh/thap",\n'
    '  "uu_tien_gia": "thap/trung binh/cao"\n'
    "}\n"
    "Chỉ trả đúng JSON, không giải thích thêm.\n"
)


def build_criteria_prompt(user_message: str) -> str:
    return (
        CRITERIA_SYSTEM_PROMPT
        + "\n\n"
        + f'Mô tả của người dùng: "{user_message}"'
    )


def call_ai_for_criteria(user_message: str) -> tuple[dict | None, str, Exception | None]:
    """
    Gửi prompt cho AI, nhận về raw JSON string.
    Trả:
      - criteria: dict hoặc None nếu parse lỗi
      - raw: string gốc AI trả về
      - err: Exception nếu có lỗi parse, ngược lại None
    """
    prompt = build_criteria_prompt(user_message)
    raw = call_ai(prompt)

    try:
        criteria = json.loads(raw)
        return criteria, raw, None
    except Exception as e:
        return None, raw, e
