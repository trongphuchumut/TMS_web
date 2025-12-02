from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q

from tool.models import Tool
from .models import ToolTransaction


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


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q

from tool.models import Tool
from .models import ToolTransaction

from iot_gateway.mqtt import send_tool_borrow, send_tool_return
import random


def tool_transaction_create(request, tool_id):
    """
    Tạo giao dịch TOOL theo hệ thống mới:
    - Không cập nhật tồn kho ngay.
    - Tạo PENDING record.
    - Gửi MQTT → chờ SUCCESS/FAILED.
    """
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

        # TON TRƯỚC = tồn kho hiện tại
        ton_truoc = tool.ton_kho

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
            ton_sau=ton_sau,   # cập nhật sau
            ma_du_an=ma_du_an,
            ghi_chu=ghi_chu,
            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
            trang_thai="PENDING",
            tx_id=tx_id,
        )

        # 3) Gửi MQTT
        # - EXPORT  → tool_borrow_start
        # - IMPORT, RETURN → tool_return_start

        locker = getattr(tool, "tu", "B")
        cell = getattr(tool, "ngan", 1)

        if loai == ToolTransaction.EXPORT:
            send_tool_borrow(
                locker=locker,
                cell=cell,
                user_rfid=user_rfid,
                tool_code=tool.ma_tool,
                qty=so_luong,
                tx_id=tx_id,
            )

        elif loai in (ToolTransaction.IMPORT, ToolTransaction.RETURN):
            send_tool_return(
                locker=locker,
                cell=cell,
                user_rfid=user_rfid,
                tool_code=tool.ma_tool,
                qty=so_luong,
                tx_id=tx_id,
            )

        else:
            messages.error(request, "Loại giao dịch không hợp lệ.")
            return redirect(request.path)

        # 4) Thông báo cho người dùng
        messages.success(
            request,
            "Giao dịch đã gửi đến tủ. Hệ thống đang chờ phản hồi (PENDING)."
        )

        return redirect("tool_muontra:history_tool")

    # GET → hiện form
    context = {
        "tool": tool,
        "loai_choices": ToolTransaction.LOAI_CHOICES,
    }
    return render(request, "tool_transaction_form.html", context)
