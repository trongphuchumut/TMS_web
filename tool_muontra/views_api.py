# tool_muontra/views_api.py
import json, random, re

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from iot_gateway.mqtt import send_tool_borrow, send_tool_return
from tool.models import Tool
from .models import ToolTransaction

MQTT_TX_TIMEOUT_SECONDS = getattr(settings, "MQTT_TX_TIMEOUT_SECONDS", 60)


def normalize_locker_cell(locker, cell):
    if isinstance(cell, str):
        m = re.fullmatch(r"([A-Za-z])\s*(\d+)", cell.strip())
        if m:
            return m.group(1).upper(), int(m.group(2))
    return (locker or "B"), int(cell)


def _create_pending_tx(*, tool, loai, qty, user, user_rfid, ma_du_an="", ghi_chu=""):
    """
    NOTE: tool nên đã được select_for_update ở ngoài (nếu cần).
    user_rfid hiện chưa lưu vào DB (model chưa có field) nên chỉ dùng cho MQTT.
    """
    ton_truoc = tool.ton_kho
    tx_id = random.randint(1, 999_999_999)

    tran = ToolTransaction.objects.create(
        loai=loai,
        tool=tool,
        so_luong=qty,
        ton_truoc=ton_truoc,
        ton_sau=ton_truoc,  # sẽ cập nhật khi SUCCESS
        ma_du_an=ma_du_an.strip(),
        ghi_chu=ghi_chu.strip(),
        nguoi_thuc_hien=user if (user and user.is_authenticated) else None,
        trang_thai="PENDING",
        tx_id=tx_id,
        ly_do_fail="",
    )
    return tran


def _parse_payload(request):
    # hỗ trợ cả JSON body lẫn form-data
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return {}
    return request.POST


@require_POST
def api_tool_export(request, tool_id):
    """Xin xuất tool (EXPORT) -> gửi MQTT borrow."""
    data = _parse_payload(request)

    try:
        qty = int(data.get("so_luong", 0))
    except Exception:
        return JsonResponse({"ok": False, "error": "so_luong_invalid"}, status=400)
    if qty <= 0:
        return JsonResponse({"ok": False, "error": "so_luong_must_be_gt_0"}, status=400)

    user_rfid = (data.get("user_rfid") or "U000").strip()
    ma_du_an = data.get("ma_du_an", "")
    ghi_chu = data.get("ghi_chu", "")

    with transaction.atomic():
        # lock tool để check tồn kho chính xác + chống 2 request đồng thời
        tool = Tool.objects.select_for_update().get(pk=tool_id)

        # ✅ CHẶN XUẤT VƯỢT TỒN
        if qty > tool.ton_kho:
            return JsonResponse(
                {"ok": False, "error": "insufficient_stock", "ton_kho": tool.ton_kho},
                status=409
            )

        tran = _create_pending_tx(
            tool=tool,
            loai=ToolTransaction.EXPORT,
            qty=qty,
            user=request.user,
            user_rfid=user_rfid,
            ma_du_an=ma_du_an,
            ghi_chu=ghi_chu,
        )

        locker, cell = normalize_locker_cell(getattr(tool, "tu", None), getattr(tool, "ngan", 1))

        # gửi MQTT sau khi DB commit để tránh tạo “tx ma” khi rollback
        transaction.on_commit(lambda: send_tool_borrow(
            locker=locker,
            cell=cell,
            user_rfid=user_rfid,
            tool_code=tool.ma_tool,
            qty=qty,
            tx_id=tran.tx_id,
        ))

    return JsonResponse({"ok": True, "tx_id": tran.tx_id, "status": "PENDING"})


@require_POST
def api_tool_import(request, tool_id):
    """Xin nhập tool (IMPORT) -> gửi MQTT return."""
    data = _parse_payload(request)

    try:
        qty = int(data.get("so_luong", 0))
    except Exception:
        return JsonResponse({"ok": False, "error": "so_luong_invalid"}, status=400)
    if qty <= 0:
        return JsonResponse({"ok": False, "error": "so_luong_must_be_gt_0"}, status=400)

    user_rfid = (data.get("user_rfid") or "U000").strip()
    ma_du_an = data.get("ma_du_an", "")
    ghi_chu = data.get("ghi_chu", "")

    with transaction.atomic():
        tool = Tool.objects.select_for_update().get(pk=tool_id)

        tran = _create_pending_tx(
            tool=tool,
            loai=ToolTransaction.IMPORT,
            qty=qty,
            user=request.user,
            user_rfid=user_rfid,
            ma_du_an=ma_du_an,
            ghi_chu=ghi_chu,
        )

        locker, cell = normalize_locker_cell(getattr(tool, "tu", None), getattr(tool, "ngan", 1))
        transaction.on_commit(lambda: send_tool_return(
            locker=locker,
            cell=cell,
            user_rfid=user_rfid,
            tool_code=tool.ma_tool,
            qty=qty,
            tx_id=tran.tx_id,
        ))

    return JsonResponse({"ok": True, "tx_id": tran.tx_id, "status": "PENDING"})


@require_POST
def api_tool_return(request, tool_id):
    """RETURN nếu bạn muốn tách riêng khác IMPORT; nếu không cần, có thể bỏ endpoint này."""
    data = _parse_payload(request)

    try:
        qty = int(data.get("so_luong", 0))
    except Exception:
        return JsonResponse({"ok": False, "error": "so_luong_invalid"}, status=400)
    if qty <= 0:
        return JsonResponse({"ok": False, "error": "so_luong_must_be_gt_0"}, status=400)

    user_rfid = (data.get("user_rfid") or "U000").strip()
    ma_du_an = data.get("ma_du_an", "")
    ghi_chu = data.get("ghi_chu", "")

    with transaction.atomic():
        tool = Tool.objects.select_for_update().get(pk=tool_id)

        tran = _create_pending_tx(
            tool=tool,
            loai=ToolTransaction.RETURN,
            qty=qty,
            user=request.user,
            user_rfid=user_rfid,
            ma_du_an=ma_du_an,
            ghi_chu=ghi_chu,
        )

        locker, cell = normalize_locker_cell(getattr(tool, "tu", None), getattr(tool, "ngan", 1))
        transaction.on_commit(lambda: send_tool_return(
            locker=locker,
            cell=cell,
            user_rfid=user_rfid,
            tool_code=tool.ma_tool,
            qty=qty,
            tx_id=tran.tx_id,
        ))

    return JsonResponse({"ok": True, "tx_id": tran.tx_id, "status": "PENDING"})


def api_check_tool_tx(request, tx_id):
    """Poll trạng thái; nếu timeout thì FAILED."""
    try:
        tx = ToolTransaction.objects.select_related("tool").get(tx_id=tx_id)
    except ToolTransaction.DoesNotExist:
        return JsonResponse({"status": "UNKNOWN"})

    if tx.trang_thai == "PENDING" and tx.created_at:
        age_sec = (timezone.now() - tx.created_at).total_seconds()
        if age_sec > MQTT_TX_TIMEOUT_SECONDS:
            tx.trang_thai = "FAILED"
            tx.ly_do_fail = "timeout"
            tx.save(update_fields=["trang_thai", "ly_do_fail"])

    return JsonResponse({
        "status": tx.trang_thai,
        "reason": tx.ly_do_fail or "",
        "ton_truoc": tx.ton_truoc,
        "ton_sau": tx.ton_sau,
        "tool_id": tx.tool_id,
    })
