# chatbot/intents.py

import re
import unicodedata
from .ai_client import call_ai


# ===========================
#  Utility: chuẩn hóa tiếng Việt
# ===========================

def normalize(text: str) -> str:
    """
    Chuẩn hóa tiếng Việt:
    - lowercase
    - bỏ dấu
    - trim khoảng trắng
    """
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


# ===========================
#  Hàm chính: detect_intent
# ===========================

def detect_intent(user_message: str) -> str:
    raw = user_message or ""
    norm = normalize(raw)  # hàm bạn đã có

    # YES / NO trước
    if norm in ("khong", "ko", "k", "no", "hong"):
        return "confirm_no"
    if norm in ("dung", "đúng", "ok", "oke", "uh", "u", "chuan"):
        return "confirm_yes"

    """
    
    Trả về 1 trong 4 intent:
      - 'smalltalk_faq'   : chào hỏi, hỏi cách dùng hệ thống, hỏi khái niệm chung
      - 'search_device'   : tìm / xem thông tin tool/holder trong kho
      - 'fuzzy_suggest'   : nhờ gợi ý chọn tool/holder theo điều kiện gia công
      - 'clarify'         : KHÔNG HIỂU RÕ Ý, cần hỏi người dùng nói rõ hơn

    Nguyên tắc:
      - Ưu tiên rule cho các pattern rõ ràng.
      - Chỉ khi không match rule nào mới dùng AI phân loại.
      - Nếu vẫn mơ hồ -> trả về 'clarify' chứ không đoán bừa.
    """
    raw_text = user_message.lower()
    text = normalize(user_message)
    
    print("========== INTENT DEBUG ==========")
    print("[INTENT] Raw:", user_message)
    print("[INTENT] Norm:", text)

    # ============ 0) CÂU HỎI TỒN KHO / SỐ LƯỢNG -> search_device ============
    stock_keywords = [
        "so luong", "số lượng",
        "ton kho", "tồn kho",
        "con bao nhieu", "còn bao nhiêu",
        "trong kho",
    ]
    if any(k in text for k in stock_keywords):
        print("[INTENT] Stock/inventory question -> search_device")
        return "search_device"

    # ============ 1) CÂU HỎI ĐỊNH NGHĨA '... LÀ GÌ' ============
    has_la_gi = " la gi" in text or text.endswith("la gi")
    if has_la_gi:
        device_words = [
            "holder", "tool", "insert",
            "endmill", "dao", "mui", "mũi",
            "cnmg", "wnmg", "tnmg", "dmg", "hss", "carbide",
        ]
        if any(w in text for w in device_words):
            print("[INTENT] Definition about DEVICE -> search_device")
            return "search_device"
        else:
            print("[INTENT] Definition about SYSTEM -> smalltalk_faq")
            return "smalltalk_faq"

    # ============ 2) HOW-TO / HƯỚNG DẪN SỬ DỤNG -> smalltalk_faq ============
    howto_keywords = ["cach ", "huong dan", "lam sao", "lam the nao", "how to"]
    howto_actions = [
        "muon", "mượn",
        "tra", "trả",
        "tao", "tạo",
        "them", "thêm",
        "xoa", "xóa",
        "dang nhap", "đăng nhập",
        "dang xuat", "đăng xuất",
        "su dung", "sử dụng",
        "nhap kho", "nhập kho",
        "xuat kho", "xuất kho",
        "tao holder", "tạo holder",
        "tao tool", "tạo tool",
    ]
    is_howto = any(k in text for k in howto_keywords) and any(
        a in text for a in howto_actions
    )
    if is_howto:
        print("[INTENT] How-to question -> smalltalk_faq")
        return "smalltalk_faq"

    # ============ 3) FUZZY SUGGESTION (gợi ý chọn tool/holder) ============
    fuzzy_keywords = [
        "goi y", "gợi ý",
        "de xuat", "đề xuất",
        "nen dung", "nên dùng",
        "nen chon", "nên chọn",
        "loai nao", "loại nào",
        "chon dung", "chọn đúng",
        "hop cho", "hợp cho",
        "phu hop", "phù hợp",
        "chon tool", "chọn tool",
        "chon holder", "chọn holder",
        "suggest",
    ]
    fuzzy_verbs = [
        "dung gi", "dùng gì",
        "xai gi", "xài gì",
        "nen xai", "nên xài",
        "nen dung", "nên dùng",
    ]

    process_pattern = r"(phay|khoan|tien|tiện|taro|doa|doa|cat|cắt).*?(dung gi|dùng gì|xai gi|xài gì|nen dung gi|nên dùng gì)\??$"

    if any(k in text for k in fuzzy_keywords) or any(v in text for v in fuzzy_verbs):
        print("[INTENT] Fuzzy keywords matched -> fuzzy_suggest")
        return "fuzzy_suggest"

    if re.search(process_pattern, text):
        print("[INTENT] Process pattern matched -> fuzzy_suggest")
        return "fuzzy_suggest"

    materials = ["s45c", "sus304", "nhom", "aluminum", "inox", "skd11", "s50c", "scm440"]
    actions = ["phay", "khoan", "tien", "tiện", "doa", "taro"]
    if any(m in text for m in materials) and any(a in text for a in actions):
        print("[INTENT] material+action combo -> fuzzy_suggest")
        return "fuzzy_suggest"

    # ============ 4) SEARCH DEVICE (tìm tool/holder/mã/vị trí) ============
    search_keywords = [
        "tim", "tìm",
        "kiem", "kiếm",
        "o dau", "ở đâu",
        "vi tri", "vị trí",
        "ma ", "mã ",
        "code", "thong tin", "thông tin",
        "lay tool", "lấy tool",
        "lay holder", "lấy holder",
        "kiem tool", "kiếm tool",
        "kiem holder", "kiếm holder",
    ]
    if any(k in text for k in search_keywords):
        print("[INTENT] Search keywords -> search_device")
        return "search_device"

    code_pattern = r"\b(h-\d+|t-\d+|er\d+|sk\d+|mt\d+|d\d+(\.\d+)?)\b"
    if re.search(code_pattern, raw_text, flags=re.IGNORECASE):
        print("[INTENT] Code pattern -> search_device")
        return "search_device"

    if not is_howto:
        device_words = [
            "holder", "tool", "mũi", "mui", "dao",
            "insert", "endmill", "cnmg", "wnmg", "tnmg",
        ]
        if any(w in raw_text for w in device_words):
            print("[INTENT] Device word present -> search_device")
            return "search_device"

    # ============ 5) SMALLTALK CƠ BẢN / HỎI HỆ THỐNG ============
    smalltalk_keywords = [
        "xin chao", "xin chào",
        "chao", "chào",
        "hello", "hi",
        "ban la ai", "bạn là ai",
        "ten gi", "tên gì",
        "lam gi day", "làm gì đấy",
    ]
    if any(k in text for k in smalltalk_keywords):
        print("[INTENT] Smalltalk keyword -> smalltalk_faq")
        return "smalltalk_faq"

    system_keywords = [
        "tms la gi", "tms là gì",
        "he thong tms", "hệ thống tms",
        "chuc nang", "chức năng",
        "cach su dung", "cách sử dụng",
    ]
    if any(k in text for k in system_keywords):
        print("[INTENT] System question -> smalltalk_faq")
        return "smalltalk_faq"

    # ============ 6) AI FALLBACK (câu mơ hồ) ============
    print("[INTENT] No rule matched -> using AI classifier")
    ai_intent = detect_intent_by_ai(user_message)

    # Nếu AI trả về intent hợp lệ thì dùng
    if ai_intent in ("smalltalk_faq", "search_device", "fuzzy_suggest"):
        return ai_intent

    # >>> Nếu AI không chắc hoặc trả về 'clarify' -> mình CHỦ ĐỘNG nói là chưa hiểu rõ
    print("[INTENT] AI not confident / clarify -> clarify")
    return "clarify"


