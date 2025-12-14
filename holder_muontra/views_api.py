from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_GET
from .models import HolderHistory

MQTT_TX_TIMEOUT_SECONDS = getattr(settings, "MQTT_TX_TIMEOUT_SECONDS", 60)

# ✅ theo model Holder hiện tại của ông:
HOLDER_FREE = "dang_su_dung"       # label: Đang sẵn sàng (đang đặt tên ngược)
HOLDER_BUSY = "dang_duoc_muon"     # label: Đang được mượn


def _timeout_if_pending(h: HolderHistory) -> None:
    """Nếu PENDING quá lâu => FAILED (timeout)."""
    if h.trang_thai != "PENDING":
        return
    start_time = h.thoi_gian_muon or h.created_at
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
    - PENDING quá lâu -> FAILED(timeout)
    - Nếu nhận SUCCESS từ worker -> chốt DANG_MUON + set holder BUSY
    """
    try:
        h = HolderHistory.objects.select_related("holder").get(tx_id=tx_id)
    except HolderHistory.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN"})

    _timeout_if_pending(h)

    holder = h.holder

    # ✅ CHỈ khi giao dịch mượn đã "SUCCESS" thì mới chốt
    # (worker MQTT nên set SUCCESS khi nhận borrow_ok)
    if h.trang_thai == "SUCCESS":
        h.trang_thai = "DANG_MUON"
        h.save(update_fields=["trang_thai"])

        if holder and holder.trang_thai_tai_san != HOLDER_BUSY:
            holder.trang_thai_tai_san = HOLDER_BUSY
            holder.save(update_fields=["trang_thai_tai_san"])

    # ❌ PENDING/FAILED: không đụng holder
    return JsonResponse({
        "status": h.trang_thai,
        "reason": h.ly_do_fail or "",
    })


@require_GET
def api_check_return_tx(request, tx_id):
    """
    API check giao dịch TRẢ.
    - PENDING quá lâu -> FAILED(timeout)
    - Nếu nhận SUCCESS từ worker -> chốt DA_TRA + set holder FREE
    """
    try:
        h = HolderHistory.objects.select_related("holder").get(tx_id=tx_id)
    except HolderHistory.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN"})

    _timeout_if_pending(h)

    holder = h.holder

    # ✅ CHỈ khi giao dịch trả đã "SUCCESS" thì mới chốt
    # (worker MQTT nên set SUCCESS khi nhận return_ok)
    if h.trang_thai == "SUCCESS":
        h.trang_thai = "DA_TRA"
        h.thoi_gian_tra = timezone.now()
        h.save(update_fields=["trang_thai", "thoi_gian_tra"])

        if holder and holder.trang_thai_tai_san != HOLDER_FREE:
            holder.trang_thai_tai_san = HOLDER_FREE
            holder.save(update_fields=["trang_thai_tai_san"])

    # ❌ PENDING/FAILED: không đụng holder
    return JsonResponse({
        "status": h.trang_thai,
        "reason": h.ly_do_fail or "",
    })
