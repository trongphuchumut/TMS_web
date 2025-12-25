from django.contrib import admin
from .models import Holder


@admin.register(Holder)
class HolderAdmin(admin.ModelAdmin):

    # Các cột hiển thị trong danh sách Holder
    list_display = (
        "ma_noi_bo",
        "rfid", 
        "ten_thiet_bi",
        "nhom_thiet_bi",
        "loai_holder",
        "trang_thai_tai_san",
        "tu",
        "ngan",
        "may_uu_tien",
        "ma_nhom_tuong_thich",      # 👈 mới thêm
    )

    # Bộ lọc bên phải
    list_filter = (
        "nhom_thiet_bi",
        "trang_thai_tai_san",
        "nha_san_xuat",
        "nguoi_quan_ly",
        "tu",
        "may_uu_tien",
        "ma_nhom_tuong_thich",      # 👈 có luôn
    )

    # Cho phép tìm kiếm
    search_fields = (
        "ma_noi_bo",
        "rfid",  
        "ten_thiet_bi",
        "ma_nha_sx",
        "nha_san_xuat",
        "loai_holder",
        "so_serial",
        "ma_nhom_tuong_thich",      # 👈 search theo mã nhóm
    )

    readonly_fields = ("created_at",)

    ordering = ("ma_noi_bo",)

    # 👇 Hiển thị tool_khuyen_dung dạng khung chọn 2 cột (rất dễ dùng)
    filter_horizontal = ("tool_khuyen_dung",)

    # 👇 Sắp xếp các nhóm field trong form Holder
    fieldsets = (
        ("Thông tin chung", {
            "fields": (
                "ten_thiet_bi",
                "nhom_thiet_bi",
                "ma_noi_bo",
                "rfid", 
                "ma_nha_sx",
                "loai_holder",
                "so_serial",
                "trang_thai_tai_san",
            )
        }),

        ("Nhà sản xuất & Quản lý", {
            "fields": (
                "nha_san_xuat",
                "nha_cung_cap",
                "nguoi_quan_ly",
            )
        }),

        ("Thông số kỹ thuật", {
            "fields": (
                "chuan_ga",
                "loai_kep",
                "chieu_dai_lam_viec",
                "duong_kinh_kep_max",
            )
        }),

        ("Vị trí kho", {
            "fields": (
                "tu",
                "ngan",
                "may_uu_tien",
                "ngay_nhap_kho",
                "gia_tri_mua",
            )
        }),

        ("Bảo trì & Kiểm tra", {
            "fields": (
                "chu_ky_kiem_tra",
                "lan_kiem_tra_gan_nhat",
                "so_lan_ga_thao",
                "danh_gia_gan_nhat",
            )
        }),

        ("Thông số fuzzy", {
            "fields": (
                "cv",
                "dx",
                "mon",
                "tan_suat",
                "ld",
                "ket_luan_fuzzy",
            )
        }),

        ("Tương thích & Gợi ý", {
            "fields": (
                "ma_nhom_tuong_thich",   # 👈 nhóm/mã hiệu tương thích
                "tool_khuyen_dung",      # 👈 Tool tương thích khuyên dùng
            )
        }),

        ("Khác", {
            "fields": ("created_at",)
        }),
    )