# ===========================
#  AI classifier fallback
# ===========================

def detect_intent_by_ai(user_message: str) -> str:
    """
    Nhờ AI phân loại intent.
    AI được phép trả về 1 trong 4 từ:
      - smalltalk_faq
      - search_device
      - fuzzy_suggest
      - clarify  (nếu câu hỏi mơ hồ, không đủ thông tin, không tự tin phân loại)
    """
    prompt = f"""
Bạn là bộ phân loại câu hỏi cho hệ thống quản lý kho công cụ TMS.

Nhiệm vụ:
- Nhận một câu người dùng hỏi bằng tiếng Việt.
- Phân loại câu này vào đúng 1 trong các nhóm intent sau:

1) smalltalk_faq:
   - Chào hỏi, nói chuyện linh tinh
   - Câu hỏi hướng dẫn cách sử dụng hệ thống
   - Hỏi khái niệm chung: "TMS là gì"

2) search_device:
   - Người dùng muốn TÌM hoặc XEM thông tin một thiết bị cụ thể trong kho
   - Tìm tool/holder theo mã, tên, vị trí, số lượng, tồn kho
   - Ví dụ: "tìm holder H-001", "Endmill HSS Φ10 là gì", "Insert tiện ngoài CNMG là gì",
     "số lượng tool DRL-5.0 trong kho", "vị trí tool CNMG ở đâu"

3) fuzzy_suggest:
   - Người dùng mô tả nhu cầu gia công, muốn GỢI Ý thiết bị tối ưu
   - Có từ khóa: gợi ý, đề xuất, nên dùng, loại nào phù hợp, dùng gì, xài gì
   - Hoặc mô tả vật liệu + kiểu gia công: "phay S45C", "khoan SUS304 dùng dao gì",
     "tiện ngoài S45C nên dùng insert nào"

4) clarify:
   - Câu hỏi quá mơ hồ, không đủ thông tin để biết là tìm thiết bị hay gợi ý
   - Bạn cảm thấy KHÔNG TỰ TIN khi chọn 1 trong 3 intent trên
   - Ví dụ: "ủa sao kỳ vậy ta", "cái đó sao ta", "hmm", "??", hoặc câu không rõ ngữ cảnh

YÊU CẦU:
- Chỉ trả về DUY NHẤT 1 từ trong 4 từ sau (không giải thích thêm):
  smalltalk_faq
  search_device
  fuzzy_suggest
  clarify

Câu người dùng: "{user_message}"
Intent:
""".strip()

    ai_reply = call_ai(prompt)
    intent_raw = ai_reply.strip().lower()

    for token in ("smalltalk_faq", "search_device", "fuzzy_suggest", "clarify"):
        if token in intent_raw:
            print("[INTENT_AI] Model classified as:", token)
            return token

    print("[INTENT_AI] Model reply not clean:", ai_reply)
    # >>> Không hiểu thì báo về clarify, không nhảy bừa vào smalltalk nữa
    return "clarify"
