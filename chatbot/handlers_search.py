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
    """Lowercase + bỏ dấu tiếng Việt + strip."""
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


def is_number_token(tok: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?", tok))


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _expand_alphanum_tokens(tokens: list[str]) -> list[str]:
    """
    Expand token kiểu 'hss7' -> ['hss7','hss','7']
    Expand token kiểu 'bt40' -> ['bt40','bt','40']
    """
    expanded: list[str] = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue

        m = re.fullmatch(r"([a-z]+)(\d+(?:\.\d+)?)", tok)
        if m:
            expanded += [tok, m.group(1), m.group(2)]
            continue

        m2 = re.fullmatch(r"(\d+(?:\.\d+)?)([a-z]+)", tok)
        if m2:
            expanded += [tok, m2.group(2), m2.group(1)]
            continue

        expanded.append(tok)

    return _dedupe_keep_order(expanded)


def _normalize_synonyms(tokens: list[str]) -> list[str]:
    mapping = {
        "carbida": "carbide",
        "carbid": "carbide",
        # nếu DB bạn dùng 'cbd' trong mã thì giữ cả 2 để match tốt
        "cbd": "cbd",
        "hss": "hss",
    }
    out = []
    for t in tokens:
        out.append(mapping.get(t, t))
    return out


def _extract_diameter_candidates(raw_text: str) -> list[float]:
    """
    Bắt đường kính từ câu:
    - 'phi 7', 'Φ7', 'ø7', 'd7'
    - '7 ly'
    - 'hss7', 'carbide8'
    """
    raw = (raw_text or "")
    raw = raw.replace("φ", "phi").replace("Φ", "phi").replace("ø", "phi").replace("Ø", "phi")

    t = normalize(raw)
    nums: list[float] = []

    for m in re.finditer(r"(?:\bphi\b|\bd\b)\s*(\d+(?:\.\d+)?)", t):
        try:
            nums.append(float(m.group(1)))
        except ValueError:
            pass

    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:ly|li)\b", t):
        try:
            nums.append(float(m.group(1)))
        except ValueError:
            pass

    for m in re.finditer(r"\b(?:hss|carbide|cbd)\s*(\d+(?:\.\d+)?)\b", t):
        try:
            nums.append(float(m.group(1)))
        except ValueError:
            pass

    # dedupe
    return list(dict.fromkeys(nums))


def _detect_preference(tokens: list[str], raw_text: str) -> dict:
    """
    Nhận diện user nghiêng TOOL hay HOLDER (đỡ nhảy holder bậy).
    """
    tnorm = normalize(raw_text)

    # holder hints
    holder_pat = r"\b(bt\d+|er\d+|sk\d+|hsk\d+|mt\d+)\b"
    holder_strong = bool(re.search(holder_pat, tnorm)) or any(
        x in tokens for x in ("holder", "do", "ga", "do_ga", "bau", "kep", "collet")
    )

    # tool hints
    tool_pat = r"\b(drl|tap|ream|mill|endmill|insert|hss|carbide|cbd)\b"
    tool_strong = bool(re.search(tool_pat, tnorm)) or any(
        x in tokens for x in ("khoan", "mui", "dao", "taro", "doa", "phay")
    )

    dia_nums = _extract_diameter_candidates(raw_text)
    if dia_nums and any(x in tokens for x in ("khoan", "hss", "carbide", "cbd", "drl")):
        tool_strong = True

    return {
        "tool_strong": tool_strong,
        "holder_strong": holder_strong,
        "dia_nums": dia_nums,
    }


# ================== Keyword/tokens ==================

def extract_keyword(user_message: str) -> str:
    """
    Ưu tiên pattern mã: H-001, T-002, BT40, DRL-..., ER32, SK40, MT3, D10...
    """
    raw = (user_message or "").strip()
    code_pattern = r"(H-\d+|T-\d+|BT\d+|DRL-[\w\.\-]+|ER\d+|SK\d+|MT\d+|D\d+(\.\d+)?)"
    m = re.search(code_pattern, raw, flags=re.IGNORECASE)
    if m:
        return m.group(0)
    return raw


