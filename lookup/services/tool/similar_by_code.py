from django.db.models import Q
from tool.models import Tool

from ..shared.contracts import ok_reply, not_found_reply
from ..shared.rules import extract_code_candidate, tool_prefix, normalize
from ..shared.utils import br, link_html, safe
from .mapper import tool_to_card_dict

def _tool_detail_url(t: Tool) -> str:
    return f"/tool/{t.id}/"

def similar_tool_by_code(text: str) -> dict:
    qraw = normalize(text)
    code = extract_code_candidate(qraw)
    if not code:
        return not_found_reply("lookup_similar", "tool", "Bạn gửi mã tool cần tìm tương tự giúp mình nhé.", query=qraw)

    prefix = tool_prefix(code)

    # ưu tiên: same prefix ma_tool
    qs = Tool.objects.filter(ma_tool__istartswith=prefix).order_by("ten_tool")[:8]

    # fallback: nếu prefix ra ít quá thì thử cùng nhom_tool/dong_tool (dựa trên record match)
    if qs.count() == 0:
        base = Tool.objects.filter(ma_tool__icontains=code).first()
        if base:
            qs = Tool.objects.filter(
                Q(nhom_tool=base.nhom_tool) | Q(dong_tool=base.dong_tool)
            ).exclude(id=base.id).order_by("ten_tool")[:8]

    if qs.count() == 0:
        return not_found_reply(
            "lookup_similar", "tool",
            f"Không tìm thấy mã tương tự cho “<b>{safe(code)}</b>”.",
            query=code,
        )

    cards = []
    lines = [f"<b>Tool tương tự</b> cho mã: <b>{safe(code)}</b> (strategy: prefix <b>{safe(prefix)}</b>)"]
    for t in qs:
        url = _tool_detail_url(t)
        cards.append(tool_to_card_dict(t))
        lines.append(f"• {safe(t.ten_tool)} ({safe(t.ma_tool)}) - {link_html('Xem', url)}")

    return ok_reply("lookup_similar", "tool", br(lines), similar=cards, query=code)
