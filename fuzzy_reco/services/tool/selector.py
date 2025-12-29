from tool.models import Tool
from django.db.models import QuerySet

def select_tool_candidates(limit: int = 50) -> QuerySet:
    # v1: ưu tiên còn hàng trước
    qs = Tool.objects.all().order_by("-ton_kho", "ten_tool")
    return qs[:limit]
