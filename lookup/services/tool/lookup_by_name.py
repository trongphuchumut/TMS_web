from django.db.models import Q
from tool.models import Tool

from ..shared.contracts import ok_reply, not_found_reply
from ..shared.rules import normalize, extract_code_candidate
from .mapper import tool_to_card_dict, render_tool_reply

def _tool_detail_url(t: Tool) -> str:
    # Best-effort: nếu bạn có URL detail khác, đổi 1 chỗ này là xong
    return f"/tool/{t.id}/"

def lookup_tool_by_name(text: str) -> dict:
    qraw = normalize(text)
    if not qraw:
        return not_found_reply("lookup_name", "tool", "Bạn gửi tên/mã tool giúp mình nhé.", query=text)

    code = extract_code_candidate(qraw)

    # ưu tiên match ma_tool exact
    obj = Tool.objects.filter(ma_tool__iexact=code).first()
    if not obj:
        # fallback: search theo nhiều field
        obj = (
            Tool.objects.filter(
                Q(ten_tool__icontains=qraw)
                | Q(ma_tool__icontains=qraw)
                | Q(model__icontains=qraw)
                | Q(ma_nha_sx__icontains=qraw)
                | Q(nhom_tool__icontains=qraw)
                | Q(dong_tool__icontains=qraw)
            )
            .order_by("ten_tool")
            .first()
        )

    if not obj:
        return not_found_reply(
            "lookup_name", "tool",
            f"Không tìm thấy tool theo “<b>{qraw}</b>”. Bạn thử nhập đúng <b>ma_tool</b> hoặc tên gần đúng hơn nhé.",
            query=qraw,
        )

    url = _tool_detail_url(obj)
    reply = render_tool_reply(obj, url)
    return ok_reply("lookup_name", "tool", reply, item=tool_to_card_dict(obj), query=qraw)
