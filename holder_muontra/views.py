from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from iot_gateway.mqtt import send_holder_borrow, send_holder_return
import random

from holder.models import Holder
from .models import HolderHistory


# ======================================================
#  LỊCH SỬ HOLDER
# ======================================================
def history_holder(request):
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
        )

    if muc_dich:
        histories = histories.filter(muc_dich=muc_dich)

    if trang_thai:
        histories = histories.filter(trang_thai=trang_thai)

    return render(request, "holder_history.html", {
        "histories": histories,
        "q": q,
        "muc_dich": muc_dich,
        "trang_thai": trang_thai,
        "MUC_DICH_CHOICES": HolderHistory.MUC_DICH_CHOICES,
        "TRANG_THAI_CHOICES": HolderHistory.TRANG_THAI_CHOICES,
    })


# ======================================================
#  MƯỢN HOLDER
# ======================================================
def borrow_for_holder(request, holder_id):
    holder = get_object_or_404(Holder, pk=holder_id)

    if holder.trang_thai_tai_san != "dang_su_dung":
        messages.error(
            request,
            f"Holder hiện đang ở trạng thái: {holder.get_trang_thai_tai_san_display()}, không thể mượn."
        )
        return redirect("holder_muontra:history_holder")

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

        tx_id = random.randint(1, 999_999_999)

        HolderHistory.objects.create(
            holder=holder,
            muc_dich=muc_dich,
            du_an=du_an,
            mo_ta=mo_ta,
            trang_thai="PENDING",
            tx_id=tx_id,
            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
        )

        send_holder_borrow(
            locker=holder.tu or "A",
            cell=holder.ngan or 1,
            user_rfid=user_rfid.replace(":", "").upper(),
            holder_rfid_expected=(holder.rfid or "").replace(":", "").upper(),
            tx_id=tx_id,
        )

        messages.success(request, "Đã gửi yêu cầu mượn holder. Đang chờ tủ phản hồi.")
        return redirect("holder_muontra:wait_holder", tx_id=tx_id, mode="borrow")

    return render(request, "holder_borrow.html", {
        "holder": holder,
        "MUC_DICH_CHOICES": HolderHistory.MUC_DICH_CHOICES,
    })


# ======================================================
#  TRẢ HOLDER
# ======================================================
def return_for_holder(request, holder_id):
    holder = get_object_or_404(Holder, pk=holder_id)

    if holder.trang_thai_tai_san != "dang_duoc_muon":
        messages.error(request, "Holder hiện không ở trạng thái đang được mượn.")
        return redirect("holder_muontra:history_holder")

    borrow_ticket = (
        HolderHistory.objects
        .filter(holder=holder, trang_thai="DANG_MUON")
        .order_by("-thoi_gian_muon")
        .first()
    )

    if not borrow_ticket:
        messages.error(request, "Không tìm thấy phiếu mượn đang mở.")
        return redirect("holder_muontra:history_holder")

    if request.method == "POST":
        mo_ta_tra = request.POST.get("mo_ta_tra", "").strip()
        user_rfid = request.POST.get("user_rfid", "U000").strip()

        mon_sau_raw = request.POST.get("mon_sau", "").strip()
        mon_sau = None
        if mon_sau_raw:
            try:
                mon_sau = max(0, min(100, int(float(mon_sau_raw))))
            except Exception:
                messages.error(request, "Mức mòn không hợp lệ (0–100).")
                return redirect(request.path)

        tx_id = random.randint(1, 999_999_999)

        create_kwargs = dict(
            holder=holder,
            muc_dich=borrow_ticket.muc_dich,
            du_an=borrow_ticket.du_an,
            mo_ta=mo_ta_tra,
            trang_thai="PENDING",
            tx_id=tx_id,
            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
        )

        if hasattr(HolderHistory, "mon_truoc"):
            create_kwargs["mon_truoc"] = holder.mon
        if hasattr(HolderHistory, "mon_sau"):
            create_kwargs["mon_sau"] = mon_sau

        HolderHistory.objects.create(**create_kwargs)

        send_holder_return(
            locker=holder.tu or "A",
            cell=holder.ngan or 1,
            user_rfid=user_rfid.replace(":", "").upper(),
            holder_rfid_expected=(holder.rfid or "").replace(":", "").upper(),
            tx_id=tx_id,
        )

        messages.success(request, "Đã gửi yêu cầu trả holder. Đang chờ tủ xử lý.")
        return redirect("holder_muontra:wait_holder", tx_id=tx_id, mode="return")

    return render(request, "holder_return.html", {
        "holder": holder,
        "last_history": borrow_ticket,
    })


# ======================================================
#  TRANG CHỜ MQTT
# ======================================================
def wait_holder(request, tx_id, mode):
    return render(request, "holder_wait.html", {
        "tx_id": tx_id,
        "mode": mode,
    })
