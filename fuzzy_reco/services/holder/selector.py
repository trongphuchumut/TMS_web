from holder.models import Holder
from django.db.models import QuerySet

def select_holder_candidates(limit: int = 50) -> QuerySet:
    # ưu tiên trạng thái sẵn sàng trước
    qs = Holder.objects.all().order_by("trang_thai_tai_san", "ten_thiet_bi")
    return qs[:limit]