def extract_tokens(user_message: str) -> list[str]:
    """
    - Token chữ: >= 2 ký tự
    - Token số: cho phép 1 chữ số (7,8,9...)
    - Expand hss7 -> hss + 7
    """
    norm = normalize(user_message)
    parts = re.split(r"[^0-9a-z]+", norm)

    tokens: list[str] = []
    for p in parts:
        if not p:
            continue
        if p.isdigit():
            tokens.append(p)
        elif len(p) >= 2:
            tokens.append(p)

    stopwords = {
        "tim", "kiem", "toi", "cho", "giup", "xin", "voi",
        "thiet", "bi", "trong", "kho", "cua",
        "vi", "tri", "o", "dau", "nay", "thoi",
        "can", "muon", "lay", "so", "luong", "con",
        "bao", "nhieu",
    }
    tokens = [t for t in tokens if t not in stopwords]

    tokens = _expand_alphanum_tokens(tokens)
    tokens = _normalize_synonyms(tokens)

    return tokens


# ================== URL builders ==================

def build_holder_url(holder: Holder) -> str:
    try:
        return reverse("holder:holder_profile", args=[holder.id])
    except Exception:
        return f"/holder/holders/{holder.id}/"


def build_tool_url(tool: Tool) -> str:
    try:
        return reverse("tool:tool_detail", args=[tool.id])
    except Exception:
        return f"/tool/{tool.id}/"


# ================== Core search ==================

def _search_candidates(keyword: str, tokens: list[str], raw_text: str):
    """
    Tìm Holder + Tool theo icontains token, rồi chấm điểm.
    - Nếu tool_strong và không có holder hint -> không query holder
    - Token số là ràng buộc mạnh cho tool
    - Weighted-average + penalty nếu lệch số
    """
    keyword = (keyword or "").strip()
    if not tokens and not keyword:
        return []

    if not tokens and keyword:
        tokens = [normalize(keyword)]

    pref = _detect_preference(tokens, raw_text)
    tool_strong = pref["tool_strong"]
    holder_strong = pref["holder_strong"]
    dia_nums = pref["dia_nums"]

    print("[SEARCH_DEBUG] Tokens used:", tokens)
    print("[SEARCH_DEBUG] Preference tool_strong=", tool_strong, "holder_strong=", holder_strong, "dia_nums=", dia_nums)

    # ========= HOLDER QS =========
    holders = []
    if not (tool_strong and not holder_strong):
        holder_q = Q()
        for tok in tokens:
            # số mà không có holder-hint -> bỏ qua khi tìm holder (tránh nhiễu)
            if is_number_token(tok) and (not holder_strong):
                continue
            holder_q |= (
                Q(ma_noi_bo__icontains=tok)
                | Q(ten_thiet_bi__icontains=tok)
                | Q(ma_nha_sx__icontains=tok)
                | Q(nhom_thiet_bi__icontains=tok)
                | Q(chuan_ga__icontains=tok)
                | Q(loai_kep__icontains=tok)
            )
        if holder_q:
            holders = list(Holder.objects.filter(holder_q)[:30])

    # ========= TOOL QS =========
    tools = []
    if not (holder_strong and not tool_strong):
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

        qs = Tool.objects.filter(tool_q) if tool_q else Tool.objects.none()

        # nếu bắt được đường kính -> lọc thêm theo duong_kinh (nếu field tồn tại)
        if dia_nums:
            try:
                eps = 0.15
                dia_q = Q()
                for d in dia_nums:
                    dia_q |= Q(duong_kinh__gte=d - eps, duong_kinh__lte=d + eps)
                qs = qs.filter(dia_q)
            except Exception:
                pass

        tools = list(qs[:30])

    print(f"[SEARCH_DEBUG] Holders matched (pre-score): {len(holders)}")
    print(f"[SEARCH_DEBUG] Tools matched (pre-score): {len(tools)}")

    candidates: list[dict] = []

    # ===== HOLDER scoring =====
    for h in holders:
        fields = [
            getattr(h, "ma_noi_bo", "") or "",
            getattr(h, "ten_thiet_bi", "") or "",
            getattr(h, "nhom_thiet_bi", "") or "",
            getattr(h, "ma_nha_sx", "") or "",
            getattr(h, "chuan_ga", "") or "",
            getattr(h, "loai_kep", "") or "",
        ]

        total = 0.0
        wsum = 0.0

        if keyword:
            s_kw = max(sim(keyword, f) for f in fields if f)
            total += 1.0 * s_kw
            wsum += 1.0

        for tok in tokens:
            s_tok = max(sim(tok, f) for f in fields if f)
            w = 1.0
            if re.fullmatch(r"(bt|er|sk|hsk|mt)\d+", tok):
                w = 2.5
            total += w * s_tok
            wsum += w

        score = (total / wsum) if wsum else 0.0
        candidates.append({"type": "holder", "obj": h, "score": score})

    # ===== TOOL scoring =====
    for t in tools:
        fields = [
            getattr(t, "ma_tool", "") or "",
            getattr(t, "ten_tool", "") or "",
            getattr(t, "nhom_tool", "") or "",
            getattr(t, "ma_nha_sx", "") or "",
            getattr(t, "model", "") or "",
            getattr(t, "vat_lieu_phu_hop", "") or "",
            getattr(t, "ghi_chu", "") or "",
            getattr(t, "che_do_cat_khuyen_nghi", "") or "",
        ]

        total = 0.0
        wsum = 0.0

        if keyword:
            s_kw = max(sim(keyword, f) for f in fields if f)
            total += 1.0 * s_kw
            wsum += 1.0

        hay = normalize((getattr(t, "ten_tool", "") or "") + " " + (getattr(t, "ma_tool", "") or ""))

        for tok in tokens:
            s_tok = max(sim(tok, f) for f in fields if f)
            w = 1.0

            if is_number_token(tok):
                w = 3.0
                # nếu số KHÔNG xuất hiện trong tên/mã -> phạt rất nặng
                if tok not in hay:
                    s_tok *= 0.15
                else:
                    s_tok = max(s_tok, 1.0)

                # bonus thêm nếu có field duong_kinh và khớp gần đúng
                try:
                    d = float(tok)
                    dk = getattr(t, "duong_kinh", None)
                    if dk is not None:
                        diff = abs(float(dk) - d)
                        if diff <= 0.05:
                            s_tok = max(s_tok, 1.0)
                        elif diff <= 0.20:
                            s_tok = max(s_tok, 0.85)
                except Exception:
                    pass

            # token nằm trong mã -> boost nhẹ
            if tok and tok in normalize(getattr(t, "ma_tool", "") or ""):
                s_tok = min(s_tok * 1.2, 1.0)

            total += w * s_tok
            wsum += w

        score = (total / wsum) if wsum else 0.0
        candidates.append({"type": "tool", "obj": t, "score": score})

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


