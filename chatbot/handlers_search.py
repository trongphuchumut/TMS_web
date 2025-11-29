# chatbot/handlers_search.py
import re
import unicodedata
from difflib import SequenceMatcher

from django.db.models import Q
from django.urls import reverse

from holder.models import Holder
from tool.models import Tool


# ================== Helpers chung ==================

def normalize(text: str) -> str:
    """Lowercase + bỏ dấu tiếng Việt để so fuzzy."""
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def sim(a: str, b: str) -> float:
    """Độ giống nhau ~ [0..1]."""
    a_norm = normalize(a)
    b_norm = normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def extract_keyword(user_message: str) -> str:
    """
    Rút keyword chính:
    - Ưu tiên pattern mã: H-001, T-002, BT40, DRL-5.0, ER32, SK40, MT3, D10...
    - Nếu không bắt được mã -> dùng nguyên câu.
    """
    raw = user_message.strip()

    code_pattern = r"(H-\d+|T-\d+|BT\d+|DRL-[\w\.\-]+|ER\d+|SK\d+|MT\d+|D\d+(\.\d+)?)"
    m = re.search(code_pattern, raw, flags=re.IGNORECASE)
    if m:
        return m.group(0)

    return raw


def extract_tokens(user_message: str) -> list[str]:
    """
    Tách câu thành các token dùng để search:
    'tìm cho tôi BT40 endmill Φ10-16'
      -> ['bt40', 'endmill', '10', '16']
    Bỏ stopword rác kiểu 'tim', 'cho', 'toi'...
    """
    norm = normalize(user_message)
    parts = re.split(r"[^0-9a-z]+", norm)
    tokens = [p for p in parts if len(p) >= 2]

    stopwords = {"tim", "toi", "cho", "giup", "xin", "voi"}
    tokens = [t for t in tokens if t not in stopwords]
    return tokens


def build_holder_url(holder: Holder) -> str:
    """Link profile holder (sửa lại tên URL cho khớp project thật của bạn)."""
    try:
        return reverse("holder:holder_profile", args=[holder.id])
    except Exception:
        return f"/holder/holders/{holder.id}/"


def build_tool_url(tool: Tool) -> str:
    """Link profile tool (sửa lại tên URL cho khớp project thật của bạn)."""
    try:
        return reverse("tool:tool_detail", args=[tool.id])
    except Exception:
        return f"/tool/{tool.id}/"


# ================== Core search ==================

