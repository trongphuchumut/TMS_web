# holder_muontra/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

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
    """
    Form mượn holder:
    - Chỉ cho mượn khi holder đang ở trạng thái 'dang_su_dung'
    - Tạo 1 dòng HolderHistory trạng thái 'DANG_MUON'
    - Cập nhật trạng thái holder -> 'dang_duoc_muon'
    """
    holder = get_object_or_404(Holder, pk=holder_id)

    # 1. Chặn nếu holder không ở trạng thái sẵn sàng
    if holder.trang_thai_tai_san != "dang_su_dung":
        messages.error(
            request,
            f"Holder hiện đang ở trạng thái: {holder.get_trang_thai_tai_san_display()}, không thể mượn."
        )
        return redirect("holder_muontra:history_holder")

    # 2. Chặn nếu đã có phiếu mượn đang mở
    if HolderHistory.objects.filter(holder=holder, trang_thai="DANG_MUON").exists():
        messages.error(
            request,
            "Holder này đã có phiếu mượn đang mở, không thể mượn tiếp."
        )
        return redirect("holder_muontra:history_holder")

    if request.method == "POST":
        muc_dich = request.POST.get("muc_dich")
        du_an = request.POST.get("du_an", "").strip()
        mo_ta = request.POST.get("mo_ta", "").strip()

        if not muc_dich:
            messages.error(request, "Bạn chưa chọn mục đích mượn.")
            return redirect(request.path)

        history = HolderHistory.objects.create(
            holder=holder,
            muc_dich=muc_dich,
            du_an=du_an,
            mo_ta=mo_ta,
            trang_thai="DANG_MUON",  # khớp TRANG_THAI_CHOICES
            # thoi_gian_muon dùng auto_now_add
            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
            # mon_truoc sẽ được set trong save() nếu chưa có
        )

        # Cập nhật trạng thái holder -> đang được mượn
        holder.trang_thai_tai_san = "dang_duoc_muon"
        # Nếu holder.mon đang None, coi như 100
        if holder.mon is None:
            holder.mon = 100
        holder.save()

        messages.success(request, "Đã lưu phiếu mượn holder.")
        return redirect("holder_muontra:history_holder")

    context = {
        "holder": holder,
        "MUC_DICH_CHOICES": HolderHistory.MUC_DICH_CHOICES,
    }
    return render(request, "holder_borrow.html", context)


def return_for_holder(request, holder_id):
    """
    Form trả holder:
    - Chỉ xử lý nếu có 1 history đang 'DANG_MUON'
    - Tính thời lượng, giảm độ bền (mặc định mỗi lần ít nhất 10),
      nếu bảo trì xong thì reset về 100.
    """
    holder = get_object_or_404(Holder, pk=holder_id)

    # Phiếu mượn gần nhất (đang mượn)
    last_history = (
        HolderHistory.objects
        .filter(holder=holder, trang_thai="DANG_MUON")
        .order_by("-thoi_gian_muon")
        .first()
    )

    # Không có phiếu mượn đang mở -> chặn luôn
    if not last_history:
        messages.error(
            request,
            "Holder này hiện không có phiếu mượn đang mở, không thể trả."
        )
        return redirect("holder_muontra:history_holder")

    if request.method == "POST":
        ly_do = request.POST.get("ly_do_tra")
        mo_ta_tra = request.POST.get("mo_ta_tra", "").strip()

        thoi_gian_tra = timezone.now()
        thoi_gian_muon = last_history.thoi_gian_muon

        # Thời lượng (phút)
        delta = thoi_gian_tra - thoi_gian_muon
        thoi_luong_phut = int(delta.total_seconds() // 60)

        # ====== TÍNH GIẢM ĐỘ BỀN ======
        phut_moi_1_percent = 120  # ví dụ: 120 phút = giảm 1%
        giam_theo_thoi_gian = thoi_luong_phut / phut_moi_1_percent if phut_moi_1_percent > 0 else 0

        # Mỗi lần mượn/trả tối thiểu mất 10 độ bền
        giam_do_ben = max(10, giam_theo_thoi_gian)

        # Độ bền trước khi trả
        mon_truoc = holder.mon if holder.mon is not None else 100

        if ly_do == "bao_tri_xong":
            # Bảo trì xong thì hồi về 100%
            holder.mon = 100
        else:
            # Giảm độ bền, không cho nhỏ hơn 0
            holder.mon = max(0, mon_truoc - giam_do_ben)

        holder.trang_thai_tai_san = "dang_su_dung"
        holder.save()

        # Cập nhật phiếu mượn
        last_history.thoi_gian_tra = thoi_gian_tra
        last_history.thoi_luong_phut = thoi_luong_phut
        last_history.mon_truoc = mon_truoc
        last_history.mon_sau = holder.mon
        last_history.trang_thai = "DA_TRA"

        # Nếu model có các field này, thì set
        if hasattr(last_history, "ly_do_tra"):
            last_history.ly_do_tra = ly_do
        if hasattr(last_history, "mo_ta_tra"):
            last_history.mo_ta_tra = mo_ta_tra

        last_history.save()

        messages.success(request, "Đã cập nhật phiếu trả.")
        return redirect("holder_muontra:history_holder")

    # GET -> hiện form trả
    return render(request, "holder_return.html", {
        "holder": holder,
        "last_history": last_history,
    })
