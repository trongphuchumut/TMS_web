# chatbot/fuzzy/candidates.py
from __future__ import annotations
from typing import Any, Tuple, List

from django.db.models import Q

from holder.models import Holder
from tool.models import Tool


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def _safe_float(v: Any, default: float | None = None) -> float | None:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


# ===== TOOL =====
def _tool_qty(t: Tool) -> int:
    """
    Đọc số lượng tồn kho của Tool (tiêu hao).
    ✅ Bạn đổi đúng field tồn kho của bạn ở đây.
    """
    for f in ("so_luong_ton", "ton_kho", "so_luong", "qty", "quantity"):
        if hasattr(t, f):
            return _safe_int(getattr(t, f), 0)
    return 0


# ===== HOLDER =====
def _holder_is_available(h: Holder) -> bool:
    """
    Holder là duy nhất => chỉ cần biết có đang nằm trong kho hay không.
    ✅ Nếu bạn có field is_available hoặc trang_thai thì dùng.
    """
    if hasattr(h, "is_available"):
        return bool(getattr(h, "is_available"))
    if hasattr(h, "trang_thai"):
        val = str(getattr(h, "trang_thai") or "").upper()
        return val in {"TRONG_KHO", "AVAILABLE", "IN_STOCK", "OK"}
    return True  # fallback (không chặn nếu thiếu field)


def _holder_durability_left(h: Holder) -> float | None:
    """
    Tính độ bền còn lại: nguong_thay - mon (hoặc wear_max - mon)
    ✅ Bạn đổi đúng field mòn/ngưỡng ở đây.
    """
    if hasattr(h, "mon") and hasattr(h, "nguong_thay"):
        mon = _safe_float(getattr(h, "mon"), None)
        nguong = _safe_float(getattr(h, "nguong_thay"), None)
        if mon is not None and nguong is not None:
            return max(0.0, nguong - mon)

    if hasattr(h, "mon") and hasattr(h, "wear_max"):
        mon = _safe_float(getattr(h, "mon"), None)
        mx = _safe_float(getattr(h, "wear_max"), None)
        if mon is not None and mx is not None:
            return max(0.0, mx - mon)

    return None


def get_candidates(criteria: dict | None) -> Tuple[List[Any], str]:
    """
    ✅ Đây là bước LỌC CỨNG (constraint) trước fuzzy:
      - Tool: đủ tồn kho >= min_qty
      - Holder: available + (nếu set) durability_left >= min_holder_left
    """
    criteria = criteria or {}
    loai = (criteria.get("loai_thiet_bi") or "tool").strip().lower()
    if loai not in {"tool", "holder", "both"}:
        loai = "tool"

    vat_lieu = (criteria.get("vat_lieu") or "").strip()
    loai_gia_cong = (criteria.get("loai_gia_cong") or "").strip()

    min_qty = _safe_int(criteria.get("min_qty"), 1)
    if min_qty < 1:
        min_qty = 1

    min_holder_left = _safe_float(criteria.get("min_holder_left"), None)
    if min_holder_left is not None and min_holder_left < 0:
        min_holder_left = 0.0

    broad = (not vat_lieu) and (not loai_gia_cong)

    def tool_qs():
        qs = Tool.objects.all()
        cond = Q()
        if vat_lieu and hasattr(Tool, "vat_lieu_phu_hop"):
            cond |= Q(vat_lieu_phu_hop__icontains=vat_lieu)
        if loai_gia_cong:
            # tuỳ model bạn, giữ rộng để không miss
            if hasattr(Tool, "nhom_tool"):
                cond |= Q(nhom_tool__icontains=loai_gia_cong)
            if hasattr(Tool, "dong_tool"):
                cond |= Q(dong_tool__icontains=loai_gia_cong)
            if hasattr(Tool, "loai_gia_cong"):
                cond |= Q(loai_gia_cong__icontains=loai_gia_cong)
            cond |= Q(ten_tool__icontains=loai_gia_cong) | Q(ma_tool__icontains=loai_gia_cong)
        return qs.filter(cond) if cond else qs

    def holder_qs():
        qs = Holder.objects.all()
        cond = Q()
        if loai_gia_cong:
            if hasattr(Holder, "nhom_thiet_bi"):
                cond |= Q(nhom_thiet_bi__icontains=loai_gia_cong)
            cond |= Q(ten_thiet_bi__icontains=loai_gia_cong) | Q(ma_noi_bo__icontains=loai_gia_cong)
        # vật liệu với holder thường không chắc có field, bạn thêm nếu có
        return qs.filter(cond) if cond else qs

    candidates: List[Any] = []

    # ===== TOOL =====
    if loai in ("tool", "both"):
        tools = list(tool_qs()[: (250 if broad else 160)])
        tools = [t for t in tools if _tool_qty(t) >= min_qty]
        candidates.extend(tools)

    # ===== HOLDER =====
    if loai in ("holder", "both"):
        holders = list(holder_qs()[: (200 if broad else 120)])
        holders = [h for h in holders if _holder_is_available(h)]

        # nếu bạn muốn hard filter độ bền còn lại
        if min_holder_left is not None and min_holder_left > 0:
            keep = []
            for h in holders:
                left = _holder_durability_left(h)
                # thiếu dữ liệu left thì giữ lại (hoặc đổi thành loại nếu bạn muốn chặt)
                if left is None or left >= float(min_holder_left):
                    keep.append(h)
            holders = keep

        candidates.extend(holders)
    if criteria.get("debug"):
        print(
            "[FUZZY][CAND] loai:",
            loai,
            "| min_qty:",
            min_qty,
            "| min_holder_left:",
            min_holder_left
        )
        print(
            "[FUZZY][CAND] candidates after constraint:",
            len(candidates)
        )
    return candidates, loai
