# holder_muontra/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from iot_gateway.mqtt import send_holder_borrow, send_holder_return
import random

from holder.models import Holder
from .models import HolderHistory


def history_holder(request):
    """
    Trang xem lịch sử mượn/trả holder + bộ lọc đơn giản.
    """
    q = request.GET.get("q", "").strip()
    muc_dich = request.GET.get("muc_dich", "")
    trang_thai = request.GET.get("trang_thai", "")

    histories = (
        HolderHistory.objects
        .select_related("holder", "nguoi_thuc_hien")
        .order_by("-thoi_gian_muon")
    )

    if q:
        histories = histories.filter(
            Q(holder__ma_noi_bo__icontains=q)
            | Q(holder__ten_thiet_bi__icontains=q)
            | Q(du_an__icontains=q)
            | Q(ma_noi_bo_snapshot__icontains=q)
            | Q(ten_thiet_bi_snapshot__icontains=q)
        )

    if muc_dich:
        histories = histories.filter(muc_dich=muc_dich)

    if trang_thai:
        histories = histories.filter(trang_thai=trang_thai)

    context = {
        "histories": histories,
        "q": q,
        "muc_dich": muc_dich,
        "trang_thai": trang_thai,
        "MUC_DICH_CHOICES": HolderHistory.MUC_DICH_CHOICES,
        "TRANG_THAI_CHOICES": HolderHistory.TRANG_THAI_CHOICES,
    }
    return render(request, "holder_history.html", context)


def borrow_for_holder(request, holder_id):
    holder = get_object_or_404(Holder, pk=holder_id)

    # Không cho mượn nếu holder không sẵn sàng
    if holder.trang_thai_tai_san != "dang_su_dung":
        messages.error(
            request,
            f"Holder hiện đang ở trạng thái: {holder.get_trang_thai_tai_san_display()}, không thể mượn."
        )
        return redirect("holder_muontra:history_holder")

    # Nếu đang có phiếu mượn đang mở -> chặn
    if HolderHistory.objects.filter(holder=holder, trang_thai="DANG_MUON").exists():
        messages.error(request, "Holder này đã có phiếu mượn đang mở.")
        return redirect("holder_muontra:history_holder")

    if request.method == "POST":
        muc_dich = request.POST.get("muc_dich")
        du_an = request.POST.get("du_an", "").strip()
        mo_ta = request.POST.get("mo_ta", "").strip()
        user_rfid = request.POST.get("user_rfid", "U000").strip()

        if not muc_dich:
            messages.error(request, "Bạn chưa chọn mục đích mượn.")
            return redirect(request.path)

        # ======== 1) GENERATE tx_id ========
        tx_id = random.randint(1, 999_999_999)

        # ======== 2) TẠO LỊCH SỬ DẠNG PENDING ========
        history = HolderHistory.objects.create(
            holder=holder,
            muc_dich=muc_dich,
            du_an=du_an,
            mo_ta=mo_ta,
            trang_thai="PENDING",       # CHỜ TỦ PHẢN HỒI
            tx_id=tx_id,                # GẮN TX_ID
            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
        )

        # ======== 3) Gửi lệnh MQTT ========
        locker = holder.tu or "A"
        cell = holder.ngan or 1
        holder_rfid = holder.ma_noi_bo


        send_holder_borrow(
            locker=locker,
            cell=cell,
            user_rfid=user_rfid,
            holder_rfid_expected=holder_rfid,
            tx_id=tx_id,
        )

        # ======== 4) BÁO NGƯỜI DÙNG ========
        messages.success(
            request,
            "Đã gửi yêu cầu mượn holder. Đang chờ tủ phản hồi (PENDING)."
        )
        return redirect("holder_muontra:wait_holder", tx_id=tx_id)

    context = {
        "holder": holder,
        "MUC_DICH_CHOICES": HolderHistory.MUC_DICH_CHOICES,
    }
    return render(request, "holder_borrow.html", context)


def return_for_holder(request, holder_id):
    holder = get_object_or_404(Holder, pk=holder_id)

    last_history = (
        HolderHistory.objects
        .filter(holder=holder, trang_thai="DANG_MUON")
        .order_by("-thoi_gian_muon")
        .first()
    )

    if not last_history:
        messages.error(request, "Không có phiếu mượn đang mở.")
        return redirect("holder_muontra:history_holder")

    if request.method == "POST":
        ly_do = request.POST.get("ly_do_tra", "")
        mo_ta_tra = request.POST.get("mo_ta_tra", "").strip()
        user_rfid = request.POST.get("user_rfid", "U000").strip()

        # ======== 1) tx_id ========
        tx_id = random.randint(1, 999_999_999)

        # ======== 2) Tạo LỊCH SỬ trả PENDING ========
        # thay vì sửa last_history, ta tạo 1 dòng mới
        history_return = HolderHistory.objects.create(
            holder=holder,
            muc_dich=last_history.muc_dich,
            du_an=last_history.du_an,
            mo_ta=mo_ta_tra,
            trang_thai="PENDING",
            tx_id=tx_id,
            nguoi_thuc_hien=(
                request.user if request.user.is_authenticated else None
            ),
            ly_do_tra=ly_do if hasattr(HolderHistory, "ly_do_tra") else "",
        )

        # ======== 3) Gửi MQTT ========
        locker = holder.tu or "A"
        cell = holder.ngan or 1
        holder_rfid = holder.ma_noi_bo


        send_holder_return(
            locker=locker,
            cell=cell,
            user_rfid=user_rfid,
            holder_rfid_expected=holder_rfid,
            tx_id=tx_id,
        )

        messages.success(request, "Đã yêu cầu trả holder. Đang chờ tủ xử lý (PENDING).")
        return redirect("holder_muontra:wait_holder", tx_id=tx_id)

    return render(request, "holder_return.html", {
        "holder": holder,
        "last_history": last_history,
    })
def wait_holder(request, tx_id):
    """
    Trang chờ tủ xử lý giao dịch holder. JS sẽ gọi API để kiểm tra trạng thái.
    """
    return render(request, "holder_wait.html", {"tx_id": tx_id})
