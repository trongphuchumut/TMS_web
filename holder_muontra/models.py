# holder_muontra/models.py
from django.db import models
from django.contrib.auth.models import User
from holder.models import Holder


class HolderHistory(models.Model):
    """
    Lịch sử mượn / trả 1 holder, có đọc & lưu một phần thông tin từ bảng Holder.
    Dùng để:
      - log mục đích mượn (sử dụng / bảo trì)
      - dự án, mô tả
      - thời gian mượn / trả, thời lượng sử dụng
      - % độ bền trước / sau (dựa trên field `mon` của Holder, 0–100)
    """

    MUC_DICH_CHOICES = [
        ("SU_DUNG", "Mượn để sử dụng"),
        ("BAO_TRI", "Đem đi bảo trì"),
    ]

    TRANG_THAI_CHOICES = [
        ("DANG_MUON", "Đang mượn"),
        ("DA_TRA", "Đã trả"),
    ]

    # === THAM CHIẾU HOLDER GỐC ===
    holder = models.ForeignKey(
        Holder,
        on_delete=models.CASCADE,
        related_name="histories",
        verbose_name="Holder",
    )

    # Snapshot thông tin từ Holder
    ten_thiet_bi_snapshot = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Tên thiết bị (snapshot)",
        help_text="Copy từ Holder.ten_thiet_bi tại thời điểm mượn",
    )
    ma_noi_bo_snapshot = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Mã nội bộ (snapshot)",
        help_text="Copy từ Holder.ma_noi_bo tại thời điểm mượn",
    )

    # === MỤC ĐÍCH & BỐI CẢNH MƯỢN ===
    muc_dich = models.CharField(
        max_length=20,
        choices=MUC_DICH_CHOICES,
        verbose_name="Mục đích mượn",
    )
    du_an = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Dự án / lệnh sản xuất",
    )
    mo_ta = models.TextField(
        blank=True,
        verbose_name="Mô tả chi tiết / ghi chú",
    )

    # Người mượn / thao tác
    nguoi_thuc_hien = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="holder_history_actions",
        verbose_name="Người thực hiện",
    )

    # === THỜI GIAN MƯỢN / TRẢ ===
    thoi_gian_muon = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời gian mượn",
    )
    thoi_gian_tra = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời gian trả",
    )

    # Thời lượng sử dụng (phút) – sẽ tính khi trả
    thoi_luong_phut = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Thời lượng sử dụng (phút)",
    )

    # === % ĐỘ BỀN TRƯỚC / SAU (0–100) ===
    mon_truoc = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="% độ bền trước khi mượn",
        help_text="Từ Holder.mon tại thời điểm mượn (0–100)",
    )
    mon_sau = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="% độ bền sau khi trả",
        help_text="Sau khi trừ hao / reset bảo trì (0–100)",
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI_CHOICES,
        default="DANG_MUON",
        verbose_name="Trạng thái mượn",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Tạo lúc",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Cập nhật lúc",
    )

    class Meta:
        verbose_name = "Lịch sử mượn holder"
        verbose_name_plural = "Lịch sử mượn holder"
        ordering = ["-thoi_gian_muon"]

    def __str__(self):
        return f"{self.holder.ma_noi_bo} - {self.get_muc_dich_display()} - {self.trang_thai}"

    # --- HỖ TRỢ: tự đọc info từ Holder khi tạo record mới ---
    def save(self, *args, **kwargs):
        # Nếu là record mới (chưa có pk) thì chụp snapshot từ Holder
        if self.pk is None and self.holder:
            if not self.ten_thiet_bi_snapshot:
                self.ten_thiet_bi_snapshot = self.holder.ten_thiet_bi
            if not self.ma_noi_bo_snapshot:
                self.ma_noi_bo_snapshot = self.holder.ma_noi_bo

            # Độ bền trước: ưu tiên lấy từ holder.mon,
            # nếu holder.mon đang None => coi như 100% (mới)
            if self.mon_truoc is None:
                if self.holder.mon is not None:
                    self.mon_truoc = self.holder.mon
                else:
                    self.mon_truoc = 100

        super().save(*args, **kwargs)
