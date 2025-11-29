# chatbot/views.py
import json
import unicodedata

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .intents import detect_intent
from .handlers_smalltalk import handle_smalltalk_faq
from .handlers_search import handle_search_device
from .fuzzy.pipeline import run_fuzzy_suggest  # pipeline fuzzy trả về dict


def normalize_vi(text: str) -> str:
    """Lowercase + bỏ dấu tiếng Việt, dùng để check keyword thoát fuzzy."""
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def is_fuzzy_exit_message(message: str) -> bool:
    """
    User muốn thoát khỏi mode bổ sung fuzzy.
    Ví dụ: 'thôi', 'stop', 'không cần', 'thôi đủ rồi', 'dừng lại'...
    """
    norm = normalize_vi(message)
    patterns = [
        "thoi",         # "thôi"
        "thoi du roi",
        "dung lai",
        "stop",
        "khong can",
        "k can",
        "khong can nua",
        "huy",
        "huy bo",
    ]
    return any(p in norm for p in patterns)


@csrf_exempt
def chatbot_view(request):
    if request.method != "POST":
        return JsonResponse({"reply": "Chỉ hỗ trợ POST."}, status=405)

    # ===== ĐỌC BODY =====
    try:
        body = json.loads(request.body.decode("utf-8"))
        user_message = (body.get("message") or "").strip()
    except Exception:
        print("[CHATBOT] JSON không hợp lệ từ client:", request.body)
        return JsonResponse({"reply": "JSON không hợp lệ."}, status=400)

    if not user_message:
        print("[CHATBOT] Nhận request nhưng message trống")
        return JsonResponse({"reply": "Bạn chưa gửi nội dung."})

    # ===== LỊCH SỬ HỘI THOẠI =====
    history = request.session.get("chat_history", [])
    history.append({"role": "user", "content": user_message})

    print("\n========== NEW MESSAGE ==========")
    print("[CHATBOT] User:", user_message)
    print("[CHATBOT] History length:", len(history))

    # ===== 0) MODE FUZZY FOLLOW-UP =====
    fuzzy_state = request.session.get("fuzzy_state")
    if fuzzy_state:
        print("[CHATBOT] Fuzzy follow-up mode ON")

        # user muốn thoát mode fuzzy
        if is_fuzzy_exit_message(user_message):
            print("[CHATBOT] User requested to exit fuzzy follow-up")
            request.session.pop("fuzzy_state", None)
            reply = (
                "Ok, mình tạm dừng phần gợi ý fuzzy ở đây. "
                "Nếu bạn cần, cứ mô tả lại yêu cầu gia công, mình sẽ tư vấn từ đầu nhé."
            )
            history.append({"role": "bot", "content": reply})
            request.session["chat_history"] = history
            print("[CHATBOT] Reply (exit fuzzy):", reply[:150], "...\n")
            return JsonResponse({"reply": reply})

        # ngược lại: coi như user đang bổ sung thông tin cho cùng 1 ca fuzzy
        last_desc = fuzzy_state.get("description") or ""
        combined_desc = (last_desc + "\nThông tin bổ sung: " + user_message).strip()

        result = run_fuzzy_suggest(combined_desc, debug=False)
        reply = result["message"]

        # nếu vẫn cần hỏi thêm -> giữ state, update description
        if result["status"] == "need_more_info":
            request.session["fuzzy_state"] = {
                "description": combined_desc,
            }
            print("[CHATBOT] Fuzzy still need_more_info, keep state")
        else:
            # đã đủ thông tin -> clear state
            request.session.pop("fuzzy_state", None)
            print("[CHATBOT] Fuzzy reached final status, clear state")

        history.append({"role": "bot", "content": reply})
        request.session["chat_history"] = history
        print("[CHATBOT] Reply (fuzzy follow-up):", reply[:150], "...\n")
        return JsonResponse({"reply": reply})

    # ===== 1) KHÔNG Ở MODE FUZZY -> DETECT INTENT BÌNH THƯỜNG =====
    intent = detect_intent(user_message)
    print("[CHATBOT] Detected intent:", intent)

    if intent == "smalltalk_faq":
        reply = handle_smalltalk_faq(user_message, history)

    elif intent == "search_device":
        reply = handle_search_device(request, user_message)

    elif intent == "fuzzy_suggest":
        # Lần đầu gọi fuzzy cho câu hỏi này
        result = run_fuzzy_suggest(user_message, debug=False)
        reply = result["message"]

        # Nếu cần hỏi thêm -> lưu fuzzy_state để lần sau tiếp tục
        if result["status"] == "need_more_info":
            request.session["fuzzy_state"] = {
                "description": user_message,
            }
            print("[CHATBOT] Fuzzy need_more_info, set fuzzy_state")

    else:
        reply = "Xin lỗi, mình chưa hiểu ý bạn. Bạn có thể nói rõ hơn không?"

    # ===== 2) LƯU HISTORY + TRẢ LỜI =====
    history.append({"role": "bot", "content": reply})
    request.session["chat_history"] = history

    print("[CHATBOT] Reply:", reply[:150], "...\n")
    return JsonResponse({"reply": reply})

from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

@receiver(user_logged_out)
def clear_chat_on_logout(sender, request, user, **kwargs):
    if request is not None:
        request.session.pop("chat_history", None)