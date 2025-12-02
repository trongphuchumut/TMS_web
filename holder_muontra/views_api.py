from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from .models import HolderHistory
MQTT_TX_TIMEOUT_SECONDS = getattr(settings, "MQTT_TX_TIMEOUT_SECONDS", 60)


def api_check_holder_tx(request, tx_id):
    """
    Trả về trạng thái giao dịch holder theo tx_id.
    Nếu PENDING quá lâu thì auto chuyển sang FAILED (timeout).
    """
    try:
        h = HolderHistory.objects.get(tx_id=tx_id)
    except HolderHistory.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN"})

    # Nếu vẫn đang PENDING -> kiểm tra timeout
    if h.trang_thai == "PENDING":
        # Lấy thời điểm bắt đầu: thoi_gian_muon (hoặc created_at nếu bạn có)
        start_time = h.thoi_gian_muon or h.created_at
        if start_time:
            delta = timezone.now() - start_time
            age_sec = delta.total_seconds()
            if age_sec > MQTT_TX_TIMEOUT_SECONDS:
                # Quá thời gian chờ -> coi như thất bại
                h.trang_thai = "FAILED"
                h.ly_do_fail = "timeout"
                h.save(update_fields=["trang_thai", "ly_do_fail"])

    return JsonResponse({
        "status": h.trang_thai,
        "reason": h.ly_do_fail or "",
    })