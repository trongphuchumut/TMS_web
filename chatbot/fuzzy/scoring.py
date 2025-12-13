"""
FUZZY SCORING CORE (v2)

Mục tiêu:
- Chấm đủ tiêu chí cho TOOL (điểm mờ 1..5) như ảnh bạn đưa:
  gia, do_ben, do_on_dinh_qua_trinh, chat_luong_be_mat, do_san_co, uu_tien_dung_truoc
- Chấm đủ tiêu chí cho HOLDER (đo kỹ thuật) như ảnh:
  cv, dx, ld, mon(%), tan_suat_su_dung

- Vẫn giữ các tiêu chí chung:
  vat_lieu, loai_gia_cong, duong_kinh, chieu_dai_lam_viec

Output:
- score: 0..1
- breakdown: dict tiêu chí -> điểm membership (0..1) trước khi nhân trọng số

Ghi chú:
- Code dùng getattr an toàn + alias field để tương thích nhiều model.
- "uu_tien" trong criteria dùng để tăng trọng số (weight), KHÔNG bắt buộc.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import unicodedata
from difflib import SequenceMatcher


# ================== text helpers ==================

def normalize_vi(text: str) -> str:
    if not text:
        return ""
    text = str(text).lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def sim(a: str, b: str) -> float:
    a, b = normalize_vi(a), normalize_vi(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# ================== fuzzy helpers ==================

def tri(x: float, a: float, b: float, c: float) -> float:
    """Membership tam giác."""
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if (b - a) else 0.0
    return (c - x) / (c - b) if (c - b) else 0.0


def clamp01(v: float) -> float:
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def _prio_to_weight(prio: str | None) -> float:
    # cao -> weight lớn, thap -> nhỏ
    if not prio:
        return 1.0
    p = normalize_vi(prio)
    if p in ("cao", "high", "rat cao", "uu tien"):
        return 1.35
    if p in ("trung_binh", "trung binh", "medium", "vua"):
        return 1.0
    if p in ("thap", "low", "khong can", "it"):
        return 0.75
    return 1.0


def _get_first_float(obj: Any, attrs: List[str]) -> float | None:
    for a in attrs:
        v = getattr(obj, a, None)
        if v is None:
            continue
        try:
            return float(v)
        except Exception:
            continue
    return None


def _get_first_text(obj: Any, attrs: List[str]) -> str | None:
    for a in attrs:
        v = getattr(obj, a, None)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _score_1_5_to_01(v: float | None) -> float | None:
    """Map điểm 1..5 -> 0..1"""
    if v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return None
    return clamp01((v - 1.0) / 4.0)


def _norm_0_10(v: float | None) -> float | None:
    if v is None:
        return None
    try:
        return clamp01(float(v) / 10.0)
    except Exception:
        return None


def _norm_percent(v: float | None) -> float | None:
    if v is None:
        return None
    try:
        return clamp01(float(v) / 100.0)
    except Exception:
        return None


def _pref_to_direction(pref: str | None, default: str = "high") -> str:
    """
    Trả về "high" / "low" / "medium" theo câu ưu tiên
    default: nếu không có -> coi như neutral theo high (đối với tiêu chí "càng cao càng tốt")
    """
    if not pref:
        return default
    p = normalize_vi(pref)
    if p in ("cao", "high", "rat cao"):
        return "high"
    if p in ("thap", "low", "khong can", "it"):
        return "low"
    if p in ("trung_binh", "trung binh", "medium", "vua"):
        return "medium"
    return default


# ================== common criteria scores ==================

def _material_score(dev: Any, vat_lieu: str | None) -> float | None:
    if not vat_lieu:
        return None
    candidates = [
        _get_first_text(dev, ["vat_lieu_phu_hop"]),
        _get_first_text(dev, ["vat_lieu"]),
        _get_first_text(dev, ["nhom_vat_lieu"]),
        _get_first_text(dev, ["ghi_chu"]),
    ]
    candidates = [c for c in candidates if c]
    if not candidates:
        return None
    best = max(sim(vat_lieu, c) for c in candidates)
    return clamp01(best)


def _process_score(dev: Any, loai_gia_cong: str | None) -> float | None:
    if not loai_gia_cong:
        return None
    candidates = [
        _get_first_text(dev, ["loai_gia_cong"]),
        _get_first_text(dev, ["nhom_tool"]),
        _get_first_text(dev, ["dong_tool"]),
        _get_first_text(dev, ["nhom_thiet_bi"]),
        _get_first_text(dev, ["loai_holder"]),
        _get_first_text(dev, ["ten_tool"]),
        _get_first_text(dev, ["ten_thiet_bi"]),
    ]
    candidates = [c for c in candidates if c]
    if not candidates:
        return None
    best = max(sim(loai_gia_cong, c) for c in candidates)
    return clamp01(best)


def _diameter_score(dev: Any, req_d: float | None) -> float | None:
    """req_d là số; nếu bạn parse ra range [8,10] thì nên convert mid trước khi gọi scoring."""
    if req_d is None:
        return None
    d = _get_first_float(dev, ["duong_kinh", "diameter"])
    if d is None:
        return None
    a = req_d * 0.75
    b = req_d
    c = req_d * 1.10
    return clamp01(tri(d, a, b, c))


def _length_score(dev: Any, req_l: float | None) -> float | None:
    if req_l is None:
        return None
    l = _get_first_float(dev, ["chieu_dai_lam_viec", "chieu_dai", "length"])
    if l is None:
        return None
    a = req_l * 0.70
    b = req_l
    c = req_l * 1.20
    return clamp01(tri(l, a, b, c))


# ================== TOOL criteria scores (1..5) ==================
# Tool fields alias: thêm vào đây nếu model bạn đặt khác

TOOL_FIELD_ALIASES: Dict[str, List[str]] = {
    "gia": ["gia", "diem_gia", "gia_diem", "gia_1_5"],
    "do_ben": ["do_ben", "diem_do_ben", "do_ben_1_5"],
    "do_on_dinh_qua_trinh": ["do_on_dinh_qua_trinh", "do_on_dinh", "diem_do_on_dinh"],
    "chat_luong_be_mat": ["chat_luong_be_mat", "be_mat", "diem_be_mat"],
    "do_san_co": ["do_san_co", "san_co", "diem_san_co", "ton_diem"],
    "uu_tien_dung_truoc": ["uu_tien_dung_truoc", "uu_tien", "diem_uu_tien"],
}

def _tool_rating_score(dev: Any, key: str, prefer: str | None) -> float | None:
    """
    key: một trong TOOL_FIELD_ALIASES
    prefer: ưu tiên người dùng (cao/thap/...)
    """
    raw = _get_first_float(dev, TOOL_FIELD_ALIASES.get(key, []))
    v01 = _score_1_5_to_01(raw)
    if v01 is None:
        return None

    # "gia": 1=rẻ,5=đắt -> nếu user muốn rẻ => prefer low => score cao khi v01 thấp
    if key == "gia":
        direction = _pref_to_direction(prefer, default="low")  # mặc định prefer rẻ
        if direction == "low":
            return clamp01(1.0 - v01)
        if direction == "high":
            return v01
        # medium
        return clamp01(1.0 - abs(v01 - 0.5) * 2.0)

    # các key còn lại: càng cao càng tốt
    direction = _pref_to_direction(prefer, default="high")
    if direction == "high":
        return v01
    if direction == "low":
        return clamp01(1.0 - v01)
    # medium
    return clamp01(1.0 - abs(v01 - 0.5) * 2.0)


# ================== HOLDER criteria scores (0..10, %, usage) ==================
# Holder fields alias: thêm vào đây nếu model bạn đặt khác

HOLDER_FIELD_ALIASES: Dict[str, List[str]] = {
    "cv": ["cv", "do_cung_vung", "do_cung_vung_cv"],
    "dx": ["dx", "do_chinh_xac", "do_chinh_xac_ga_kep"],
    "ld": ["ld", "chieu_dai_nho_dao", "do_nho", "nhodao"],
    "mon": ["mon", "tinh_trang_mon", "mon_phan_tram", "wear_percent"],
    "tan_suat": ["tan_suat", "tan_suat_su_dung", "so_lan_thang", "usage_per_month"],
}

def _holder_metric_score(dev: Any, key: str, prefer: str | None) -> float | None:
    if key == "cv":
        v = _get_first_float(dev, HOLDER_FIELD_ALIASES["cv"])
        v01 = _norm_0_10(v)
        if v01 is None:
            return None
        return v01  # càng cao càng tốt

    if key == "dx":
        v = _get_first_float(dev, HOLDER_FIELD_ALIASES["dx"])
        v01 = _norm_0_10(v)
        if v01 is None:
            return None
        return v01  # càng cao càng tốt

    if key == "ld":
        # LD: càng nhỏ càng tốt (nhô dao ít -> cứng vững)
        v = _get_first_float(dev, HOLDER_FIELD_ALIASES["ld"])
        v01 = _norm_0_10(v)  # nếu LD của bạn không 0..10, bạn đổi norm theo thực tế
        if v01 is None:
            return None
        direction = _pref_to_direction(prefer, default="low")  # mặc định prefer nhỏ
        if direction == "low":
            return clamp01(1.0 - v01)
        if direction == "high":
            return v01
        return clamp01(1.0 - abs(v01 - 0.5) * 2.0)

    if key == "mon":
        # mòn %: càng thấp càng tốt
        v = _get_first_float(dev, HOLDER_FIELD_ALIASES["mon"])
        v01 = _norm_percent(v)
        if v01 is None:
            return None
        direction = _pref_to_direction(prefer, default="low")
        if direction == "low":
            return clamp01(1.0 - v01)  # ít mòn -> tốt
        if direction == "high":
            return v01
        return clamp01(1.0 - abs(v01 - 0.5) * 2.0)

    if key == "tan_suat":
        # tần suất dùng: tuỳ chính sách, mặc định càng cao càng "được dùng nhiều" -> không chắc tốt/xấu
        # để an toàn: dùng dạng medium (tránh thiên vị)
        v = _get_first_float(dev, HOLDER_FIELD_ALIASES["tan_suat"])
        v01 = _norm_0_10(v)  # nếu là lần/tháng >10, bạn đổi norm theo thực tế
        if v01 is None:
            return None
        direction = _pref_to_direction(prefer, default="medium")
        if direction == "high":
            return v01
        if direction == "low":
            return clamp01(1.0 - v01)
        return clamp01(1.0 - abs(v01 - 0.5) * 2.0)

    return None


# ================== detect type ==================

def _is_tool(dev: Any) -> bool:
    return getattr(dev, "ma_tool", None) is not None or getattr(dev, "ten_tool", None) is not None

def _is_holder(dev: Any) -> bool:
    return getattr(dev, "ma_noi_bo", None) is not None or getattr(dev, "ten_thiet_bi", None) is not None


# ================== main scoring ==================

def score_device(dev: Any, criteria: dict) -> Tuple[float, Dict[str, float]]:
    """
    Trả về (score 0..1, breakdown)
    breakdown: điểm từng tiêu chí trước khi nhân trọng số.
    """
    if not isinstance(criteria, dict):
        return 0.0, {}

    uu = criteria.get("uu_tien") or {}
    if not isinstance(uu, dict):
        uu = {}

    parts: Dict[str, float] = {}
    weights: Dict[str, float] = {}

    # ====== (A) tiêu chí chung ======
    m = _material_score(dev, criteria.get("vat_lieu"))
    if m is not None:
        parts["vat_lieu"] = m
        weights["vat_lieu"] = 1.20

    p = _process_score(dev, criteria.get("loai_gia_cong"))
    if p is not None:
        parts["loai_gia_cong"] = p
        weights["loai_gia_cong"] = 1.10 * _prio_to_weight(uu.get("toc_do"))

    d = _diameter_score(dev, criteria.get("duong_kinh"))
    if d is not None:
        parts["duong_kinh"] = d
        weights["duong_kinh"] = 1.00 * _prio_to_weight(uu.get("do_chinh_xac"))

    l = _length_score(dev, criteria.get("chieu_dai_lam_viec"))
    if l is not None:
        parts["chieu_dai_lam_viec"] = l
        weights["chieu_dai_lam_viec"] = 0.85 * _prio_to_weight(uu.get("chat_luong_be_mat"))

    # ====== (B) TOOL criteria (1..5) ======
    if _is_tool(dev):
        tool_keys = [
            "gia",
            "do_ben",
            "do_on_dinh_qua_trinh",
            "chat_luong_be_mat",
            "do_san_co",
            "uu_tien_dung_truoc",
        ]

        # map ưu tiên từ uu_tien nếu có
        # bạn có thể cho user nói: "ưu tiên độ bền", "ưu tiên giá rẻ", ...
        pref_map = {
            "gia": uu.get("gia"),
            "do_ben": uu.get("do_ben"),
            "chat_luong_be_mat": uu.get("chat_luong_be_mat"),
            "do_on_dinh_qua_trinh": uu.get("do_on_dinh") or uu.get("do_on_dinh_qua_trinh"),
            "do_san_co": uu.get("do_san_co"),
            "uu_tien_dung_truoc": uu.get("uu_tien_dung_truoc"),
        }

        # weights base (bạn có thể chỉnh theo báo cáo)
        base_w = {
            "gia": 0.75,
            "do_ben": 1.15,
            "do_on_dinh_qua_trinh": 1.00,
            "chat_luong_be_mat": 1.05,
            "do_san_co": 0.80,
            "uu_tien_dung_truoc": 0.70,
        }

        for k in tool_keys:
            s = _tool_rating_score(dev, k, pref_map.get(k))
            if s is None:
                continue
            parts[k] = s
            weights[k] = base_w.get(k, 0.8) * _prio_to_weight(pref_map.get(k))

    # ====== (C) HOLDER criteria (CV/DX/LD/mon/tan_suat) ======
    if _is_holder(dev):
        holder_keys = ["cv", "dx", "ld", "mon", "tan_suat"]

        pref_map = {
            "cv": uu.get("do_cung_vung") or uu.get("cv"),
            "dx": uu.get("do_chinh_xac") or uu.get("dx"),
            "ld": uu.get("chieu_dai_nho_dao") or uu.get("ld"),
            "mon": uu.get("tinh_trang_mon") or uu.get("mon"),
            "tan_suat": uu.get("tan_suat_su_dung") or uu.get("tan_suat"),
        }

        base_w = {
            "cv": 1.10,
            "dx": 1.10,
            "ld": 0.85,
            "mon": 1.25,
            "tan_suat": 0.60,
        }

        for k in holder_keys:
            s = _holder_metric_score(dev, k, pref_map.get(k))
            if s is None:
                continue
            parts[k] = s
            weights[k] = base_w.get(k, 0.8) * _prio_to_weight(pref_map.get(k))

    # ====== finalize ======
    if not parts:
        return 0.0, {}

    num = sum(parts[k] * weights.get(k, 1.0) for k in parts)
    den = sum(weights.get(k, 1.0) for k in parts)
    score = (num / den) if den else 0.0
    return clamp01(score), parts


def score_all_candidates(candidates: List[Any], criteria: dict) -> List[Tuple[float, Any, Dict[str, float]]]:
    scored: List[Tuple[float, Any, Dict[str, float]]] = []
    for dev in candidates:
        s, br = score_device(dev, criteria)
        scored.append((s, dev, br))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored
