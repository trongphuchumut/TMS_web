from typing import Dict, Any, List, Tuple
from holder.models import Holder

from ..shared.utils import clamp, safe_float, norm_percent_good
from ..shared.contracts import engine_result
from .selector import select_holder_candidates

ENGINE_VERSION = "holder_fuzzy_v1"


# =========================
# Membership helpers (triangular)
# =========================

def tri_mu(x: float, a: float, b: float, c: float) -> float:
    """
    Triangular membership µ(x) for triangle (a, b, c).
    Handles shoulder triangles where a==b or b==c.
    """
    if x <= a:
        return 1.0 if a == b else 0.0
    if x >= c:
        return 1.0 if b == c else 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


def fuzzify_triangles(x: float, sets: Dict[str, Tuple[float, float, float]]) -> Dict[str, float]:
    return {name: round(tri_mu(x, *abc), 4) for name, abc in sets.items()}


def build_input_membership_defs() -> Dict[str, Any]:
    """
    Inputs in this engine are clamped to 0..10.
    So we define membership on universe 0..10.
    """
    # 3-set triangles on 0..10 (simple, stable for UI)
    low = (0.0, 0.0, 5.0)
    med = (2.5, 5.0, 7.5)
    high = (5.0, 10.0, 10.0)

    # cost_level currently unused in scoring, but we still provide membership for visualization
    return {
        "cost_level": {
            "universe": [0.0, 10.0],
            "sets": {
                "cheap": low,
                "mid": med,
                "premium": high,
            },
            "used_in_scoring": False,
        },
        "precision_importance": {
            "universe": [0.0, 10.0],
            "sets": {"low": low, "med": med, "high": high},
            "used_in_scoring": True,
        },
        "durability_importance": {
            "universe": [0.0, 10.0],
            "sets": {"low": low, "med": med, "high": high},
            "used_in_scoring": True,
        },
        "speed_importance": {
            "universe": [0.0, 10.0],
            "sets": {"low": low, "med": med, "high": high},
            "used_in_scoring": True,
        },
    }


# =========================
# Feature extraction
# =========================

def _dx_to_score(dx_value: float) -> float:
    """
    IMPORTANT:
    - If your DB field h.dx is ALREADY a "goodness score" 0..10: return clamp(dx_value, 0..10)
    - If your DB field h.dx is runout/độ đảo in mm (smaller is better): convert to 0..10 score.

    Choose ONE behavior by editing the return line below.
    """

    # Option A: dx is already a score 0..10 (bigger is better)
    return clamp(dx_value, 0.0, 10.0)

    # Option B: dx is runout in mm (smaller is better) -> score
    # Example mapping: 0.002mm -> ~10, 0.03mm -> ~0
    # dx_mm = max(dx_value, 0.0)
    # score = 10.0 - (dx_mm / 0.003)  # tune divisor to your real range
    # return clamp(score, 0.0, 10.0)


def _feature_scores(h: Holder) -> Dict[str, Any]:
    # cv: assume higher is better (rigidity/stability)
    cv = clamp(safe_float(h.cv, 5.0), 0.0, 10.0)

    # dx: see _dx_to_score() note above
    dx_raw = safe_float(h.dx, 5.0)
    dx = _dx_to_score(dx_raw)

    # mon: % mòn. want "remaining good" = 100 - mon
    wear = None if h.mon is None else clamp(float(h.mon), 0.0, 100.0)
    remaining = None if wear is None else (100.0 - wear)
    remaining10 = norm_percent_good(remaining)  # 0..10

    # tan_suat: uses/month; lower is better
    ts = safe_float(h.tan_suat, 0.0)
    # 0 -> 10; >=30 -> 0
    ts_score = clamp(10.0 - (ts / 3.0), 0.0, 10.0)

    # ld: length/overhang mm; lower is better
    ld = safe_float(h.ld, 0.0)
    # 0 -> 10; 200 -> 0
    ld_score = clamp(10.0 - (ld / 20.0), 0.0, 10.0)

    def fb(x):  # fallback
        return 5.0 if x is None else float(x)

    return {
        "cv": fb(cv),
        "dx": fb(dx),
        "remaining": fb(remaining10),
        "tan_suat": fb(ts_score),
        "ld": fb(ld_score),
        "status": h.trang_thai_tai_san,
    }


