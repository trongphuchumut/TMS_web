from django.contrib import admin
from .models import ToolTransaction


@admin.register(ToolTransaction)
class ToolTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "loai",
        "tool",
        "so_luong",
        "ton_truoc",
        "ton_sau",
        "ma_du_an",
        "nguoi_thuc_hien",
    )

    list_filter = ("loai", "tool", "created_at")
    search_fields = (
        "tool__ma_tool",
        "tool__ten_tool",
        "ma_du_an",
        "ghi_chu",
    )
    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "nguoi_thuc_hien",
        "ton_truoc",
        "ton_sau",
    )

    fieldsets = (
        ("Thông tin giao dịch", {
            "fields": ("loai", "tool", "so_luong", "ton_truoc", "ton_sau")
        }),
        ("Dự án & ghi chú", {
            "fields": ("ma_du_an", "ghi_chu")
        }),
        ("Hệ thống", {
            "fields": ("nguoi_thuc_hien", "created_at")
        }),
    )

    # ❌ Không cho tạo mới trong admin
    def has_add_permission(self, request):
        return False

    # ❌ Không cho chỉnh sửa (chỉ xem)
    def has_change_permission(self, request, obj=None):
        return True

    # (Tuỳ bạn) cho xoá hay không — mình khuyên là KHÔNG
    def has_delete_permission(self, request, obj=None):
        return True
