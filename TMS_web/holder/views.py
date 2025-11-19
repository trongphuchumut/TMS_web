from django.shortcuts import render, redirect, get_object_or_404
from .models import Holder


def holder_profile(request, pk):
    holder = get_object_or_404(Holder, pk=pk)
    return render(request, "holder_profile.html", {"holder": holder})


def holder_create(request):
    error = None  # để báo lỗi ra template nếu có

    if request.method == "POST":
        data = request.POST

        # Lấy mã nội bộ, strip cho sạch khoảng trắng
        ma_noi_bo = (data.get("ma_noi_bo") or "").strip()

        # 1) Không cho để trống
        if not ma_noi_bo:
            error = "Vui lòng nhập mã nội bộ."
        # 2) Không cho trùng
        elif Holder.objects.filter(ma_noi_bo=ma_noi_bo).exists():
            error = "Mã nội bộ này đã tồn tại, vui lòng nhập mã khác."
        else:
            # Nếu mọi thứ ok -> tạo mới
            holder = Holder.objects.create(
                ten_thiet_bi=data.get("ten_thiet_bi"),
                nhom_thiet_bi=data.get("nhom_thiet_bi"),
                ma_noi_bo=ma_noi_bo,
                ma_nha_sx=data.get("ma_nha_sx"),
                loai_holder=data.get("loai_holder") or None,
                so_serial=data.get("so_serial") or None,
                nha_san_xuat=data.get("nha_san_xuat") or None,
                nha_cung_cap=data.get("nha_cung_cap") or None,
                nguoi_quan_ly=data.get("nguoi_quan_ly") or None,
                trang_thai_tai_san=data.get("trang_thai_tai_san") or None,
                chuan_ga=data.get("chuan_ga") or None,
                loai_kep=data.get("loai_kep") or None,
                chieu_dai_lam_viec=data.get("chieu_dai_lam_viec") or None,
                duong_kinh_kep_max=data.get("duong_kinh_kep_max") or None,
                tu=data.get("tu") or None,
                ngan=data.get("ngan") or None,
                may_uu_tien=data.get("may_uu_tien") or None,
                ngay_nhap_kho=data.get("ngay_nhap_kho") or None,
                gia_tri_mua=data.get("gia_tri_mua") or None,
                chu_ky_kiem_tra=data.get("chu_ky_kiem_tra") or None,
                lan_kiem_tra_gan_nhat=data.get("lan_kiem_tra_gan_nhat") or None,
                so_lan_ga_thao=data.get("so_lan_ga_thao") or None,
                danh_gia_gan_nhat=data.get("danh_gia_gan_nhat") or None,
                cv=data.get("cv") or None,
                dx=data.get("dx") or None,
                mon=data.get("mon") or None,
                tan_suat=data.get("tan_suat") or None,
                ld=data.get("ld") or None,
                ket_luan_fuzzy=data.get("ket_luan_fuzzy") or None,
            )

            # Vì app_name = "holder" nên phải dùng namespace "holder:"
            # Tạm thời đưa về trang profile chung, sau này bạn làm trang chi tiết thì đổi sau
            return redirect("holder:holder_profile")
            # Hoặc nếu sau này có holder_detail nhận pk:
            # return redirect("holder:holder_detail", pk=holder.pk)

    # GET hoặc POST có lỗi -> render lại form + lỗi
    return render(request, "holder_form.html", {"error": error})


def holder_list(request):
    holders = Holder.objects.all()
    return render(request, "holder_list.html", {"holders": holders})
