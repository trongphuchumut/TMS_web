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

    # Lấy chữ cái đầu của tủ: "A1" -> "A", "C2" -> "C"
    tu_str = str(tu).strip().upper()
    tu_char = tu_str[0]          # A / B / C

    # Lấy phần số của ngăn: "01" -> 1, "3" -> 3
    ngan_str = str(ngan).strip()
    try:
        ngan_num = int(ngan_str)  # tự bỏ 0 ở đầu
    except ValueError:
        return None

    return f"{tu_char}{ngan_num}"  # vd: "A1"
    

def kho_cong_cu_view(request):
    items = {}

    # ===== TOOL =====
    for t in Tool.objects.all():
        code = build_code(t.tu, t.ngan)
        if not code:
            continue

        items[code] = {
            "name": t.ten_tool,
            "status": "ok" if (t.ton_kho or 0) > 0 else "error",
            "qty": t.ton_kho or 0,
            "url": reverse("tool:tool_profile", args=[t.pk]),
        }

    # ===== HOLDER =====
    for h in Holder.objects.all():
        code = build_code(h.tu, h.ngan)
        if not code:
            continue

        # nếu ngăn đã có tool/holder khác thì thôi, hoặc bạn có thể merge
        if code in items:
            continue

        items[code] = {
            "name": h.ten_thiet_bi,
            "status": "ok",       # tạm thời cho ok, sau này tính theo trạng_thai_tai_san
            "qty": "",            # holder là tài sản, không có số lượng
            "url": "#",           # sau này trỏ sang trang profile holder
        }

    items_json = json.dumps(items, cls=DjangoJSONEncoder)

    return render(
        request,
        "khocongcu.html",
        {
            "items_json": items_json,
        },
    )