# ================== Summaries ==================

def _summarize_holder(h: Holder) -> str:
    trang_thai = dict(getattr(Holder, "TRANG_THAI_CHOICES", [])).get(getattr(h, "trang_thai_tai_san", None), "Không rõ")
    return (
        f"• Mã: {getattr(h, 'ma_noi_bo', '')}\n"
        f"• Tên: {getattr(h, 'ten_thiet_bi', '')}\n"
        f"• Nhóm: {getattr(h, 'nhom_thiet_bi', '')}\n"
        f"• Chuẩn gá: {getattr(h, 'chuan_ga', None) or '—'}, Loại kẹp: {getattr(h, 'loai_kep', None) or '—'}\n"
        f"• Vị trí: Tủ {getattr(h, 'tu', None) or '?'}, Ngăn {getattr(h, 'ngan', None) or '?'}\n"
        f"• Trạng thái: {trang_thai}"
    )


def _summarize_tool(t: Tool) -> str:
    return (
        f"• Mã: {getattr(t, 'ma_tool', '')}\n"
        f"• Tên: {getattr(t, 'ten_tool', '')}\n"
        f"• Nhóm: {getattr(t, 'nhom_tool', '')}\n"
        f"• Đường kính: {getattr(t, 'duong_kinh', None) or '—'} mm, "
        f"Chiều dài LV: {getattr(t, 'chieu_dai_lam_viec', None) or '—'} mm\n"
        f"• Tồn kho: {getattr(t, 'ton_kho', None)} (mức cảnh báo: {getattr(t, 'muc_canh_bao', None) or 'chưa đặt'})\n"
        f"• Vị trí: Tủ {getattr(t, 'tu', None) or '?'}, Ngăn {getattr(t, 'ngan', None) or '?'}"
    )


# ================== Public API ==================

