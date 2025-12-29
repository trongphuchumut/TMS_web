# holder_muontra/views.py

from __future__ import annotations

import random

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from iot_gateway.mqtt import send_holder_borrow, send_holder_return
from holder.models import Holder
from .models import HolderHistory

# ===================== CONFIG =====================
DEBUG_RFID = True  # bật log để soi RFID

# ✅ Chuẩn mới: "sẵn sàng" mới là trạng thái có thể mượn
HOLDER_FREE = "san_sang"
HOLDER_BUSY = "dang_duoc_muon"

# Nếu UserProfile của bạn nằm ở app khác, sửa import này cho đúng.
# Ví dụ: from accounts.models import UserProfile
try:
    from accounts.models import UserProfile  # <-- sửa cho đúng dự án bạn
except Exception:
    UserProfile = None


def _clean_rfid(x: str | None) -> str:
    """Chuẩn hóa RFID: bỏ ':' + uppercase + strip."""
    if not x:
        return ""
    return str(x).replace(":", "").strip().upper()


def _get_user_rfid_from_profile(request) -> str:
    """
    Lấy RFID của user đang đăng nhập từ UserProfile (DB).
    Trả về "" nếu không lấy được.
    """
    if not request.user.is_authenticated:
        return ""

    # Cách 1: nếu có model UserProfile thì query theo user
    if UserProfile is not None:
        try:
            p = UserProfile.objects.filter(user=request.user).only("rfid_code").first()
            return _clean_rfid(getattr(p, "rfid_code", "") if p else "")
        except Exception:
            pass

    # Cách 2: nếu bạn dùng OneToOneField có related_name
    # thử các tên phổ biến: userprofile / profile
    for attr in ("userprofile", "profile"):
        p = getattr(request.user, attr, None)
        if p is not None:
            return _clean_rfid(getattr(p, "rfid_code", "") or getattr(p, "rfid", "") or "")

    return ""


def _resolve_user_rfid(request) -> tuple[str, str]:
    """
    Resolve user_rfid theo thứ tự ưu tiên:
    1) DB profile (user đăng nhập)
    2) POST user_rfid (kiosk/manual)
    Trả về (rfid, source)
    """
    rfid_db = _get_user_rfid_from_profile(request)
    if rfid_db:
        return (rfid_db, "DB_PROFILE")

    rfid_post = _clean_rfid(request.POST.get("user_rfid"))
    if rfid_post:
        return (rfid_post, "POST_FORM")

    return ("", "MISSING")


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

    # ✅ CHUẨN MỚI: chỉ cho mượn khi holder ở trạng thái "sẵn sàng"
    if holder.trang_thai_tai_san != HOLDER_FREE:
        messages.error(
            request,
            f"Holder hiện đang ở trạng thái: {holder.get_trang_thai_tai_san_display()}, không thể mượn."
        )
        return redirect("holder_muontra:history_holder")

    # Chặn nếu đã có phiếu mượn đang mở
    if HolderHistory.objects.filter(holder=holder, trang_thai="DANG_MUON").exists():
        messages.error(request, "Holder này đã có phiếu mượn đang mở.")
        return redirect("holder_muontra:history_holder")

    if request.method == "POST":
        muc_dich = request.POST.get("muc_dich")
        du_an = request.POST.get("du_an", "").strip()
        mo_ta = request.POST.get("mo_ta", "").strip()

        # --- RFID resolve ---
        user_rfid, rfid_src = _resolve_user_rfid(request)
        if DEBUG_RFID:
            print("[HOLDER_BORROW] POST keys:", list(request.POST.keys()))
            print("[HOLDER_BORROW] user_rfid =", user_rfid, "source =", rfid_src)

        if not user_rfid:
            messages.error(request, "Chưa nhận được RFID người dùng (DB/Profile hoặc Form).")
            return redirect(request.path)

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
            user_rfid=user_rfid,
            holder_rfid_expected=_clean_rfid(holder.rfid),
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

    # ✅ chỉ cho trả khi holder đang được mượn
    if holder.trang_thai_tai_san != HOLDER_BUSY:
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

        # --- RFID resolve ---
        user_rfid, rfid_src = _resolve_user_rfid(request)
        if DEBUG_RFID:
            print("[HOLDER_RETURN] POST keys:", list(request.POST.keys()))
            print("[HOLDER_RETURN] user_rfid =", user_rfid, "source =", rfid_src)

        if not user_rfid:
            messages.error(request, "Chưa nhận được RFID người dùng (DB/Profile hoặc Form).")
            return redirect(request.path)

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
            user_rfid=user_rfid,
            holder_rfid_expected=_clean_rfid(holder.rfid),
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
