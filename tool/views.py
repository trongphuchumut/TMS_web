from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from .models import Tool
# nếu sau này có ToolIssueHistory thì import thêm ở đây:
# from .models import ToolIssueHistory


def tool_profile(request, pk):
    tool = get_object_or_404(Tool, pk=pk)

    # ========== LỊCH SỬ CẤP PHÁT (tạm để trống nếu chưa có model) ==========
    try:
        # nếu bạn định nghĩa ToolIssueHistory với related_name="issue_history"
        history_list = tool.issue_history.all().order_by("-ngay")[:10]
    except AttributeError:
        history_list = []

    # ========== TÍNH % TỒN KHO ĐỂ VẼ THANH ==========
    stock_percent = 0
    if tool.ton_kho is not None:
        # lấy mốc so sánh là mức cảnh báo, nếu không có thì lấy chính tồn kho hiện tại
        base = tool.muc_canh_bao or tool.ton_kho
        if base:
            stock_percent = max(0, min(100, int(tool.ton_kho / base * 100)))
    holders_match = tool.holders_khuyen_dung.all()
    return render(
        request,
        "tool_profile.html",  # hoặc "tool/tool_profile.html" nếu bạn để trong folder app
        {
            "tool": tool,
            "history_list": history_list,
            "stock_percent": stock_percent,
            "holders_match": holders_match,   # 👈 thêm dòng này
        },
    )


def tool_create(request):
    error = None  # để báo lỗi ra template nếu có

    if request.method == "POST":
        data = request.POST

        ma_tool = (data.get("ma_tool") or "").strip()
        loai_gia_cong = (data.get("loai_gia_cong") or "").strip()

        # ====== VALIDATE CƠ BẢN ======
        if not ma_tool:
            error = "Vui lòng nhập mã tool."
        elif not loai_gia_cong:
            error = "Vui lòng chọn loại gia công chính."
        elif Tool.objects.filter(ma_tool=ma_tool).exists():
            error = "Mã tool này đã tồn tại, vui lòng nhập mã khác."
        else:
            # helper nhỏ để ép int hoặc None
            def to_int_or_none(value):
                if value in (None, ""):
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            ton_kho_val = data.get("ton_kho")
            muc_canh_bao_val = data.get("muc_canh_bao")

            # fuzzy score
            diem_gia = to_int_or_none(data.get("diem_gia"))
            diem_do_ben = to_int_or_none(data.get("diem_do_ben"))
            diem_on_dinh = to_int_or_none(data.get("diem_on_dinh"))
            diem_chat_luong_be_mat = to_int_or_none(data.get("diem_chat_luong_be_mat"))
            diem_san_co = to_int_or_none(data.get("diem_san_co"))
            diem_uu_tien_dung_truoc = to_int_or_none(data.get("diem_uu_tien_dung_truoc"))

            tool = Tool.objects.create(
                # ========== THÔNG TIN CHUNG ==========
                ten_tool=data.get("ten_tool") or None,
                ma_tool=ma_tool,
                nhom_tool=data.get("nhom_tool") or None,
                dong_tool=data.get("dong_tool") or None,
                nha_san_xuat=data.get("nha_san_xuat") or None,
                ma_nha_sx=data.get("ma_nha_sx") or None,
                tieu_chuan=data.get("tieu_chuan") or None,
                model=data.get("model") or None,
                vat_lieu_phu_hop=data.get("vat_lieu_phu_hop") or None,
                ghi_chu=data.get("ghi_chu") or None,

                # ========== THÔNG SỐ KỸ THUẬT CƠ BẢN ==========
                duong_kinh=data.get("duong_kinh") or None,
                chieu_dai_lam_viec=data.get("chieu_dai_lam_viec") or None,
                don_vi_tinh=data.get("don_vi_tinh") or None,
                tuoi_tho_chuan=data.get("tuoi_tho_chuan") or None,

                # ========== RÀNG BUỘC KỸ THUẬT (ĐỀ XUẤT) ==========
                loai_gia_cong=loai_gia_cong,
                nhom_vat_lieu_iso=data.get("nhom_vat_lieu_iso") or "",
                duong_kinh_min=data.get("duong_kinh_min") or None,
                duong_kinh_max=data.get("duong_kinh_max") or None,
                ty_le_sau_lo_max=data.get("ty_le_sau_lo_max") or None,
                do_cung_min=to_int_or_none(data.get("do_cung_min")),
                do_cung_max=to_int_or_none(data.get("do_cung_max")),
                may_phu_hop=data.get("may_phu_hop") or None,
                can_coolant=bool(data.get("can_coolant")),

                # ========== TỒN KHO & VỊ TRÍ ==========
                ton_kho=to_int_or_none(ton_kho_val) or 0,
                muc_canh_bao=to_int_or_none(muc_canh_bao_val),
                tu=data.get("tu") or None,
                ngan=data.get("ngan") or None,
                may_uu_tien=data.get("may_uu_tien") or None,
                ngay_nhap_kho=data.get("ngay_nhap_kho") or None,
                gia_tri_mua=data.get("gia_tri_mua") or None,

                # ========== THÔNG TIN MÒN & FUZZY THAM CHIẾU ==========
                wear_max=to_int_or_none(data.get("wear_max")),
                nguong_thay=to_int_or_none(data.get("nguong_thay")),
                hrc_tham_chieu=to_int_or_none(data.get("hrc_tham_chieu")),
                che_do_cat_khuyen_nghi=data.get("che_do_cat_khuyen_nghi") or None,
                ket_luan_fuzzy=data.get("ket_luan_fuzzy") or None,

                # ========== CÁC THUỘC TÍNH MỜ ==========
                diem_gia=diem_gia,
                diem_do_ben=diem_do_ben,
                diem_on_dinh=diem_on_dinh,
                diem_chat_luong_be_mat=diem_chat_luong_be_mat,
                diem_san_co=diem_san_co,
                diem_uu_tien_dung_truoc=diem_uu_tien_dung_truoc,
            )

            # Sau khi tạo xong -> về trang profile của tool vừa tạo
            return redirect("tool:tool_profile", pk=tool.pk)

    # GET hoặc POST có lỗi -> render lại form + lỗi
    return render(request, "tool_form.html", {"error": error})


def tool_list(request):
    tools = Tool.objects.all()
    return render(request, "tool_list.html", {"tools": tools})
