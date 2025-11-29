# chatbot/fuzzy/candidates.py
from holder.models import Holder
from tool.models import Tool


def get_candidates(criteria: dict | None) -> tuple[list, str]:
    """
    Dựa vào criteria để quyết định lấy Tool / Holder / cả hai.
    Trả về:
      - list candidates (object Tool hoặc Holder)
      - loai_thiet_bi đã sử dụng ("tool" / "holder" / "both")
    """
    loai = "tool"
    if criteria:
        loai = criteria.get("loai_thiet_bi", "tool") or "tool"

    if loai == "holder":
        candidates = list(Holder.objects.all()[:50])
    elif loai == "both":
        candidates = list(Holder.objects.all()[:25]) + list(Tool.objects.all()[:25])
    else:
        candidates = list(Tool.objects.all()[:50])

    return candidates, loai
