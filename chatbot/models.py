from django.db import models


class ChatbotConfig(models.Model):
    """
    Cấu hình chung cho chatbot.
    Dự kiến chỉ dùng 1 row (global).
    """

    bot_name = models.CharField(
        max_length=100,
        default="Trợ lý TMS",
        verbose_name="Tên chatbot hiển thị"
    )

    enable_smalltalk = models.BooleanField(
        default=True,
        verbose_name="Cho phép smalltalk / chào hỏi"
    )

    max_search_results = models.PositiveIntegerField(
        default=3,
        verbose_name="Số gợi ý search tối đa"
    )

    max_fuzzy_suggestions = models.PositiveIntegerField(
        default=3,
        verbose_name="Số gợi ý fuzzy tối đa"
    )

    search_auto_show_threshold = models.FloatField(
        default=0.90,
        verbose_name="Ngưỡng search auto show (0–1)"
    )

    fuzzy_need_more_info_threshold = models.FloatField(
        default=0.40,
        verbose_name="Ngưỡng fuzzy cần hỏi thêm (0–1)"
    )

    enable_debug_block = models.BooleanField(
        default=False,
        verbose_name="Bật DEBUG trong câu trả lời"
    )

    TONE_CHOICES = [
        ("formal", "Trang trọng"),
        ("casual", "Thân mật"),
    ]
    tone = models.CharField(
        max_length=20,
        choices=TONE_CHOICES,
        default="casual",
        verbose_name="Giọng điệu trả lời"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Cấu hình Chatbot"

    class Meta:
        verbose_name = "Cấu hình Chatbot"
        verbose_name_plural = "Cấu hình Chatbot"


def get_chatbot_config() -> "ChatbotConfig":
    """
    Helper lấy config (1 bản duy nhất).
    Nếu chưa có thì tạo default.
    """
    cfg, _ = ChatbotConfig.objects.get_or_create(pk=1)
    return cfg


class FuzzyRunLog(models.Model):
    """
    Lưu lại lần chạy FUZZY gần nhất để demo/bảo vệ đồ án:
    - câu hỏi
    - tiêu chí đã parse
    - top kết quả + breakdown
    """
    created_at = models.DateTimeField(auto_now_add=True)
    user_text = models.TextField()
    criteria_json = models.JSONField()
    results_json = models.JSONField()  # list topN: {score, name, code, breakdown}

    def __str__(self) -> str:
        return f"FuzzyRunLog #{self.pk} - {self.created_at:%Y-%m-%d %H:%M}"
