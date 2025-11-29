from django.contrib import admin
from .models import HolderHistory


@admin.register(HolderHistory)
class HolderHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ma_noi_bo_snapshot",
        "ten_thiet_bi_snapshot",
        "muc_dich",
        "trang_thai",
        "du_an",
        "mon_truoc",
        "mon_sau",
        "thoi_gian_muon",
        "thoi_gian_tra",
        "thoi_luong_phut",
        "nguoi_thuc_hien",
    )

    list_filter = (
        "muc_dich",
        "trang_thai",
        "thoi_gian_muon",
        "thoi_gian_tra",
    )

    search_fields = (
        "holder__ma_noi_bo",
        "holder__ten_thiet_bi",
        "ma_noi_bo_snapshot",
        "ten_thiet_bi_snapshot",
        "du_an",
        "mo_ta",
        "nguoi_thuc_hien__username",
        "nguoi_thuc_hien__first_name",
        "nguoi_thuc_hien__last_name",
    )

    ordering = ("-thoi_gian_muon",)

    # 🔹 Chỉ để readonly các field hệ thống / auto:
    readonly_fields = (
        "thoi_luong_phut",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Thông tin holder", {
            "fields": (
                "holder",
                "ma_noi_bo_snapshot",
                "ten_thiet_bi_snapshot",
            )
        }),
        ("Mượn / Trả", {
            "fields": (
                "muc_dich",
                "du_an",
                "mo_ta",
                "trang_thai",
                "thoi_gian_muon",
                "thoi_gian_tra",
                "thoi_luong_phut",
            )
        }),
        ("Mòn / Độ bền", {
            "fields": (
                "mon_truoc",
                "mon_sau",
            )
        }),
        ("Hệ thống", {
            "fields": (
                "nguoi_thuc_hien",
                "created_at",
                "updated_at",
            )
        }),
    )