def _search_candidates(keyword: str, tokens: list[str]):
    """
    Tìm nhanh trong DB (cả Holder + Tool) theo icontains từng token,
    sau đó tính fuzzy score để chọn món gần nhất.
    Trả về list candidates đã có score, sort giảm dần.
    """
    keyword = (keyword or "").strip()
    if not tokens and not keyword:
        return []

    if not tokens and keyword:
        tokens = [normalize(keyword)]

    print("[SEARCH_DEBUG] Tokens used for query:", tokens)

    # ========== HOLDER ==========
    holder_q = Q()
    for tok in tokens:
        holder_q |= (
            Q(ma_noi_bo__icontains=tok)
            | Q(ten_thiet_bi__icontains=tok)
            | Q(ma_nha_sx__icontains=tok)
            | Q(nhom_thiet_bi__icontains=tok)
            | Q(chuan_ga__icontains=tok)
            | Q(loai_kep__icontains=tok)
        )
    holders_qs = Holder.objects.filter(holder_q)[:30]

    # ========== TOOL ==========
    tool_q = Q()
    for tok in tokens:
        tool_q |= (
            Q(ma_tool__icontains=tok)
            | Q(ten_tool__icontains=tok)
            | Q(nhom_tool__icontains=tok)
            | Q(ma_nha_sx__icontains=tok)
            | Q(model__icontains=tok)
            | Q(vat_lieu_phu_hop__icontains=tok)
            | Q(ghi_chu__icontains=tok)
            | Q(che_do_cat_khuyen_nghi__icontains=tok)
        )
    tools_qs = Tool.objects.filter(tool_q)[:30]

    print(f"[SEARCH_DEBUG] Holders matched (pre-score): {holders_qs.count()}")
    print(f"[SEARCH_DEBUG] Tools matched (pre-score): {tools_qs.count()}")

    candidates = []

    # Score cho Holder
    for h in holders_qs:
        fields = [
            h.ma_noi_bo or "",
            h.ten_thiet_bi or "",
            h.nhom_thiet_bi or "",
            h.ma_nha_sx or "",
            h.chuan_ga or "",
            h.loai_kep or "",
        ]
        scores = []
        if keyword:
            scores.append(max(sim(keyword, f) for f in fields if f))
        for tok in tokens:
            scores.append(max(sim(tok, f) for f in fields if f))
        score = max(scores) if scores else 0.0

        candidates.append({
            "type": "holder",
            "obj": h,
            "score": score,
        })

    # Score cho Tool
    for t in tools_qs:
        fields = [
            t.ma_tool or "",
            t.ten_tool or "",
            t.nhom_tool or "",
            t.ma_nha_sx or "",
            t.model or "",
            t.vat_lieu_phu_hop or "",
            t.ghi_chu or "",
            t.che_do_cat_khuyen_nghi or "",
        ]
        scores = []
        if keyword:
            scores.append(max(sim(keyword, f) for f in fields if f))
        for tok in tokens:
            scores.append(max(sim(tok, f) for f in fields if f))
        score = max(scores) if scores else 0.0

        candidates.append({
            "type": "tool",
            "obj": t,
            "score": score,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def _summarize_holder(h: Holder) -> str:
    trang_thai = dict(Holder.TRANG_THAI_CHOICES).get(h.trang_thai_tai_san, "Không rõ")
    return (
        f"• Mã: {h.ma_noi_bo}\n"
        f"• Tên: {h.ten_thiet_bi}\n"
        f"• Nhóm: {h.nhom_thiet_bi}\n"
        f"• Chuẩn gá: {h.chuan_ga or '—'}, Loại kẹp: {h.loai_kep or '—'}\n"
        f"• Vị trí: Tủ {h.tu or '?'}, Ngăn {h.ngan or '?'}\n"
        f"• Trạng thái: {trang_thai}"
    )


def _summarize_tool(t: Tool) -> str:
    return (
        f"• Mã: {t.ma_tool}\n"
        f"• Tên: {t.ten_tool}\n"
        f"• Nhóm: {t.nhom_tool}\n"
        f"• Đường kính: {t.duong_kinh or '—'} mm, "
        f"Chiều dài LV: {t.chieu_dai_lam_viec or '—'} mm\n"
        f"• Tồn kho: {t.ton_kho} (mức cảnh báo: {t.muc_canh_bao or 'chưa đặt'})\n"
        f"• Vị trí: Tủ {t.tu or '?'}, Ngăn {t.ngan or '?'}"
    )


# ================== Hàm public cho chatbot ==================

def handle_search_device(request, user_message: str) -> str:
    """
    Phiên bản mới:
    - KHÔNG xử lý 'đúng/không' ở đây nữa.
    - Chỉ:
      + Tìm candidates
      + Nếu score cao -> trả luôn
      + Nếu score vừa -> hỏi confirm và set session["device_confirm_state"]
    Còn 'đúng/không' sẽ do view + handle_search_confirm xử lý.
    """
    keyword = extract_keyword(user_message)
    tokens = extract_tokens(user_message)

    print("[SEARCH] User message:", user_message)
    print("[SEARCH] Keyword extracted:", keyword)
    print("[SEARCH] Tokens extracted:", tokens)

    candidates = _search_candidates(keyword, tokens)
    if not candidates:
        return "Mình không tìm thấy holder hoặc tool nào phù hợp với từ khóa này trong kho."

    best = candidates[0]
    best_score = best["score"]
    obj_type = best["type"]
    obj = best["obj"]

    print(f"[SEARCH] Best match: {obj_type} id={obj.id} score={best_score:.2f}")

    AUTO_SHOW_THRESHOLD = 0.90   # rất chắc
    CONFIRM_THRESHOLD = 0.70     # tạm được, cần hỏi lại

    # ====== 1) Tự tin cao -> trả luôn ======
    if best_score >= AUTO_SHOW_THRESHOLD:
        if obj_type == "holder":
            url = build_holder_url(obj)
            summary = _summarize_holder(obj)
            return (
                "Mình tìm được thiết bị phù hợp nhất là holder sau:\n\n"
                f"{summary}\n\n"
                f'🔗 <a href="{url}" target="_blank" class="chatbot-link">Xem chi tiết</a>'
            )
        else:
            url = build_tool_url(obj)
            summary = _summarize_tool(obj)
            return (
                "Mình tìm được công cụ phù hợp nhất là tool sau:\n\n"
                f"{summary}\n\n"
                f'🔗 <a href="{url}" target="_blank" class="chatbot-link">Xem chi tiết</a>'
            )

    # ====== 2) Score trung bình -> hỏi confirm, set device_confirm_state ======
    if best_score >= CONFIRM_THRESHOLD:
        if obj_type == "holder":
            code = obj.ma_noi_bo
            name = obj.ten_thiet_bi
            label = "holder"
        else:
            code = obj.ma_tool
            name = obj.ten_tool
            label = "tool"

        # 🔴 LƯU STATE ĐỂ VIEW XỬ LÝ YES/NO Ở REQUEST SAU
        request.session["device_confirm_state"] = {
            "type": obj_type,
            "id": obj.id,
            "code": code,
            "name": name,
        }
        request.session.modified = True

        return (
            f"Bạn đang hỏi về **{label} {code} - {name}** phải không?\n"
            "Nếu đúng thì trả lời 'đúng', nếu không đúng thì trả lời 'không' giúp mình nhé."
        )

    # ====== 3) Score thấp -> đưa top 3 gợi ý ======
    top_lines = []
    for c in candidates[:3]:
        if c["type"] == "holder":
            h = c["obj"]
            top_lines.append(f"- Holder {h.ma_noi_bo}: {h.ten_thiet_bi} (score ~ {c['score']:.2f})")
        else:
            t = c["obj"]
            top_lines.append(f"- Tool {t.ma_tool}: {t.ten_tool} (score ~ {c['score']:.2f})")

    return (
        "Từ khóa này khá mơ hồ, mình chưa đoán ra chính xác thiết bị nào bạn muốn.\n"
        "Một vài gợi ý gần nhất:\n"
        + "\n".join(top_lines)
        + "\n\nBạn thử gõ mã hoặc tên thiết bị rõ hơn một chút nhé."
    )


def handle_search_confirm(request, user_message: str, state: dict, intent: str):
    """
    Xử lý khi user trả lời 'đúng' / 'không' (intent đã là confirm_yes / confirm_no).
    - state: lấy từ session["device_confirm_state"]
    - intent: 'confirm_yes' hoặc 'confirm_no'
    Trả:
      - reply: str
      - done: bool -> True nếu kết thúc flow confirm
    """
    candidate_id = state.get("id")
    candidate_type = state.get("type")

    holder = None
    tool = None

    if candidate_type == "holder" and candidate_id:
        try:
            holder = Holder.objects.get(pk=candidate_id)
        except Holder.DoesNotExist:
            holder = None

    if candidate_type == "tool" and candidate_id:
        try:
            tool = Tool.objects.get(pk=candidate_id)
        except Tool.DoesNotExist:
            tool = None

    if intent == "confirm_yes":
        # User xác nhận đúng thiết bị
        if holder:
            url = build_holder_url(holder)
            summary = _summarize_holder(holder)
            reply = (
                "✅ Đúng rồi, đây là holder bạn hỏi:\n\n"
                f"{summary}\n\n"
                f'🔗 <a href="{url}" target="_blank" class="chatbot-link">Xem chi tiết</a>'
            )
        elif tool:
            url = build_tool_url(tool)
            summary = _summarize_tool(tool)
            reply = (
                "✅ Đúng rồi, đây là công cụ bạn hỏi:\n\n"
                f"{summary}\n\n"
                f'🔗 <a href="{url}" target="_blank" class="chatbot-link">Xem chi tiết</a>'
            )
        else:
            reply = (
                "Mình vừa bị mất thông tin thiết bị trong hệ thống, "
                "bạn mô tả lại mã hoặc tên thiết bị giúp mình nhé."
            )
        done = True

    else:  # confirm_no
        reply = (
            "Ok, vậy bạn mô tả lại mã hoặc tên thiết bị, "
            "hoặc mô tả rõ hơn (nhóm, chuẩn gá, vị trí tủ/ngăn) để mình tìm lại cho chính xác nhé."
        )
        done = True

    return reply, done
