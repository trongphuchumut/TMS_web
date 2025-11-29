# chatbot/faq_utils.py
import os
import difflib

FAQ_DATA = []


def load_faq_data():
    """
    Đọc file faq_data.txt trong cùng thư mục.
    Mỗi dòng: câu hỏi mẫu ||| câu trả lời
    """
    global FAQ_DATA
    faq_path = os.path.join(os.path.dirname(__file__), "faq_data.txt")
    if not os.path.exists(faq_path):
        FAQ_DATA = []
        return

    items = []
    with open(faq_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|||" not in line:
                continue
            q, a = line.split("|||", 1)
            items.append({"q": q.strip(), "a": a.strip()})

    FAQ_DATA = items


def find_faq_answer(user_message: str, threshold: float = 0.7):
    """
    Tìm câu trả lời trong FAQ nếu gần giống (so khớp mờ).
    """
    if not FAQ_DATA:
        load_faq_data()
        if not FAQ_DATA:
            return None

    text = user_message.lower()
    best_score = 0.0
    best_answer = None

    for item in FAQ_DATA:
        q = item["q"].lower()
        score = difflib.SequenceMatcher(None, text, q).ratio()
        if score > best_score:
            best_score = score
            best_answer = item["a"]

    if best_score >= threshold:
        return best_answer
    return None
