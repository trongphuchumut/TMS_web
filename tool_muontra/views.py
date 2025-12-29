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

# ===================== CONFIG =====================
DEBUG_RFID = True  # bật log để soi RFID

# SỬA IMPORT NÀY cho đúng app/model UserProfile của bạn
# Ví dụ: from users.models import UserProfile
try:
    from accounts.models import UserProfile  # <-- đổi đúng chỗ bạn đang đặt UserProfile
except Exception:
    UserProfile = None


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


def _clean_rfid(x: str | None) -> str:
    if not x:
        return ""
    return str(x).replace(":", "").strip().upper()


def _get_user_rfid_from_profile(request) -> str:
    """
    Lấy RFID theo user đang login từ DB UserProfile.
    Trả về "" nếu không có.
    """
    if not request.user.is_authenticated:
        return ""

    # Cách 1: query model UserProfile (nếu import được)
    if UserProfile is not None:
        try:
            p = UserProfile.objects.filter(user=request.user).only("rfid_code").first()
            return _clean_rfid(getattr(p, "rfid_code", "") if p else "")
        except Exception:
            pass

    # Cách 2: thử OneToOne related_name phổ biến
    for attr in ("userprofile", "profile"):
        p = getattr(request.user, attr, None)
        if p is not None:
            return _clean_rfid(getattr(p, "rfid_code", "") or getattr(p, "rfid", "") or "")

    return ""


def _resolve_user_rfid(request) -> tuple[str, str]:
    """
    1) DB profile (đăng nhập)
    2) POST form (kiosk/manual)
    """
    rfid_db = _get_user_rfid_from_profile(request)
    if rfid_db:
        return (rfid_db, "DB_PROFILE")

    rfid_post = _clean_rfid(request.POST.get("user_rfid"))
    if rfid_post:
        return (rfid_post, "POST_FORM")

    return ("", "MISSING")


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

    FIX RFID: ưu tiên lấy RFID từ UserProfile (DB), nếu không có thì lấy từ POST.
             Không còn fallback U000 âm thầm.
    """
    tool = get_object_or_404(Tool, pk=tool_id)

    if request.method == "POST":
        loai = request.POST.get("loai")
        so_luong_raw = request.POST.get("so_luong")
        ma_du_an = request.POST.get("ma_du_an", "").strip()
        ghi_chu = request.POST.get("ghi_chu", "").strip()

        # ✅ resolve RFID đúng nguồn
        user_rfid, rfid_src = _resolve_user_rfid(request)
        if DEBUG_RFID:
            print("[TOOL_TX] POST keys:", list(request.POST.keys()))
            print("[TOOL_TX] user_rfid =", user_rfid, "source =", rfid_src)

        if not user_rfid:
            messages.error(request, "Chưa nhận được RFID người dùng (DB/Profile hoặc Form).")
            return redirect(request.path)

        # Validate số lượng
        try:
            so_luong = int(so_luong_raw)
        except Exception:
            messages.error(request, "Số lượng không hợp lệ.")
            return redirect(request.path)

        if so_luong <= 0:
            messages.error(request, "Số lượng phải > 0.")
            return redirect(request.path)

        with transaction.atomic():
            tool = Tool.objects.select_for_update().get(pk=tool_id)
            ton_truoc = tool.ton_kho

            if loai == ToolTransaction.EXPORT and so_luong > ton_truoc:
                messages.error(
                    request,
                    f"Không thể xuất {so_luong}. Tồn kho hiện tại chỉ còn {ton_truoc}."
                )
                return redirect(request.path)

            ton_sau = ton_truoc
            tx_id = random.randint(1, 999_999_999)

            tran = ToolTransaction.objects.create(
                loai=loai,
                tool=tool,
                so_luong=so_luong,
                ton_truoc=ton_truoc,
                ton_sau=ton_sau,
                ma_du_an=ma_du_an,
                ghi_chu=ghi_chu,
                nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
                trang_thai="PENDING",
                tx_id=tx_id,
            )

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
            tran.trang_thai = "FAILED"
            tran.ly_do_fail = "invalid_loai"
            tran.save(update_fields=["trang_thai", "ly_do_fail"])
            return redirect(request.path)

        messages.success(request, "Đã gửi lệnh đến tủ. Đang chờ phản hồi...")
        return redirect("tool_muontra:tool_transaction_wait", tx_id=tran.tx_id)

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
