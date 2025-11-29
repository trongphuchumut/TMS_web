# chatbot/handlers_smalltalk.py
from .ai_client import call_ai
from .faq_utils import find_faq_answer


def handle_smalltalk_faq(user_message: str, history: list) -> str:
    text = user_message.lower()

    # 1) chào hỏi đơn giản
    if any(x in text for x in ["xin chào", "chào", "hello", "hi", "chào bot"]):
        return "Chào bạn 👋! Mình là trợ lý TMS. Bạn muốn tìm thiết bị hay nhờ gợi ý tool/holder?"

    # 2) thử match FAQ trong txt
    faq_answer = find_faq_answer(user_message)
    if faq_answer:
        return faq_answer

    # 3) không match FAQ -> gửi cho AI, kèm context
    ctx = history[-10:]  # chỉ lấy ~10 câu gần nhất

    lines = [
        "Bạn là trợ lý thân thiện cho hệ thống quản lý kho công cụ TMS.",
        "Hãy trả lời ngắn gọn, dễ hiểu, giữ ngữ cảnh hội thoại, bằng tiếng Việt.",
        "Dưới đây là lịch sử hội thoại:",
        "",
    ]
    for msg in ctx:
        prefix = "User" if msg["role"] == "user" else "Bot"
        lines.append(f"{prefix}: {msg['content']}")
    lines.append("Bot:")

    prompt = "\n".join(lines)
    answer = call_ai(prompt)
    return answer
