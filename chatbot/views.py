import json
import time
import uuid
import logging
from django.shortcuts import render

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .services.conversation.orchestrator import handle_message
from .services.conversation.state import get_fuzzy_last_for_debug

logger = logging.getLogger("chatbot")


@csrf_exempt
def chat_api(request):
    """
    Endpoint chính cho chatbot widget
    POST /chatbot/
    Payload:
      {
        message: string,
        model: string,
        explain_fuzzy: 0 | 1
      }
    """

    rid = uuid.uuid4().hex[:8]   # request id ngắn cho dễ đọc log
    t0 = time.perf_counter()

    logger.debug("=" * 80)
    logger.debug(f"[{rid}] CHATBOT REQUEST START")

    if request.method != "POST":
        logger.warning(f"[{rid}] Invalid method: {request.method}")
        return JsonResponse({"reply": "POST only."}, status=405)

    # ---------- Parse JSON ----------
    try:
        payload = json.loads(request.body or "{}")
    except Exception as e:
        logger.exception(f"[{rid}] JSON parse error")
        return JsonResponse({"reply": "Payload JSON không hợp lệ."}, status=400)

    message = (payload.get("message") or "").strip()
    model = (payload.get("model") or "gpt-oss:120b-cloud").strip()
    explain_fuzzy = int(payload.get("explain_fuzzy") or 0)

    logger.debug(f"[{rid}] Raw payload = {payload}")
    logger.debug(f"[{rid}] message_len={len(message)} model='{model}' explain_fuzzy={explain_fuzzy}")

    if not message:
        logger.warning(f"[{rid}] Empty message")
        return JsonResponse({"reply": "Bạn chưa nhập tin nhắn."}, status=400)

    if len(message) > 2000:
        logger.warning(f"[{rid}] Message too long ({len(message)} chars)")
        return JsonResponse(
            {"reply": "Tin nhắn quá dài, rút gọn dưới 2000 ký tự nhé."},
            status=400,
        )

    # ---------- Context cho orchestrator ----------
    ctx = {
        "model": model,
        "explain_fuzzy": bool(explain_fuzzy),
        "request_id": rid,   # truyền xuống để log xuyên suốt
    }

    # ---------- Handle message ----------
    try:
        logger.debug(f"[{rid}] Calling orchestrator.handle_message()")
        result = handle_message(request, message, ctx)
    except Exception:
        logger.exception(f"[{rid}] ERROR in handle_message")
        return JsonResponse(
            {"reply": "Có lỗi nội bộ khi xử lý yêu cầu. Xem terminal để debug."},
            status=500,
        )

    reply = result.get("reply", "OK")

    # ---------- Timing ----------
    dt_ms = (time.perf_counter() - t0) * 1000.0

    logger.debug(f"[{rid}] Reply length = {len(reply)} chars")
    logger.debug(f"[{rid}] Total time = {dt_ms:.2f} ms")
    logger.debug(f"[{rid}] CHATBOT REQUEST END")
    logger.debug("=" * 80)

    return JsonResponse({"reply": reply})


def fuzzy_last_view(request):
    """
    GET /chatbot/fuzzy/last/
    - Default: render UI charts (fuzzy_last.html)
    - ?raw=1 : return debug JSON as <pre>
    """
    logger.debug("[FUZZY_LAST] Request fuzzy last view")

    data = get_fuzzy_last_for_debug(request)

    if not data:
        logger.debug("[FUZZY_LAST] No fuzzy data in session")
        return HttpResponse(
            "<h3>Chưa có fuzzy result gần nhất.</h3>"
            "<p>Hãy chat một câu dạng đề xuất fuzzy trước "
            "(vd: <b>'khá rẻ nhưng cần bền'</b>), rồi mở lại trang này.</p>"
        )

    logger.debug("[FUZZY_LAST] Fuzzy data keys = %s", list(data.keys()))

    # Optional: keep old debug mode
    if request.GET.get("raw") in ("1", "true", "yes"):
        html = f"""
        <html>
        <head>
          <meta charset="utf-8">
          <title>Fuzzy Last (Debug)</title>
          <style>
            body {{
              font-family: system-ui, Segoe UI, Arial;
              padding: 24px;
              background: #f8fafc;
              color: #0f172a;
            }}
            .card {{
              background: #ffffff;
              border: 1px solid #e5e7eb;
              border-radius: 16px;
              padding: 16px;
              max-width: 1000px;
            }}
            pre {{
              background: #0b1220;
              color: #e5e7eb;
              padding: 12px;
              border-radius: 12px;
              overflow: auto;
              font-size: 13px;
              line-height: 1.4;
            }}
            .muted {{ color: #64748b; }}
          </style>
        </head>
        <body>
          <h2>Fuzzy gần nhất (Debug)</h2>
          <p class="muted">Dữ liệu lấy từ session – dùng để kiểm tra parse, fuzzy engine, rules.</p>
          <div class="card">
            <pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>
          </div>
        </body>
        </html>
        """
        return HttpResponse(html)

    # Render chart UI template
    last_json = json.dumps(data, ensure_ascii=False)

    return render(
        request,
        "fuzzy_last.html",     # đúng file template bạn đã làm
        {
            "last": data,
            "last_json": last_json,
        }
    )