# chatbot/fuzzy/pipeline.py
from typing import Any

from .criteria_parser import call_ai_for_criteria
from .candidates import get_candidates
from .scoring import score_all_candidates
from ..ai_client import call_ai
from tool.models import Tool
from holder.models import Holder


# chatbot/fuzzy/pipeline.py

from typing import Any
from .criteria_parser import call_ai_for_criteria
from .candidates import get_candidates
from .scoring import score_all_candidates
from ..ai_client import call_ai
from tool.models import Tool
from holder.models import Holder


def build_main_answer(scored: list[tuple[float, Any]]) -> str:
    top = [s for s in scored if s[0] > 0][:6]

    if not top:
        return (
            "Hiện chưa tìm được thiết bị nào thực sự phù hợp sau khi lọc. "
            "Bạn thử mô tả chi tiết hơn (vật liệu, kiểu gia công, kích thước, yêu cầu bề mặt...) nhé."
        )

    top_tools: list[tuple[float, Tool]] = []
    top_holders: list[tuple[float, Holder]] = []

    for score, dev in top:
        if isinstance(dev, Tool):
            top_tools.append((score, dev))
        elif isinstance(dev, Holder):
            top_holders.append((score, dev))

    lines: list[str] = []
    lines.append("Dựa trên tiêu chí fuzzy, mình đề xuất:")

    if top_tools:
        lines.append("")
        lines.append("🔧 Tool phù hợp:")
        for score, tool in top_tools[:3]:
            lines.append(
                f"- Tool {tool.ma_tool} – {tool.ten_tool} "
                f"(nhóm {tool.nhom_tool or '?'}) – điểm fuzzy ~ {round(score * 100)}"
            )

    if top_holders:
        lines.append("")
        lines.append("🧱 Holder phù hợp:")
        for score, holder in top_holders[:3]:
            lines.append(
                f"- Holder {holder.ma_noi_bo} – {holder.ten_thiet_bi} "
                f"– điểm fuzzy ~ {round(score * 100)}"
            )

    return "\n".join(lines)



def build_debug_block(
    user_message: str,
    criteria: dict | None,
    raw_ai_criteria: str,
    criteria_err,
    loai_thiet_bi: str,
    candidates: list,
    scored: list[tuple[float, Any]],
) -> str:
    """Ghép block DEBUG chi tiết pipeline để bạn dễ theo dõi / mở rộng."""
    lines: list[str] = []
    lines.append("=== DEBUG fuzzy_suggest ===")
    lines.append(f"user_message: {user_message!r}")
    lines.append("")
    lines.append("---- B1: AI phân tích tiêu chí ----")
    lines.append(f"raw_criteria_from_ai: {raw_ai_criteria!r}")
    if criteria_err:
        lines.append(f"JSON parse error: {repr(criteria_err)}")
    lines.append("")
    lines.append("criteria (parsed):")
    lines.append(str(criteria))

    lines.append("")
    lines.append("---- B2: Candidates từ DB ----")
    lines.append(f"loai_thiet_bi: {loai_thiet_bi}")
    lines.append(f"num_candidates: {len(candidates)}")

    lines.append("")
    lines.append("---- B3: Điểm fuzzy tuyến tính (tối đa 20 dòng) ----")
    for score, dev in scored[:20]:
        if isinstance(dev, Tool):
            ident = f"Tool[{dev.id}] {dev.ma_tool} - {dev.ten_tool}"
        elif isinstance(dev, Holder):
            ident = f"Holder[{dev.id}] {dev.ma_noi_bo} - {dev.ten_thiet_bi}"
        else:
            ident = f"Obj[{getattr(dev, 'id', '?')}]"
        lines.append(f"{ident} -> score={score:.3f}")

    return "\n".join(lines)


def run_fuzzy_suggest(user_message: str, debug: bool = False) -> str:
    """
    Pipeline tổng cho fuzzy:
      - B1: AI phân tích câu nói -> JSON tiêu chí
      - B2: Lọc ứng viên từ DB
      - B3: Chấm điểm fuzzy
      - B4: Build câu trả lời chính
      - (optional) DEBUG: ghép thêm block debug chi tiết phía dưới
    """

    # B1: gọi AI phân tích tiêu chí
    criteria, raw_ai_criteria, criteria_err = call_ai_for_criteria(user_message)

    # Nếu parse JSON lỗi hoàn toàn => dùng fallback text mode
    if criteria is None:
        fallback_prompt = (
            "Bạn là chuyên gia chọn tool/holder. "
            "Hãy đọc mô tả sau và đề xuất vài tool/holder phù hợp, kèm giải thích ngắn.\n\n"
            f"Mô tả: {user_message}"
        )
        fallback_answer = call_ai(fallback_prompt)

        if debug:
            debug_block = (
                "=== DEBUG fuzzy_suggest ===\n"
                "JSON parse error, dùng fallback text mode.\n"
                f"raw_criteria_from_ai: {raw_ai_criteria!r}\n"
                f"error: {repr(criteria_err)}\n"
                f"fallback_prompt: {fallback_prompt!r}"
            )
            return fallback_answer + "\n\n" + debug_block

        return fallback_answer

    # B2: lấy candidates
    candidates, loai_thiet_bi = get_candidates(criteria)

    # B3: chấm điểm
    scored = score_all_candidates(candidates, criteria)

    # B4: câu trả lời chính
    main_answer = build_main_answer(scored)

    if debug:
        debug_block = build_debug_block(
            user_message=user_message,
            criteria=criteria,
            raw_ai_criteria=raw_ai_criteria,
            criteria_err=criteria_err,
            loai_thiet_bi=loai_thiet_bi,
            candidates=candidates,
            scored=scored,
        )
        return main_answer + "\n\n" + debug_block

    return main_answer

# chatbot/fuzzy/pipeline.py (thêm code này)

CRITICAL_FIELDS = ["vat_lieu", "loai_gia_cong"]  # bạn có thể thêm tùy ý


def detect_missing_fields(criteria: dict | None) -> list[str]:
    if not criteria:
        return CRITICAL_FIELDS[:]  # thiếu sạch
    missing = []
    for f in CRITICAL_FIELDS:
        v = criteria.get(f)
        if not v or not str(v).strip():
            missing.append(f)
    return missing

# chatbot/fuzzy/pipeline.py (thêm)

def build_followup_question(missing_fields: list[str]) -> str:
    questions = []

    if "vat_lieu" in missing_fields:
        questions.append("- Vật liệu gia công là gì? (VD: S45C, SUS304, nhôm A6061…)")

    if "loai_gia_cong" in missing_fields:
        questions.append("- Bạn đang cần gia công gì? (khoan / phay mặt phẳng / phay rãnh / taro / doa…)")

    # nếu sau này bổ sung thêm field:
    # if "duong_kinh" in missing_fields:
    #     questions.append("- Đường kính lỗ / dao khoảng bao nhiêu (mm)?")

    if not questions:
        return "Bạn có thể mô tả chi tiết hơn về yêu cầu gia công không?"

    intro = "Mình đã tìm được vài lựa chọn tạm phù hợp, nhưng để đề xuất chính xác hơn, cho mình hỏi thêm:\n"
    return intro + "\n".join(questions)

