from django.db import models

class Holder(models.Model):
    # THÔNG TIN CHUNG
    ten_thiet_bi = models.CharField(max_length=200)
    nhom_thiet_bi = models.CharField(max_length=100)
    ma_noi_bo = models.CharField(max_length=50, unique=True)
    ma_nha_sx = models.CharField(max_length=100)
    loai_holder = models.CharField(max_length=100, blank=True, null=True)
    so_serial = models.CharField(max_length=100, blank=True, null=True)

    nha_san_xuat = models.CharField(max_length=100, blank=True, null=True)
    nha_cung_cap = models.CharField(max_length=150, blank=True, null=True)
    nguoi_quan_ly = models.CharField(max_length=100, blank=True, null=True)
    
    TRANG_THAI_CHOICES = [
        ("dang_su_dung", "Đang sẵn sàng"),
        ("dang_bao_tri", "Đang bảo trì"),
        ("ngung_su_dung", "Ngừng sử dụng"),
        ("dang_duoc_muon", "Đang được mượn"),
    ]
    trang_thai_tai_san = models.CharField(
        max_length=20,
        choices=TRANG_THAI_CHOICES,
        blank=True,
        null=True,
    )

    # THÔNG SỐ KỸ THUẬT & KHO
    chuan_ga = models.CharField(max_length=50, blank=True, null=True)
    loai_kep = models.CharField(max_length=50, blank=True, null=True)
    chieu_dai_lam_viec = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True
    )
    duong_kinh_kep_max = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True
    )

    tu = models.CharField(max_length=50, blank=True, null=True)
    ngan = models.CharField(max_length=50, blank=True, null=True)
    may_uu_tien = models.CharField(max_length=200, blank=True, null=True)

    ngay_nhap_kho = models.DateField(blank=True, null=True)
    gia_tri_mua = models.BigIntegerField(blank=True, null=True)

    # BẢO TRÌ & TÌNH TRẠNG
    chu_ky_kiem_tra = models.CharField(max_length=100, blank=True, null=True)
    lan_kiem_tra_gan_nhat = models.DateField(blank=True, null=True)
    so_lan_ga_thao = models.IntegerField(blank=True, null=True)
    danh_gia_gan_nhat = models.TextField(blank=True, null=True)

    # THÔNG SỐ FUZZY
    cv = models.DecimalField(  # Độ cứng vững
        max_digits=4, decimal_places=1, blank=True, null=True
    )
    dx = models.DecimalField(  # Độ chính xác gá kẹp
        max_digits=4, decimal_places=1, blank=True, null=True
    )
    mon = models.IntegerField(blank=True, null=True)  # % mòn
    tan_suat = models.IntegerField(blank=True, null=True)  # lần/tháng
    ld = models.DecimalField(  # chiều dài nhô dao
        max_digits=6, decimal_places=2, blank=True, null=True
    )
    ket_luan_fuzzy = models.TextField(blank=True, null=True)

    # 🔹 TRƯỜNG MỚI 1: DANH SÁCH TOOL TƯƠNG THÍCH / KHUYÊN DÙNG
    tool_khuyen_dung = models.ManyToManyField(
        'tool.tool',          # hoặc 'Tool' nếu cùng app
        blank=True,
        related_name='holders_khuyen_dung',
        help_text="Các tool tương thích & khuyên dùng với holder này"
    )

    # 🔹 TRƯỜNG MỚI 2: MÃ / NHÓM TƯƠNG THÍCH
    ma_nhom_tuong_thich = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Nếu 2 holder có cùng mã này thì coi như tương thích / thay thế cho nhau"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ma_noi_bo} - {self.ten_thiet_bi}"
