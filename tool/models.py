from django.db import models


class Tool(models.Model):
    # ====== CONSTANTS / CHOICES ======
    LOAI_GIA_CONG_CHOICES = [
        ("DRILL", "Khoan"),
        ("MILL", "Phay"),
        ("TAP", "Taro"),
        ("REAM", "Doa"),
        ("TURN", "Tiện"),
    ]

    NHOM_VL_CHOICES = [
        ("P", "Thép (ISO P)"),
        ("M", "Thép không gỉ (ISO M)"),
        ("K", "Gang (ISO K)"),
        ("N", "Nhôm/kim loại màu (ISO N)"),
        ("S", "Hợp kim chịu nhiệt (ISO S)"),
        ("H", "Thép đã tôi (ISO H)"),
    ]

    # ================= THÔNG TIN CHUNG =================
    ten_tool = models.CharField(
        max_length=200,
        verbose_name="Tên tool"
    )
    ma_tool = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Mã tool"
    )
    nhom_tool = models.CharField(
        max_length=100,
        verbose_name="Nhóm tool",
        help_text="VD: Mũi khoan, Dao phay, Mũi taro…"
    )
    dong_tool = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Dòng tool",
        help_text="VD: Drill, Endmill, Tap…"
    )

    nha_san_xuat = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nhà sản xuất"
    )
    ma_nha_sx = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Mã nhà sản xuất"
    )
    tieu_chuan = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Tiêu chuẩn"
    )
    model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Model"
    )
    vat_lieu_phu_hop = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Vật liệu gia công phù hợp",
        help_text="VD: C45, S50C, SUS304…"
    )
    ghi_chu = models.TextField(
        blank=True,
        verbose_name="Ghi chú thêm"
    )

    # ================= THÔNG SỐ KỸ THUẬT CƠ BẢN =================
    duong_kinh = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Đường kính làm việc (mm)"
    )
    chieu_dai_lam_viec = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Chiều dài làm việc (mm)"
    )
    don_vi_tinh = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Đơn vị tính",
        help_text="VD: cái, hộp, bộ…"
    )
    tuoi_tho_chuan = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Tuổi thọ chuẩn",
        help_text="VD: 1500 lỗ / 1 tool"
    )

    # ================= RÀNG BUỘC KỸ THUẬT DÙNG CHO ĐỀ XUẤT =================
    loai_gia_cong = models.CharField(
        max_length=50,
        choices=LOAI_GIA_CONG_CHOICES,
        verbose_name="Loại gia công chính",
        null=True,
        blank=True,
        help_text="Khoan / Phay / Taro / Doa / Tiện…"
    )

    duong_kinh_min = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="ĐK min cho phép (mm)"
    )
    duong_kinh_max = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="ĐK max cho phép (mm)"
    )
    ty_le_sau_lo_max = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Tỷ lệ sâu lỗ max (L/D)"
    )

    nhom_vat_lieu_iso = models.CharField(
        max_length=2,
        choices=NHOM_VL_CHOICES,
        blank=True,
        verbose_name="Nhóm vật liệu ISO"
    )
    do_cung_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Độ cứng vật liệu min (HRC)"
    )
    do_cung_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Độ cứng vật liệu max (HRC)"
    )

    may_phu_hop = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Dòng máy phù hợp",
        help_text="VD: VMC 10.000 rpm, CNC tiện, Máy khoan bàn…"
    )
    can_coolant = models.BooleanField(
        default=False,
        verbose_name="Yêu cầu tưới nguội"
    )

    # ================= TỒN KHO & VỊ TRÍ =================
    ton_kho = models.PositiveIntegerField(
        default=0,
        verbose_name="Tồn kho hiện tại"
    )
    muc_canh_bao = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Mức cảnh báo tối thiểu"
    )

    tu = models.CharField(
    max_length=1,
    blank=True,
    verbose_name="Tủ (A/B/...)"
    )

    ngan = models.PositiveSmallIntegerField(
    null=True,
    blank=True,
    verbose_name="Ngăn (số)"
    )

    may_uu_tien = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Máy / Line ưu tiên"
    )

    ngay_nhap_kho = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ngày nhập kho"
    )
    gia_tri_mua = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Giá trị mua (VND/đv)"
    )

    # ================= THÔNG TIN MÒN & FUZZY THAM CHIẾU =================
    wear_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Độ mòn tối đa (%)"
    )
    nguong_thay = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Ngưỡng cảnh báo thay (%)"
    )
    hrc_tham_chieu = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Độ cứng vật liệu tham chiếu (HRC)"
    )
    che_do_cat_khuyen_nghi = models.TextField(
        blank=True,
        verbose_name="Chế độ cắt khuyến nghị"
    )
    ket_luan_fuzzy = models.TextField(
        blank=True,
        verbose_name="Kết luận fuzzy / khuyến nghị"
    )

    # ================= CÁC THUỘC TÍNH MỜ ĐỂ ĐỀ XUẤT =================
    # 1–5: 1 = thấp / kém, 5 = rất cao / rất tốt
    diem_gia = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Điểm giá (1=rẻ, 5=rất đắt)"
    )
    diem_do_ben = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Điểm độ bền (1=thấp, 5=rất bền)"
    )
    diem_on_dinh = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Độ ổn định quá trình (1=kém, 5=rất ổn định)"
    )
    diem_chat_luong_be_mat = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Chất lượng bề mặt (1=thô, 5=rất đẹp)"
    )
    diem_san_co = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Độ sẵn có (1=khó mua, 5=luôn sẵn)"
    )
    diem_uu_tien_dung_truoc = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Mức ưu tiên dùng trước (1=ít, 5=ưu tiên cao)"
    )

    # ================= META =================
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời gian tạo"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Thời gian cập nhật"
    )

    class Meta:
        verbose_name = "Tool tiêu hao"
        verbose_name_plural = "Tool tiêu hao"
        ordering = ["ten_tool", "ma_tool"]
        indexes = [
            models.Index(fields=["ma_tool"]),
            models.Index(fields=["nhom_tool", "dong_tool"]),
            models.Index(fields=["loai_gia_cong", "nhom_vat_lieu_iso"]),
        ]

    def __str__(self):
        return f"{self.ten_tool} ({self.ma_tool})" if self.ma_tool else self.ten_tool

    @property
    def is_low_stock(self) -> bool:
        """Trả về True nếu tồn kho dưới hoặc bằng mức cảnh báo."""
        if self.muc_canh_bao is None:
            return False
        return self.ton_kho <= self.muc_canh_bao

    def get_fuzzy_profile(self) -> dict:
        """
        Gom các thuộc tính mờ thành 1 dict – tiện đưa sang
        engine fuzzy xử lý.
        """
        return {
            "diem_gia": self.diem_gia,
            "diem_do_ben": self.diem_do_ben,
            "diem_on_dinh": self.diem_on_dinh,
            "diem_chat_luong_be_mat": self.diem_chat_luong_be_mat,
            "diem_san_co": self.diem_san_co,
            "diem_uu_tien_dung_truoc": self.diem_uu_tien_dung_truoc,
        }
