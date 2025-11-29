# chatbot/fuzzy/scoring.py
from typing import Any

from tool.models import Tool
from holder.models import Holder


def score_device(dev: Any, criteria: dict | None) -> float:
    """
    Hàm chấm điểm fuzzy cho từng device (Tool hoặc Holder).
    Hiện tại mới dùng vật liệu để demo. Sau này mở rộng:
      - HRC
      - đường kính / chiều dài
      - tuổi thọ chuẩn / wear
      - cluster fuzzy
      - ...
    """
    if not criteria:
        return 0.0

    score = 0.0

    vat_lieu = (criteria.get("vat_lieu") or "").lower().strip()
    if vat_lieu:
        # Tool có field vat_lieu_phu_hop
        if isinstance(dev, Tool) and hasattr(dev, "vat_lieu_phu_hop"):
            if vat_lieu in (dev.vat_lieu_phu_hop or "").lower():
                score += 0.4

    # TODO: ví dụ mở rộng:
    # duong_kinh = criteria.get("duong_kinh_uu_tien")
    # if duong_kinh and hasattr(dev, "duong_kinh"):
    #     # cộng điểm nếu gần giống
    #     ...

    return score


def score_all_candidates(candidates: list, criteria: dict | None) -> list[tuple[float, Any]]:
    """
    Chấm điểm toàn bộ candidates.
    Trả list [(score, dev), ...] và đã sort giảm dần.
    """
    scored = [(score_device(dev, criteria), dev) for dev in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored
