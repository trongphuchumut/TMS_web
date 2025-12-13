import re
from typing import Any, List, Tuple

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def _norm(v: float | None, vmin: float, vmax: float) -> float:
    if v is None: return 0.0
    if vmax == vmin: return 0.0
    return _clamp01((float(v) - vmin) / (vmax - vmin))

def _to_float_range(v: Any) -> tuple[float | None, float | None]:
    if v is None:
        return (None, None)
    if isinstance(v, (int, float)):
        x = float(v)
        return (x, x)
    if isinstance(v, (list, tuple)):
        nums = []
        for x in v:
            try: nums.append(float(x))
            except Exception: pass
        if not nums: return (None, None)
        return (min(nums), max(nums))
    if isinstance(v, str):
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", v)]
        if not nums: return (None, None)
        if len(nums) == 1: return (nums[0], nums[0])
        return (min(nums), max(nums))
    return (None, None)

def _pref_to_01(v: Any) -> float | None:
    """
    Map chữ -> 0..1 (để đặt "query" cho các tiêu chí dạng ưu tiên)
    cao/high: 0.85
    vừa/medium: 0.55
    thấp/low/không cần: 0.25
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return _clamp01(float(v))
    s = str(v).strip().lower()
    if s in ("cao", "high", "tot", "cao_cap", "rat cao"): return 0.85
    if s in ("vua", "trung_binh", "trung binh", "medium", "tb"): return 0.55
    if s in ("thap", "low", "khong_can", "khong", "it"): return 0.25
    return None

def _score_1_5_to_01(v: Any) -> float | None:
    """1..5 -> 0..1"""
    try:
        if v is None:
            return None
        return _clamp01((float(v) - 1.0) / 4.0)
    except Exception:
        return None

def _norm_0_10(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return _clamp01(float(v) / 10.0)
    except Exception:
        return None

def _norm_percent(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return _clamp01(float(v) / 100.0)
    except Exception:
        return None

# Sets theo trục X = 0..100 (JS của bạn đang triMu(x01*100, a,b,c))
SETS_3 = {
    "low":    {"a": 0,  "b": 20, "c": 40},
    "medium": {"a": 30, "b": 50, "c": 70},
    "high":   {"a": 60, "b": 80, "c": 100},
}

# Alias field để lấy data thật từ model (nếu có)
TOOL_FIELD_ALIASES = {
    "gia": ["gia", "diem_gia", "gia_diem"],
    "do_ben": ["do_ben", "diem_do_ben"],
    "do_on_dinh_qua_trinh": ["do_on_dinh_qua_trinh", "do_on_dinh", "diem_do_on_dinh"],
    "chat_luong_be_mat": ["chat_luong_be_mat", "be_mat", "diem_be_mat"],
    "do_san_co": ["do_san_co", "san_co", "diem_san_co"],
    "uu_tien_dung_truoc": ["uu_tien_dung_truoc", "uu_tien", "diem_uu_tien"],
}

HOLDER_FIELD_ALIASES = {
    "cv": ["cv", "do_cung_vung"],
    "dx": ["dx", "do_chinh_xac", "do_chinh_xac_ga_kep"],
    "ld": ["ld", "chieu_dai_nho_dao", "do_nho"],
    "mon": ["mon", "tinh_trang_mon", "mon_phan_tram"],
    "tan_suat": ["tan_suat", "tan_suat_su_dung", "so_lan_thang"],
}

def _get_first_attr(dev: Any, names: List[str]) -> Any:
    for n in names:
        if hasattr(dev, n):
            v = getattr(dev, n, None)
            if v is not None:
                return v
    return None

def build_plot(criteria: dict, scored: List[Tuple[float, Any, dict]]) -> dict:
    plot = {"criteria": {}}
    uu = (criteria.get("uu_tien") or {}) if isinstance(criteria, dict) else {}

    # ====== 1) duong_kinh (numeric) ======
    dmin, dmax = _to_float_range(criteria.get("duong_kinh"))
    if dmin is not None:
        q_mid = (dmin + (dmax if dmax is not None else dmin)) / 2.0
        item = {"sets": SETS_3, "query": _norm(q_mid, 0, 20), "tops": []}
        for s, dev, br in scored[:5]:
            val = getattr(dev, "duong_kinh", None) or getattr(dev, "diameter", None)
            tmin, tmax = _to_float_range(val)
            if tmin is None:
                item["tops"].append({"value": item["query"]})
            else:
                item["tops"].append({"value": _norm((tmin + (tmax or tmin)) / 2.0, 0, 20)})
        plot["criteria"]["duong_kinh"] = item

    # ====== 2) ƯU TIÊN CHUNG (từ uu_tien) ======
    # mấy cái này bạn đang dùng rồi, giữ lại
    for key in ("do_ben", "do_chinh_xac", "toc_do", "chat_luong_be_mat"):
        q = _pref_to_01(uu.get(key))
        if q is None:
            continue
        item = {"sets": SETS_3, "query": q, "tops": []}
        for s, dev, br in scored[:5]:
            # nếu breakdown có key -> lấy theo breakdown (0..1)
            if isinstance(br, dict) and br.get(key) is not None:
                item["tops"].append({"value": _clamp01(float(br[key]))})
            else:
                item["tops"].append({"value": q})
        plot["criteria"][key] = item

    # ====== 3) TOOL CRITERIA (1..5) ======
    # Vẽ đúng 6 tiêu chí tool theo ảnh 1
    TOOL_KEYS = ("gia", "do_ben", "do_on_dinh_qua_trinh", "chat_luong_be_mat", "do_san_co", "uu_tien_dung_truoc")
    for key in TOOL_KEYS:
        # query: ưu tiên (cao/thấp) hoặc nếu criteria có trực tiếp 1..5 thì dùng luôn
        q = None
        if criteria.get(key) is not None:
            q = _score_1_5_to_01(criteria.get(key))
        if q is None:
            q = _pref_to_01(uu.get(key))  # nếu user nói “ưu tiên ... cao”
        if q is None:
            # không có query -> skip (đỡ rác)
            continue

        item = {"sets": SETS_3, "query": q, "tops": []}

        for s, dev, br in scored[:5]:
            # Ưu tiên lấy breakdown (vì scoring v2 đã trả đúng 0..1)
            if isinstance(br, dict) and br.get(key) is not None:
                item["tops"].append({"value": _clamp01(float(br[key]))})
                continue

            # fallback: lấy field thật 1..5 trong model
            raw = _get_first_attr(dev, TOOL_FIELD_ALIASES.get(key, []))
            v01 = _score_1_5_to_01(raw)
            item["tops"].append({"value": v01 if v01 is not None else q})

        plot["criteria"][key] = item

    # ====== 4) HOLDER CRITERIA (CV/DX/LD/MÒN/TẦN SUẤT) ======
    # Vẽ đúng 5 tiêu chí holder theo ảnh 2
    # Query: nếu criteria có numeric thì dùng; nếu không thì fallback theo ưu tiên (cao/thấp)
    HOLDER_KEYS = ("cv", "dx", "ld", "mon", "tan_suat")
    for key in HOLDER_KEYS:
        q = None
        if criteria.get(key) is not None:
            if key in ("cv", "dx", "ld", "tan_suat"):
                q = _norm_0_10(criteria.get(key))
            elif key == "mon":
                # mòn %: để đồng nhất với scoring v2 (mòn thấp tốt), bạn có thể để query là 1 - mon%
                q0 = _norm_percent(criteria.get(key))
                q = (1.0 - q0) if q0 is not None else None

        if q is None:
            q = _pref_to_01(uu.get(key))  # nếu user nói “ưu tiên cv cao...”
        if q is None:
            continue

        item = {"sets": SETS_3, "query": q, "tops": []}

        for s, dev, br in scored[:5]:
            # ưu tiên lấy breakdown (đã là 0..1)
            if isinstance(br, dict) and br.get(key) is not None:
                item["tops"].append({"value": _clamp01(float(br[key]))})
                continue

            raw = _get_first_attr(dev, HOLDER_FIELD_ALIASES.get(key, []))
            if key in ("cv", "dx", "ld", "tan_suat"):
                v01 = _norm_0_10(raw)
            else:  # mon
                p01 = _norm_percent(raw)
                v01 = (1.0 - p01) if p01 is not None else None

            item["tops"].append({"value": v01 if v01 is not None else q})

        plot["criteria"][key] = item

    return plot
