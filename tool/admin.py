from django.contrib import admin
from .models import Tool


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):

    # ======== DANH SÁCH HIỂN THỊ =========
    list_display = (
        "ma_tool",
        "ten_tool",
        "nhom_tool",
        "dong_tool",
        "nha_san_xuat",
        "loai_gia_cong",
        "nhom_vat_lieu_iso",
        "ton_kho",
        "muc_canh_bao",
        "is_low_stock_color",
    )
    list_display_links = ("ma_tool", "ten_tool")

    # ======== FILTER BÊN PHẢI =========
    list_filter = (
        "nhom_tool",
        "loai_gia_cong",
        "nhom_vat_lieu_iso",
        "nha_san_xuat",
        "tu",
        "ngan",
        "may_uu_tien",
        "can_coolant",
    )

    # ======== Ô SEARCH =========
    search_fields = (
        "ma_tool",
        "ten_tool",
        "nhom_tool",
        "dong_tool",
        "nha_san_xuat",
        "tieu_chuan",
        "vat_lieu_phu_hop",
        "model",
        "tu",
        "ngan",
    )

    # ======== FIELD CHỈ ĐỌC =========
    readonly_fields = ("created_at", "updated_at")

    # ======== SẮP XẾP MẶC ĐỊNH =========
    ordering = ("ten_tool", "ma_tool")

    # ======== TỐI ƯU FORM – CHIA NHÓM FIELDSETS =========
    fieldsets = (
        ("THÔNG TIN CHUNG", {
            "fields": (
                "ten_tool", "ma_tool",
                "nhom_tool", "dong_tool",
                "nha_san_xuat", "ma_nha_sx",
                "tieu_chuan", "model",
                "vat_lieu_phu_hop", "ghi_chu",
            )
        }),

        ("THÔNG SỐ KỸ THUẬT CƠ BẢN", {
            "fields": (
                "duong_kinh", "chieu_dai_lam_viec",
                "don_vi_tinh", "tuoi_tho_chuan",
            ),
            "classes": ("collapse",),
        }),

        ("RÀNG BUỘC KỸ THUẬT (DE-XUẤT)", {
            "fields": (
                "loai_gia_cong",
                "duong_kinh_min", "duong_kinh_max",
                "ty_le_sau_lo_max",
                "nhom_vat_lieu_iso",
                "do_cung_min", "do_cung_max",
                "may_phu_hop", "can_coolant",
            ),
            "classes": ("collapse",),
        }),

        ("TỒN KHO & VỊ TRÍ", {
            "fields": (
                "ton_kho", "muc_canh_bao",
                "tu", "ngan", "may_uu_tien",
                "ngay_nhap_kho", "gia_tri_mua",
            )
        }),

        ("THÔNG TIN MÒN & FUZZY", {
            "fields": (
                "wear_max", "nguong_thay", "hrc_tham_chieu",
                "che_do_cat_khuyen_nghi",
                "diem_gia", "diem_do_ben", "diem_on_dinh",
                "diem_chat_luong_be_mat", "diem_san_co",
                "diem_uu_tien_dung_truoc",
                "ket_luan_fuzzy",
            ),
            "classes": ("collapse",),
        }),

        ("META", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    # ======== CUSTOM HIỂN THỊ MÀU SẮC CẢNH BÁO =========
    def is_low_stock_color(self, obj):
        """Hiển thị cảnh báo tồn kho màu đỏ/xanh."""
        if obj.muc_canh_bao is None:
            return "—"
        if obj.ton_kho <= obj.muc_canh_bao:
            return f"⚠️ {obj.ton_kho} (Thấp)"
        return f"✔️ {obj.ton_kho}"

    is_low_stock_color.short_description = "Tồn kho"
    is_low_stock_color.admin_order_field = "ton_kho"
