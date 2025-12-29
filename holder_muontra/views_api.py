# holder_muontra/views_api.py  (hoặc file bạn đang để api_check_*)

from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_GET

from .models import HolderHistory

MQTT_TX_TIMEOUT_SECONDS = getattr(settings, "MQTT_TX_TIMEOUT_SECONDS", 60)


def _timeout_if_pending(h: HolderHistory) -> None:
    """Nếu PENDING quá lâu => FAILED (timeout)."""
    if h.trang_thai != "PENDING":
        return
    start_time = h.thoi_gian_muon or getattr(h, "created_at", None)
    if not start_time:
        return
    age_sec = (timezone.now() - start_time).total_seconds()
    if age_sec > MQTT_TX_TIMEOUT_SECONDS:
        h.trang_thai = "FAILED"
        h.ly_do_fail = "timeout"
        h.save(update_fields=["trang_thai", "ly_do_fail"])


@require_GET
def api_check_borrow_tx(request, tx_id):
    """
    API check giao dịch MƯỢN.
    Worker MQTT sẽ:
      - phiếu mượn: PENDING -> DANG_MUON (hoặc FAILED)
      - holder: san_sang -> dang_duoc_muon
    API chỉ: timeout + trả status.
    """
    try:
        h = HolderHistory.objects.get(tx_id=tx_id)
    except HolderHistory.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN", "reason": "tx_not_found"})

    _timeout_if_pending(h)

    return JsonResponse({
        "status": h.trang_thai,          # PENDING / DANG_MUON / FAILED ...
        "reason": h.ly_do_fail or "",
    })


@require_GET
def api_check_return_tx(request, tx_id):
    """
    API check giao dịch TRẢ.
    Worker MQTT sẽ:
      - phiếu trả: PENDING -> SUCCESS (hoặc FAILED)
      - phiếu mượn đang mở: DANG_MUON -> DA_TRA
      - holder: dang_duoc_muon -> san_sang
    API chỉ: timeout + trả status.
    """
    try:
        h = HolderHistory.objects.get(tx_id=tx_id)
    except HolderHistory.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN", "reason": "tx_not_found"})

    _timeout_if_pending(h)

    return JsonResponse({
        "status": h.trang_thai,          # PENDING / SUCCESS / FAILED ...
        "reason": h.ly_do_fail or "",
    })
