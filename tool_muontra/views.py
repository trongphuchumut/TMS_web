# tool_muontra/views.py
from __future__ import annotations

import random
import re

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from iot_gateway.mqtt import send_tool_borrow, send_tool_return
from tool.models import Tool
from .models import ToolTransaction


# =========================================================
# Helpers
# =========================================================
def normalize_locker_cell(locker, cell):
    """
    Nhận:
      - locker="B", cell="1"   -> ("B", 1)
      - locker="B", cell="B1"  -> ("B", 1)
      - locker=None, cell="B1" -> ("B", 1)
    """
    if isinstance(cell, str):
        m = re.fullmatch(r"([A-Za-z])\s*(\d+)", cell.strip())
        if m:
            return m.group(1).upper(), int(m.group(2))
    # fallback
    locker = (locker or "B")
    return locker, int(cell)


# =========================================================
# Views
# =========================================================
def history_tool(request):
    """
    Lịch sử giao dịch tool.
    """
    q = request.GET.get("q", "").strip()
    loai = request.GET.get("loai", "").strip()

    transactions = ToolTransaction.objects.select_related("tool", "nguoi_thuc_hien")

    if q:
        transactions = transactions.filter(
            Q(tool__ma_tool__icontains=q)
            | Q(tool__ten_tool__icontains=q)
            | Q(ma_du_an__icontains=q)
            | Q(ghi_chu__icontains=q)
        )

    if loai:
        transactions = transactions.filter(loai=loai)

    transactions = transactions.order_by("-created_at")[:500]

    context = {
        "transactions": transactions,
        "q": q,
        "loai": loai,
        "loai_choices": ToolTransaction.LOAI_CHOICES,
    }
    return render(request, "tool_history.html", context)


def tool_transaction_create(request, tool_id):
    """
    Tạo giao dịch TOOL theo hệ thống mới:
    - Không cập nhật tồn kho ngay.
    - Tạo PENDING record.
    - Gửi MQTT → chờ SUCCESS/FAILED (mqtt_worker cập nhật).
    - Sau khi POST thành công → chuyển sang màn hình chờ.

    FIX: Chặn xuất vượt tồn (ví dụ tồn 13 mà nhập 14).
         Đồng thời lock Tool row để tránh 2 người bấm cùng lúc.
    """
    # GET vẫn cần tool để render form
    tool = get_object_or_404(Tool, pk=tool_id)

    if request.method == "POST":
        loai = request.POST.get("loai")
        so_luong_raw = request.POST.get("so_luong")
        ma_du_an = request.POST.get("ma_du_an", "").strip()
        ghi_chu = request.POST.get("ghi_chu", "").strip()
        user_rfid = request.POST.get("user_rfid", "U000").strip()

        # Validate số lượng
        try:
            so_luong = int(so_luong_raw)
        except Exception:
            messages.error(request, "Số lượng không hợp lệ.")
            return redirect(request.path)

        if so_luong <= 0:
            messages.error(request, "Số lượng phải > 0.")
            return redirect(request.path)

        # ======= ATOMIC + LOCK để tránh race condition =======
        with transaction.atomic():
            # lock row tool để mọi check tồn kho là “đúng tại thời điểm tạo đơn”
            tool = Tool.objects.select_for_update().get(pk=tool_id)

            # TON TRƯỚC = tồn kho hiện tại
            ton_truoc = tool.ton_kho

            # ✅ CHẶN XUẤT VƯỢT TỒN (đây là fix bạn cần)
            if loai == ToolTransaction.EXPORT and so_luong > ton_truoc:
                messages.error(
                    request,
                    f"Không thể xuất {so_luong}. Tồn kho hiện tại chỉ còn {ton_truoc}."
                )
                return redirect(request.path)

            # TON SAU = chưa biết (chỉ cập nhật sau khi SUCCESS)
            ton_sau = ton_truoc

            # 1) Generate TX ID cho MQTT
            tx_id = random.randint(1, 999_999_999)

            # 2) Tạo transaction dạng PENDING
            tran = ToolTransaction.objects.create(
                loai=loai,
                tool=tool,
                so_luong=so_luong,
                ton_truoc=ton_truoc,
                ton_sau=ton_sau,  # cập nhật sau khi SUCCESS
                ma_du_an=ma_du_an,
                ghi_chu=ghi_chu,
                nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
                trang_thai="PENDING",
                tx_id=tx_id,
            )

        # ======= Hết atomic: gửi MQTT ở ngoài để tránh giữ lock quá lâu =======

        locker_raw = getattr(tool, "tu", None)
        cell_raw = getattr(tool, "ngan", 1)
        locker, cell = normalize_locker_cell(locker_raw, cell_raw)

        if loai == ToolTransaction.EXPORT:
            send_tool_borrow(
                locker=locker,
                cell=cell,
                user_rfid=user_rfid,
                tool_code=tool.ma_tool,
                qty=so_luong,
                tx_id=tran.tx_id,
            )
        elif loai in (ToolTransaction.IMPORT, ToolTransaction.RETURN):
            send_tool_return(
                locker=locker,
                cell=cell,
                user_rfid=user_rfid,
                tool_code=tool.ma_tool,
                qty=so_luong,
                tx_id=tran.tx_id,
            )
        else:
            messages.error(request, "Loại giao dịch không hợp lệ.")
            # rollback kiểu “logic”: đánh fail luôn cho dễ nhìn
            tran.trang_thai = "FAILED"
            tran.ly_do_fail = "invalid_loai"
            tran.save(update_fields=["trang_thai", "ly_do_fail"])
            return redirect(request.path)

        messages.success(request, "Đã gửi lệnh đến tủ. Đang chờ phản hồi...")
        return redirect("tool_muontra:tool_transaction_wait", tx_id=tran.tx_id)

    # GET → hiện form
    context = {
        "tool": tool,
        "loai_choices": ToolTransaction.LOAI_CHOICES,
    }
    return render(request, "tool_transaction_form.html", context)


def tool_transaction_wait(request, tx_id: int):
    """
    Màn hình chờ phản hồi cho Tool (tận dụng holder_wait.html).
    JS trong template sẽ poll api_check_tool_tx.
    """
    tx = ToolTransaction.objects.select_related("tool").filter(tx_id=tx_id).first()
    if not tx:
        raise Http404("TX not found")

    return render(request, "holder_wait.html", {
        "tx_id": tx_id,
        "mode": "tool",
    })
