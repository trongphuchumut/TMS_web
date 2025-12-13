# chatbot/fuzzy/pipeline.py
from __future__ import annotations
from .plot_builder import build_plot

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .criteria_parser import call_ai_for_criteria
from .candidates import get_candidates
from .scoring import score_all_candidates
from tool.models import Tool
from holder.models import Holder


# Các field tối thiểu để fuzzy "đủ thông tin" cho đề xuất tự tin
CRITICAL_FIELDS = ("vat_lieu", "loai_gia_cong")


def _filled_fields(criteria: dict) -> List[str]:
    keys = []
    for k in ("loai_gia_cong", "vat_lieu", "duong_kinh", "chieu_dai_lam_viec", "yeu_cau_be_mat", "do_chinh_xac"):
        v = criteria.get(k) if isinstance(criteria, dict) else None
        if v not in (None, "", []):
            keys.append(k)
    return keys


def _missing_critical(criteria: dict) -> List[str]:
    missing = []
    for k in CRITICAL_FIELDS:
        if not criteria.get(k):
            missing.append(k)
    return missing


def _build_followup_question(missing: List[str]) -> str:
    # Hỏi ngắn, có ví dụ để user trả lời nhanh
    if not missing:
        return "Bạn có thể bổ sung thêm chi tiết (ví dụ: vật liệu, loại gia công, đường kính) để mình chấm fuzzy chính xác hơn không?"
    if missing == ["vat_lieu"]:
        return "Bạn đang gia công vật liệu gì? (vd: C45, S45C, SUS304, nhôm 6061...)"
    if missing == ["loai_gia_cong"]:
        return "Bạn đang làm dạng gia công nào? (vd: khoan / phay / taro / doa / tiện...)"
    return "Mình cần thêm: " + ", ".join(missing) + ". Bạn bổ sung giúp mình nhé."


def _build_result_text(scored: List[Tuple[float, Any, dict]], topk: int, criteria: dict, mode: str) -> str:
    top = scored[:topk]
    if not top:
        return (
            "Hiện chưa tìm được thiết bị phù hợp sau khi chấm fuzzy. "
            "Bạn thử mô tả rõ hơn (vật liệu, kiểu gia công, kích thước, yêu cầu bề mặt...) nhé."
        )

    lines = []
    lines.append("✅ **Kết quả đề xuất theo FUZZY (điểm 0..100):**")
    for i, (s, dev, br) in enumerate(top, 1):
        name = getattr(dev, "ten_tool", None) or getattr(dev, "ten_thiet_bi", None) or str(dev)
        code = getattr(dev, "ma_tool", None) or getattr(dev, "ma_noi_bo", None) or ""
        score100 = round(s * 100, 1)
        lines.append(f"{i}. **{name}** {f'({code})' if code else ''}  ➜  **{score100}**")
        # mini explain: show top 2 criteria contributions
        if br:
            ranked = sorted(br.items(), key=lambda x: x[1], reverse=True)[:3]
            why = ", ".join([f"{k}:{round(v*100)}%" for k, v in ranked])
            lines.append(f"   - vì khớp: {why}")

    # gợi ý hỏi "tại sao"
    lines.append("")
    lines.append("🧠 Bạn có thể hỏi: **“Tại sao chọn số 1?”** để mình giải thích chi tiết theo từng tiêu chí fuzzy.")
    return "\n".join(lines)


def run_fuzzy_suggest(user_message: str, debug: bool = False, model: str | None = None) -> dict:
    """
    Trả về dict:
    {
      status: "ok" | "need_more_info" | "error",
      message: str,
      criteria: dict|None,
      scored: list (top scored raw) để dùng làm UI/debug,
      meta: {...}  (confidence, filled_fields, topk_mode, ...)
    }
    """
    criteria, raw, err = call_ai_for_criteria(user_message, model=model)

    if debug:
        print("[FUZZY] model:", model)
        print("[FUZZY] raw criteria:", raw[:500])
        print("[FUZZY] parse err:", err)

    if not criteria:
        return {
            "status": "error",
            "message": "Mình chưa tách được tiêu chí từ câu hỏi (AI parse lỗi). Bạn thử mô tả lại rõ hơn nhé.",
            "criteria": None,
            "scored": [],
            "meta": {"parse_error": str(err) if err else None},
        }

    filled = _filled_fields(criteria)
    missing_crit = _missing_critical(criteria)

    # Nếu thiếu critical -> hỏi thêm (fuzzy follow-up)
    if missing_crit:
        q = _build_followup_question(missing_crit)
        return {
            "status": "need_more_info",
            "message": "⚠️ Chưa đủ thông tin để chấm FUZZY chuẩn.\n" + q,
            "criteria": criteria,
            "scored": [],
            "meta": {"filled_fields": filled, "missing": missing_crit, "confidence": criteria.get("confidence", 0.5)},
        }

    # Lấy candidates + chấm điểm
    candidates, used_type = get_candidates(criteria)
    scored = score_all_candidates(candidates, criteria)

    # Quy tắc top-k theo độ "đủ thông tin":
    if len(filled) <= 2:
        topk = 3
        mode = "few_fields_top3"
    elif len(filled) <= 3:
        topk = 2
        mode = "mid_fields_top2"
    else:
        topk = 1
        mode = "rich_fields_top1"

    msg = _build_result_text(scored, topk=topk, criteria=criteria, mode=mode)

    gap = None
    if len(scored) >= 2:
        gap = float(scored[0][0] - scored[1][0])
    plot = build_plot(criteria, scored)

    if debug:
        print("[FUZZY][PLOT] keys:", plot.get("criteria", {}).keys())

    return {
        "status": "ok",
        "message": msg,
        "criteria": criteria,
        "scored": scored[:10],
        "meta": {
            "loai_thiet_bi": used_type,
            "filled_fields": filled,
            "missing": missing_crit,
            "confidence": float(criteria.get("confidence", 0.5)),
            "topk_mode": mode,
            "gap_top12": gap,
            "plot": plot,   # ✅ QUAN TRỌNG
        },
    }

