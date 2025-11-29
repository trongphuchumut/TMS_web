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


def tool_transaction_create(request, tool_id):
    """
    Tạo 1 giao dịch tool – đúng với model hiện tại (EXPORT, IMPORT, RETURN).
    """
    tool = get_object_or_404(Tool, pk=tool_id)

    if request.method == "POST":
        print("DEBUG POST tool_transaction_create")  # để bạn thấy trên console

        # Lấy dữ liệu form
        loai = request.POST.get("loai")
        so_luong_raw = request.POST.get("so_luong")
        ma_du_an = request.POST.get("ma_du_an", "").strip()
        ghi_chu = request.POST.get("ghi_chu", "").strip()

        # Validate số lượng
        try:
            so_luong = int(so_luong_raw)
        except (TypeError, ValueError):
            messages.error(request, "Số lượng không hợp lệ.")
            return redirect(request.path)

        if so_luong <= 0:
            messages.error(request, "Số lượng phải > 0.")
            return redirect(request.path)

        # ✅ DÙNG ĐÚNG FIELD TỒN KHO
        ton_truoc = tool.ton_kho

        # Các loại cộng tồn kho (IMPORT, RETURN)
        loai_cong = {
            ToolTransaction.IMPORT,
            ToolTransaction.RETURN,
        }

        if loai in loai_cong:
            ton_sau = ton_truoc + so_luong
        else:
            # EXPORT → trừ tồn
            ton_sau = ton_truoc - so_luong
            if ton_sau < 0:
                messages.error(request, "Không đủ tồn kho để xuất.")
                return redirect(request.path)

        # Lưu transaction
        ToolTransaction.objects.create(
            loai=loai,
            tool=tool,
            so_luong=so_luong,
            ton_truoc=ton_truoc,
            ton_sau=ton_sau,
            ma_du_an=ma_du_an,
            ghi_chu=ghi_chu,
            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
        )

        # Cập nhật tồn kho thực
        tool.ton_kho = ton_sau
        tool.save(update_fields=["ton_kho"])

        messages.success(request, "Lưu giao dịch thành công.")
        return redirect("tool_muontra:history_tool")

    # GET → hiện form
    context = {
        "tool": tool,
        "loai_choices": ToolTransaction.LOAI_CHOICES,
    }
    return render(request, "tool_transaction_form.html", context)