def handle_search_device(request, user_message: str) -> str:
    """
    Flow:
    - Tìm candidates
    - Nếu unique result -> TRẢ THẲNG (đây là fix chính cho case của bạn)
    - Nếu score rất cao -> trả luôn
    - Nếu score vừa -> hỏi confirm (set session device_confirm_state)
    - Nếu thấp -> show top 3
    """
    keyword = extract_keyword(user_message)
    tokens = extract_tokens(user_message)

    print("[SEARCH] User message:", user_message)
    print("[SEARCH] Keyword extracted:", keyword)
    print("[SEARCH] Tokens extracted:", tokens)

    if not tokens and not keyword:
        return "Bạn cho mình thêm thông tin nhé: mã, tên, Φ/đường kính, chuẩn gá (BT/ER/SK)…"

    candidates = _search_candidates(keyword, tokens, raw_text=user_message)
    if not candidates:
        return "Mình không tìm thấy holder hoặc tool nào phù hợp với từ khóa này trong kho."

    best = candidates[0]
    best_score = float(best["score"])
    obj_type = best["type"]
    obj = best["obj"]

    print(f"[SEARCH] Best match: {obj_type} id={obj.id} score={best_score:.2f}")

    AUTO_SHOW_THRESHOLD = 0.90
    CONFIRM_THRESHOLD = 0.70
    UNIQUE_MIN_SCORE = 0.55  # chỉ cần đủ hợp lý là show thẳng nếu unique

    # ===== hỏi tồn kho / vị trí -> trả nhanh nếu đủ chắc =====
    norm_text = normalize(user_message)
    ask_qty = any(k in norm_text for k in ("so luong", "ton kho", "con bao nhieu", "trong kho"))
    ask_pos = any(k in norm_text for k in ("vi tri", "o dau", "nam o", "tu", "ngan"))

    if best_score >= 0.65:
        if ask_qty and obj_type == "tool":
            return f"Hiện tool **{obj.ma_tool} - {obj.ten_tool}** còn **{obj.ton_kho}** cái trong kho."
        if ask_pos:
            if obj_type == "tool":
                return f"Tool **{obj.ma_tool} - {obj.ten_tool}** đang ở **Tủ {obj.tu or '?'} / Ngăn {obj.ngan or '?'}**."
            if obj_type == "holder":
                return f"Holder **{obj.ma_noi_bo} - {obj.ten_thiet_bi}** đang ở **Tủ {obj.tu or '?'} / Ngăn {obj.ngan or '?'}**."

    # ===== FIX CHÍNH: unique result -> trả thẳng, khỏi hỏi đúng/không =====
    same_type = [c for c in candidates if c["type"] == obj_type]
    if (len(candidates) == 1 or len(same_type) == 1) and best_score >= UNIQUE_MIN_SCORE:
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

    # ===== rất chắc -> trả luôn =====
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

    # ===== score vừa -> hỏi confirm =====
    if best_score >= CONFIRM_THRESHOLD:
        if obj_type == "holder":
            code = obj.ma_noi_bo
            name = obj.ten_thiet_bi
            label = "holder"
        else:
            code = obj.ma_tool
            name = obj.ten_tool
            label = "tool"

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

    # ===== score thấp -> top 3 =====
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
        + "\n\nBạn thử gõ **mã** hoặc thêm **Φ/đường kính**, **BT/ER/SK**, vật liệu (HSS/carbide)… nhé."
    )


def handle_search_confirm(request, user_message: str, state: dict, intent: str):
    """
    Xử lý khi user trả lời 'đúng' / 'không' (intent = confirm_yes / confirm_no).
    Trả: (reply, done)
    """
    candidate_id = state.get("id")
    candidate_type = state.get("type")

    holder = None
    tool = None

    if candidate_type == "holder" and candidate_id:
        holder = Holder.objects.filter(pk=candidate_id).first()

    if candidate_type == "tool" and candidate_id:
        tool = Tool.objects.filter(pk=candidate_id).first()

    if intent == "confirm_yes":
        if holder:
            url = build_holder_url(holder)
            summary = _summarize_holder(holder)
            reply = (
                "✅ Đúng rồi, đây là holder bạn hỏi:\n\n"
                f"{summary}\n\n"
                f'🔗 <a href="{url}" target="_blank" class="chatbot-link">Xem chi tiết</a>'
            )
            return reply, True

        if tool:
            url = build_tool_url(tool)
            summary = _summarize_tool(tool)
            reply = (
                "✅ Đúng rồi, đây là công cụ bạn hỏi:\n\n"
                f"{summary}\n\n"
                f'🔗 <a href="{url}" target="_blank" class="chatbot-link">Xem chi tiết</a>'
            )
            return reply, True

        return "Mình bị mất thông tin thiết bị. Bạn gõ lại mã hoặc tên giúp mình nhé.", True

    # confirm_no
    return "Ok 👍 Bạn mô tả lại rõ hơn (mã, Φ/đường kính, hãng, nhóm tool/holder, BT/ER/SK...) nhé.", True