# =========================
# Main scoring
# =========================

def score_holder_candidates(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Clamp inputs to 0..10
    cost_level = clamp(safe_float(inputs.get("cost_level"), 5.0), 0.0, 10.0)
    precision = clamp(safe_float(inputs.get("precision_importance"), 5.0), 0.0, 10.0)
    durability = clamp(safe_float(inputs.get("durability_importance"), 5.0), 0.0, 10.0)
    speed = clamp(safe_float(inputs.get("speed_importance"), 5.0), 0.0, 10.0)

    # Holder: cost not used for scoring in v1
    prefer_quality = (precision + durability) / 2.0

    # weights v1
    w_cv = 0.30
    w_dx = 0.30
    w_remain = 0.22
    w_ld = 0.10
    w_ts = 0.08

    rules_fired: List[str] = []
    if precision >= 7:
        rules_fired.append("Prefer accuracy: prioritize dx (runout/accuracy)")
    if durability >= 7:
        rules_fired.append("Prefer low wear: prioritize remaining (100-mon)")
    if speed >= 7:
        rules_fired.append("Prefer stability: prioritize cv and short ld")

    ranked: List[Dict[str, Any]] = []
    qs = select_holder_candidates(limit=80)

    for h in qs:
        fs = _feature_scores(h)

        # status bonus
        status_bonus = 0.0
        if fs["status"] == "san_sang":
            status_bonus = 1.0
        elif fs["status"] in ("dang_bao_tri", "ngung_su_dung"):
            status_bonus = -4.0

        # scores (each 0..10 scaled by user importance 0..10)
        score_cv = fs["cv"] * (speed / 10.0)
        score_dx = fs["dx"] * (precision / 10.0)
        score_rem = fs["remaining"] * (durability / 10.0)
        score_ld = fs["ld"] * (speed / 10.0)
        score_ts = fs["tan_suat"] * (prefer_quality / 10.0)

        raw10 = (
            w_cv * score_cv +
            w_dx * score_dx +
            w_remain * score_rem +
            w_ld * score_ld +
            w_ts * score_ts
        )

        raw10 = raw10 + status_bonus
        raw10 = clamp(raw10, 0.0, 10.0)
        final = raw10 * 10.0  # 0..100

        ranked.append({
            "id": h.id,
            "code": h.ma_noi_bo,
            "name": h.ten_thiet_bi,
            "score": round(final, 2),
            "meta": {
                "chuan_ga": h.chuan_ga,
                "loai_kep": h.loai_kep,
                "duong_kinh_kep_max": str(h.duong_kinh_kep_max) if h.duong_kinh_kep_max is not None else None,
                "status": h.trang_thai_tai_san,
            }
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    ranked = ranked[:10]

    breakdown = {
        "weights": {"cv": w_cv, "dx": w_dx, "remaining": w_remain, "ld": w_ld, "tan_suat": w_ts},
        "notes": [
            "v1 maps Holder.cv/dx/mon/tan_suat/ld into 0..10 features.",
            "cost_level is currently not used for Holder scoring (no price fuzzy field). Add later if needed.",
            "membership_defs/fuzzified are added for UI visualization (triangular sets on 0..10).",
        ]
    }

    # ===== Add membership info for drawing =====
    membership_defs = build_input_membership_defs()
    fuzzified = {
        "cost_level": fuzzify_triangles(cost_level, membership_defs["cost_level"]["sets"]),
        "precision_importance": fuzzify_triangles(precision, membership_defs["precision_importance"]["sets"]),
        "durability_importance": fuzzify_triangles(durability, membership_defs["durability_importance"]["sets"]),
        "speed_importance": fuzzify_triangles(speed, membership_defs["speed_importance"]["sets"]),
    }
    used_inputs = [k for k, v in membership_defs.items() if v.get("used_in_scoring")]

    # Build base result from contract
    result = engine_result("holder", ENGINE_VERSION, inputs, ranked, rules_fired, breakdown)

    # Attach extra fields (non-breaking for old UI)
    result["membership_defs"] = membership_defs
    result["fuzzified"] = fuzzified
    result["inputs_used_in_scoring"] = used_inputs

    return result
