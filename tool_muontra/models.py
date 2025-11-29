from django.db import models
from django.contrib.auth.models import User
from tool.models import Tool
from holder.models import Holder


class ToolTransaction(models.Model):
    EXPORT = "EXPORT"                    # Xuất kho
    IMPORT = "IMPORT"                    # Nhập kho
    RETURN = "RETURN"                    # Trả lại kho


    LOAI_CHOICES = [
        (EXPORT, "Xuất kho"),
        (IMPORT, "Nhập kho"),
        (RETURN, "Trả lại kho"),

    ]

    # Loại giao dịch (user chọn trong form)
    loai = models.CharField(max_length=20, choices=LOAI_CHOICES)

    # Tool bị tác động
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)

    # Số lượng thay đổi
    so_luong = models.PositiveIntegerField()
    ton_truoc = models.PositiveIntegerField()
    ton_sau = models.PositiveIntegerField()



    # OPTIONAL – chỉ dùng cho dự án
    ma_du_an = models.CharField(max_length=100, blank=True)

    # ghi chú
    ghi_chu = models.TextField(blank=True)

    # Người thực hiện (tự lấy từ request.user)
    nguoi_thuc_hien = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL
    )

    # thời gian tạo
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.loai} - {self.tool} - {self.so_luong}"

