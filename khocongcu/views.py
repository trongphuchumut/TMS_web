# khocongcu/views.py
import json
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render

from tool.models import Tool
from holder.models import Holder


def build_code(tu, ngan):
    """
    Chuẩn hóa về dạng A1..A9, B1..B9, C1..C9
    """
    if not tu or not ngan:
        return None

    tu_str = str(tu).strip().upper()
    tu_char = tu_str[0]          # A / B / C

    ngan_str = str(ngan).strip()
    try:
        ngan_num = int(ngan_str)  # tự bỏ 0 ở đầu
    except ValueError:
        return None

    return f"{tu_char}{ngan_num}"  # vd: "A1"


def kho_cong_cu_view(request):
    # bucket tạm: code -> list các item (tool/holder)
    bucket = {}

    # ===== TOOL =====
    for t in Tool.objects.all():
        code = build_code(t.tu, t.ngan)
        if not code:
            continue

        bucket.setdefault(code, []).append({
            "label": f"Tool: {t.ten_tool}",
            "name": t.ten_tool,
            "status": "ok" if (t.ton_kho or 0) > 0 else "error",
            "qty": t.ton_kho or 0,
            "url": reverse("tool:tool_profile", args=[t.pk]),
        })

    # ===== HOLDER =====
    # ===== HOLDER =====
    for h in Holder.objects.all():
        code = build_code(h.tu, h.ngan)
        if not code:
            continue

        bucket.setdefault(code, []).append({
            "label": f"Holder: {h.ten_thiet_bi}",
            "name": h.ten_thiet_bi,
            "status": "ok",   # sau này cập nhật theo trạng_thai_tai_san
            "qty": "",
            "url": reverse("holder:holder_detail", args=[h.pk]),

        })


    # === Build cấu trúc items cho template ===
    items = {}

    for code, lst in bucket.items():
        if len(lst) == 1:
            # chỉ 1 loại → giữ format cũ để JS chạy nhánh 1 loại
            items[code] = lst[0]
        else:
            # nhiều loại → dùng format mới, JS sẽ vào nhánh dual
            items[code] = {
                "items": lst
            }

    items_json = json.dumps(items, cls=DjangoJSONEncoder)

    return render(
        request,
        "khocongcu.html",
        {
            "items_json": items_json,
        },
    )
