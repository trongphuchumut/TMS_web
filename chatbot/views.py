# chatbot/views.py
import json
import re
import unicodedata
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .intents import detect_intent
from .handlers_smalltalk import handle_smalltalk_faq
from .handlers_search import handle_search_device, handle_search_confirm
from .fuzzy.pipeline import run_fuzzy_suggest
from .fuzzy.dialog import handle_fuzzy_followup, FUZZY_TTL_TURNS

try:
    from .models import FuzzyRunLog
except Exception:
    FuzzyRunLog = None


# ================== CONFIG ==================
MAX_HISTORY = 20  # cắt history để session không phình -> tránh mất state confirm


# ================== Helpers ==================

def normalize_vi(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def parse_yes_no(text: str) -> str | None:
    t = normalize_vi(text).strip()
    if t in ("dung", "yes", "y", "ok", "oke"):
        return "yes"
    if t in ("khong", "no", "n", "sai", "khong dung"):
        return "no"
    return None


def is_why_question(text: str) -> bool:
    t = normalize_vi(text)
    return any(k in t for k in ("tai sao", "vi sao", "giai thich", "ly do", "why"))


def push_history(session, role: str, content: str) -> list[dict]:
    hist = session.get("chat_history", [])
    hist.append({"role": role, "content": content})

    if len(hist) > MAX_HISTORY:
        hist = hist[-MAX_HISTORY:]

    session["chat_history"] = hist
    session.modified = True
    return hist


def recover_confirm_state_from_history(history: list[dict]) -> dict | None:
    """
    Fallback cực quan trọng:
    Nếu session bị mất device_confirm_state, ta cố gắng parse từ câu bot hỏi confirm trước đó:
    "Bạn đang hỏi về **tool DRL-HSS-07-GEN - ...** phải không?"
    """
    # tìm tin nhắn bot gần nhất có dạng confirm
    for msg in reversed(history):
        if msg.get("role") != "bot":
            continue
        text = msg.get("content") or ""

        # match "**tool CODE -"
        m = re.search(r"\*\*(tool|holder)\s+([A-Za-z0-9\-_\.]+)\s*-\s*", text)
        if not m:
            continue

        typ_label = m.group(1).lower()       # tool | holder
        code = m.group(2).strip()

        # truy DB theo mã để lấy id + name
        try:
            if typ_label == "tool":
                from tool.models import Tool
                obj = Tool.objects.filter(ma_tool__iexact=code).first()
                if not obj:
                    return None
                return {
                    "type": "tool",
                    "id": obj.id,
                    "code": obj.ma_tool,
                    "name": obj.ten_tool,
                }

            if typ_label == "holder":
                from holder.models import Holder
                obj = Holder.objects.filter(ma_noi_bo__iexact=code).first()
                if not obj:
                    return None
                return {
                    "type": "holder",
                    "id": obj.id,
                    "code": obj.ma_noi_bo,
                    "name": obj.ten_thiet_bi,
                }
        except Exception:
            return None

    return None


# ================== Fuzzy explain ==================

def format_last_fuzzy_explain(session) -> str | None:
    last = session.get("last_fuzzy")
    if not last:
        return None

    top = last.get("top") or []
    if not top:
        return None

    best = top[0]
    lines = [
        f"🔎 **Vì sao mình gợi ý `{best.get('name')}`?**",
        f"- **Điểm fuzzy tổng:** {best.get('score')}/100",
    ]

    breakdown = best.get("breakdown") or {}
    if breakdown:
        lines.append("- **Đóng góp theo tiêu chí:**")
        for k, v in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - {k}: {round(v * 100)}%")

    lines.append(
        "\nBạn có thể bổ sung thêm vật liệu, loại gia công, "
        "đường kính, chiều dài làm việc… để chấm chính xác hơn."
    )
    return "\n".join(lines)


def store_last_fuzzy(request, user_text: str, result: dict):
    top = []
    for s, dev, br in (result.get("scored") or [])[:5]:
        top.append({
            "score": round(float(s) * 100, 1),
            "name": getattr(dev, "ten_tool", None)
                    or getattr(dev, "ten_thiet_bi", None)
                    or str(dev),
            "code": getattr(dev, "ma_tool", None)
                    or getattr(dev, "ma_noi_bo", None)
                    or "",
            "breakdown": br,
        })

    plot = (result.get("meta") or {}).get("plot") or {}

    request.session["last_fuzzy"] = {
        "ts": datetime.now().isoformat(),
        "question": user_text,
        "criteria": result.get("criteria") or {},
        "top": top,
        "meta": {
            **(result.get("meta") or {}),
            "plot": plot,
        },
    }
    request.session.modified = True

    if FuzzyRunLog:
        try:
            FuzzyRunLog.objects.create(
                user_text=user_text,
                criteria_json=request.session["last_fuzzy"]["criteria"],
                results_json=top,
            )
        except Exception:
            pass


# ================== MAIN VIEW ==================

@csrf_exempt
def chatbot_view(request):
    if request.method != "POST":
        return JsonResponse({"reply": "Only POST"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"reply": "Body JSON không hợp lệ."}, status=400)

    user_message = (data.get("message") or "").strip()
    model = (data.get("model") or "cloud").strip()
    explain_fuzzy = bool(int(data.get("explain_fuzzy", 1)))
    debug = bool(data.get("debug", False))

    if not user_message:
        return JsonResponse({"reply": "Bạn nhập câu hỏi giúp mình nhé."})

    # ----- history -----
    history = request.session.get("chat_history", [])
    push_history(request.session, "user", user_message)

    print("\n[CHATBOT] User:", user_message)

    # =========================================================
    # 1) SEARCH CONFIRM MODE (đúng / không) - CHỐT TRƯỚC detect_intent
    # =========================================================
    yn = parse_yes_no(user_message)
    if yn:
        search_state = request.session.get("device_confirm_state")

        # nếu state bị mất (session phình) -> cố recover từ history
        if not search_state:
            recovered = recover_confirm_state_from_history(history)
            if recovered:
                request.session["device_confirm_state"] = recovered
                request.session.modified = True
                search_state = recovered

        if search_state:
            reply, done = handle_search_confirm(
                request=request,
                user_message=user_message,
                state=search_state,
                intent="confirm_yes" if yn == "yes" else "confirm_no",
            )
            if done:
                request.session.pop("device_confirm_state", None)
                request.session.modified = True

            push_history(request.session, "bot", reply)
            return JsonResponse({"reply": reply})

        # user nói đúng/không nhưng không có state -> hướng dẫn nhẹ
        reply = "Bạn đang xác nhận thiết bị nào vậy? Bạn gửi lại **mã tool/holder** (ví dụ DRL-HSS-07-GEN) giúp mình nhé."
        push_history(request.session, "bot", reply)
        return JsonResponse({"reply": reply})

    # =========================================================
    # 2) FUZZY FOLLOW-UP MODE
    # =========================================================
    fuzzy_state = request.session.get("fuzzy_state")
    if fuzzy_state:
        fuzzy_state["turns_left"] = int(fuzzy_state.get("turns_left", FUZZY_TTL_TURNS))
        if fuzzy_state["turns_left"] <= 0:
            request.session.pop("fuzzy_state", None)
            request.session.modified = True
        else:
            print("[CHATBOT] Fuzzy follow-up ON. turns_left=", fuzzy_state["turns_left"])

            # tương thích chữ ký hàm (phòng khi file dialog cũ)
            try:
                res = handle_fuzzy_followup(
                    user_message,
                    fuzzy_state,
                    debug=debug,
                    model=fuzzy_state.get("model") or model,
                )
            except TypeError:
                res = handle_fuzzy_followup(user_message, fuzzy_state, debug=debug)

            if res.get("status") == "need_more_info":
                fuzzy_state["criteria"] = res.get("criteria") or fuzzy_state.get("criteria")
                fuzzy_state["turns_left"] -= 1
                request.session["fuzzy_state"] = fuzzy_state
                request.session.modified = True

            elif res.get("status") == "ok":
                request.session.pop("fuzzy_state", None)
                request.session.modified = True
                store_last_fuzzy(
                    request,
                    fuzzy_state.get("description") or user_message,
                    res,
                )

            reply = res.get("message", "Mình chưa xử lý được yêu cầu fuzzy.")
            push_history(request.session, "bot", reply)
            return JsonResponse({"reply": reply})

    # =========================================================
    # 3) WHY QUESTION (giải thích fuzzy)
    # =========================================================
    if is_why_question(user_message):
        explain = format_last_fuzzy_explain(request.session)
        if explain:
            push_history(request.session, "bot", explain)
            return JsonResponse({"reply": explain})

    # =========================================================
    # 4) DETECT INTENT
    # =========================================================
    intent, conf, reason = detect_intent(user_message, model=model)
    print("[CHATBOT] intent:", intent, "conf:", conf, "reason:", reason)

    # =========================================================
    # 5) ROUTING
    # =========================================================
    if intent == "search_device":
        reply = handle_search_device(request, user_message)

    elif intent == "fuzzy_suggest":
        try:
            result = run_fuzzy_suggest(user_message, debug=debug, model=model)
        except TypeError:
            result = run_fuzzy_suggest(user_message, debug=debug)

        reply = result.get("message", "Mình chưa xử lý được phần fuzzy.")

        if result.get("status") == "need_more_info":
            request.session["fuzzy_state"] = {
                "description": user_message,
                "criteria": result.get("criteria") or {},
                "turns_left": FUZZY_TTL_TURNS,
                "model": model,
            }
            request.session.modified = True

        elif result.get("status") == "ok":
            store_last_fuzzy(request, user_message, result)
            if explain_fuzzy:
                exp = format_last_fuzzy_explain(request.session)
                if exp:
                    reply += "\n\n" + exp

    elif intent == "smalltalk_faq":
        reply = handle_smalltalk_faq(user_message, history)

    else:
        reply = (
            "Mình chưa chắc ý bạn 🤔\n"
            "Bạn muốn **tìm thiết bị trong kho** hay **đề xuất theo fuzzy**?"
        )

    push_history(request.session, "bot", reply)
    print("[CHATBOT] Reply:", reply[:140])
    return JsonResponse({"reply": reply})


# ================== DEMO PAGES ==================

def fuzzy_last_page(request):
    last = request.session.get("last_fuzzy")
    return render(
        request,
        "fuzzy_last.html",
        {"last": last, "last_json": json.dumps(last or {}, ensure_ascii=False)},
    )


# ================== FUZZY LAST PAGES ==================

def fuzzy_last_page(request):
    """
    Render trang xem kết quả fuzzy gần nhất.
    Template chuẩn dùng: {{ last_json|json_script:"lastFuzzy" }}
    => last_json phải là dict (KHÔNG json.dumps).
    """
    last = request.session.get("last_fuzzy") or {}
    return render(
        request,
        "fuzzy_last.html",
        {
            "last": last,
            "last_json": last,  # ✅ dict để json_script hoạt động đúng
        },
    )


def api_fuzzy_last(request):
    """
    JSON endpoint: trả về last_fuzzy trong session.
    Dùng để debug nhanh và cho nút 'JSON last' trên UI.
    """
    last_json = request.session.get("last_fuzzy") or {}

    plot = (last_json.get("meta") or {}).get("plot") or {}
    criteria = (plot.get("criteria") or {}) if isinstance(plot, dict) else {}

    print(
        "[FUZZY][API_LAST] has_plot:",
        bool(plot),
        "criteria_keys:",
        list(criteria.keys()) if isinstance(criteria, dict) else criteria
    )

    return JsonResponse(last_json)

