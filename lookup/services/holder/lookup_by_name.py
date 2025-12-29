from django.db.models import Q
from holder.models import Holder

from ..shared.contracts import ok_reply, not_found_reply
from ..shared.rules import normalize, extract_code_candidate
from .mapper import holder_to_card_dict, render_holder_reply

def _holder_detail_url(h: Holder) -> str:
    return f"/holder/{h.id}/"

def lookup_holder_by_name(text: str) -> dict:
    qraw = normalize(text)
    if not qraw:
        return not_found_reply("lookup_name", "holder", "Bạn gửi tên/mã holder giúp mình nhé.", query=text)

    code = extract_code_candidate(qraw)

    obj = Holder.objects.filter(ma_noi_bo__iexact=code).first()
    if not obj:
        obj = (
            Holder.objects.filter(
                Q(ten_thiet_bi__icontains=qraw)
                | Q(ma_noi_bo__icontains=qraw)
                | Q(ma_nha_sx__icontains=qraw)
                | Q(chuan_ga__icontains=qraw)
                | Q(loai_kep__icontains=qraw)
                | Q(nhom_thiet_bi__icontains=qraw)
            )
            .order_by("ten_thiet_bi")
            .first()
        )

    if not obj:
        return not_found_reply(
            "lookup_name", "holder",
            f"Không tìm thấy holder theo “<b>{qraw}</b>”. Bạn thử nhập đúng <b>ma_noi_bo</b> hoặc tên gần đúng hơn nhé.",
            query=qraw,
        )

    url = _holder_detail_url(obj)
    reply = render_holder_reply(obj, url)
    return ok_reply("lookup_name", "holder", reply, item=holder_to_card_dict(obj), query=qraw)
