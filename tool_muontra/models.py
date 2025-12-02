from django.db import models
from django.contrib.auth.models import User
from tool.models import Tool


class ToolTransaction(models.Model):
    # Các loại giao dịch
    EXPORT = "EXPORT"    # Xuất kho (mượn / lấy tool ra)
    IMPORT = "IMPORT"    # Nhập kho (mua mới / bổ sung)
    RETURN = "RETURN"    # Trả lại kho (bỏ tool vào lại)

    LOAI_CHOICES = [
        (EXPORT, "Xuất kho"),
        (IMPORT, "Nhập kho"),
        (RETURN, "Trả lại kho"),
    ]

    # Trạng thái xử lý giao dịch
    TRANG_THAI_CHOICES = [
        ("PENDING", "Đang chờ tủ xử lý"),
        ("SUCCESS", "Thành công"),
        ("FAILED", "Thất bại"),
    ]

    # -----------------------------
    # FIELD CHÍNH
    # -----------------------------
    loai = models.CharField(max_length=20, choices=LOAI_CHOICES)

    tool = models.ForeignKey(
        Tool,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    so_luong = models.PositiveIntegerField()
    ton_truoc = models.PositiveIntegerField()
    ton_sau = models.PositiveIntegerField()

    # Các thông tin phụ
    ma_du_an = models.CharField(max_length=100, blank=True)
    ghi_chu = models.TextField(blank=True)

    # Ai thực hiện
    nguoi_thuc_hien = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="tool_transactions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # -----------------------------
    # MQTT – kết nối giao dịch phần cứng
    # -----------------------------
    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI_CHOICES,
        default="PENDING",
    )

    ly_do_fail = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Lý do giao dịch thất bại do tủ gửi về.",
    )

    tx_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID giao dịch để map giữa Django và ESP32.",
    )

    # -----------------------------
    def __str__(self):
        return f"{self.loai} - {self.tool.ma_tool} - SL: {self.so_luong}"
