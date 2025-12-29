from django.db.models import Q
from holder.models import Holder

from ..shared.contracts import ok_reply, not_found_reply
from ..shared.rules import extract_code_candidate, normalize
from ..shared.utils import br, link_html, safe
from .mapper import holder_to_card_dict

def _holder_detail_url(h: Holder) -> str:
    return f"/holder/{h.id}/"

def similar_holder_by_code(text: str) -> dict:
    qraw = normalize(text)
    code = extract_code_candidate(qraw)
    if not code:
        return not_found_reply("lookup_similar", "holder", "Bạn gửi mã holder cần tìm tương tự giúp mình nhé.", query=qraw)

    base = Holder.objects.filter(ma_noi_bo__iexact=code).first()
    if not base:
        base = Holder.objects.filter(ma_noi_bo__icontains=code).first()

    # Strategy 1 (ưu tiên): ma_nhom_tuong_thich
    if base and base.ma_nhom_tuong_thich:
        qs = Holder.objects.filter(ma_nhom_tuong_thich=base.ma_nhom_tuong_thich).exclude(id=base.id)[:8]
        strategy = f"ma_nhom_tuong_thich = {base.ma_nhom_tuong_thich}"
    else:
        # Strategy 2 fallback: chuan_ga + loai_kep + duong_kinh_kep_max
        qs = Holder.objects.all()
        strategy = "fallback"
        if base:
            if base.chuan_ga:
                qs = qs.filter(chuan_ga=base.chuan_ga)
                strategy = f"chuan_ga={base.chuan_ga}"
            if base.loai_kep:
                qs = qs.filter(loai_kep=base.loai_kep)
                strategy += f", loai_kep={base.loai_kep}"
            if base.duong_kinh_kep_max is not None:
                qs = qs.filter(duong_kinh_kep_max=base.duong_kinh_kep_max)
                strategy += f", Ømax={base.duong_kinh_kep_max}"
            qs = qs.exclude(id=base.id)[:8]
        else:
            # nếu không có base, fallback theo prefix đơn giản
            qs = Holder.objects.filter(ma_noi_bo__istartswith=code[:4]).order_by("ten_thiet_bi")[:8]
            strategy = f"prefix={code[:4]}"

    if qs.count() == 0:
        return not_found_reply(
            "lookup_similar", "holder",
            f"Không tìm thấy holder tương tự cho “<b>{safe(code)}</b>”.",
            query=code,
        )

    cards = []
    lines = [f"<b>Holder tương tự</b> cho mã: <b>{safe(code)}</b> (strategy: <b>{safe(strategy)}</b>)"]
    for h in qs:
        url = _holder_detail_url(h)
        cards.append(holder_to_card_dict(h))
        lines.append(f"• {safe(h.ten_thiet_bi)} ({safe(h.ma_noi_bo)}) - {link_html('Xem', url)}")

    return ok_reply("lookup_similar", "holder", br(lines), similar=cards, query=code)
