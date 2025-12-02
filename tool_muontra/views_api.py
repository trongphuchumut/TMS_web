# tool_muontra/views_api.py
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from .models import ToolTransaction

MQTT_TX_TIMEOUT_SECONDS = getattr(settings, "MQTT_TX_TIMEOUT_SECONDS", 60)


def api_check_tool_tx(request, tx_id):
    """
    Trả về trạng thái giao dịch tool theo tx_id.
    Nếu PENDING quá lâu thì auto FAILED (timeout).
    """
    try:
        tx = ToolTransaction.objects.get(tx_id=tx_id)
    except ToolTransaction.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN"})

    if tx.trang_thai == "PENDING":
        start_time = tx.created_at
        if start_time:
            delta = timezone.now() - start_time
            age_sec = delta.total_seconds()
            if age_sec > MQTT_TX_TIMEOUT_SECONDS:
                tx.trang_thai = "FAILED"
                tx.ly_do_fail = "timeout"
                tx.save(update_fields=["trang_thai", "ly_do_fail"])

    return JsonResponse({
        "status": tx.trang_thai,
        "reason": tx.ly_do_fail or "",
        "ton_sau": tx.ton_sau,
    })
