from typing import Dict, Any, List, Tuple
from tool.models import Tool

from ..shared.utils import (
    clamp, safe_float,
    norm_1to5_to_0to10, inv_norm_1to5_to_0to10
)
from ..shared.contracts import engine_result
from .selector import select_tool_candidates

ENGINE_VERSION = "tool_fuzzy_v1"


# =========================
# Membership helpers (triangular)
# =========================

def tri_mu(x: float, a: float, b: float, c: float) -> float:
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
    # Inputs in this engine are clamped to 0..10
    low = (0.0, 0.0, 5.0)
    med = (2.5, 5.0, 7.5)
    high = (5.0, 10.0, 10.0)

    return {
        "cost_level": {
            "universe": [0.0, 10.0],
            "sets": {"low_cost": low, "mid": med, "high_cost": high},
            "used_in_scoring": True,  # via prefer_cheap = 10 - cost_level
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

def _feature_scores(t: Tool) -> Dict[str, Any]:
    """
    Convert DB fields -> 0..10 features
    """
    cheapness = inv_norm_1to5_to_0to10(t.diem_gia)           # rẻ -> điểm cao
    durability = norm_1to5_to_0to10(t.diem_do_ben)
    stability = norm_1to5_to_0to10(t.diem_on_dinh)
    surface = norm_1to5_to_0to10(t.diem_chat_luong_be_mat)
    availability = norm_1to5_to_0to10(t.diem_san_co)

    def fb(x):  # fallback nếu thiếu điểm -> set 5 để trung tính
        return 5.0 if x is None else float(x)

    return {
        "cheapness": fb(cheapness),
        "durability": fb(durability),
        "stability": fb(stability),
        "surface": fb(surface),
        "availability": fb(availability),
        "stock": float(t.ton_kho or 0),
    }


# =========================
# Main scoring
# =========================

def score_tool_candidates(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    inputs: dict 0..10 (từ chatbot/AI parse)
    """
    cost_level = clamp(safe_float(inputs.get("cost_level"), 5.0), 0.0, 10.0)
    precision = clamp(safe_float(inputs.get("precision_importance"), 5.0), 0.0, 10.0)
    durability = clamp(safe_float(inputs.get("durability_importance"), 5.0), 0.0, 10.0)
    speed = clamp(safe_float(inputs.get("speed_importance"), 5.0), 0.0, 10.0)

    # user muốn rẻ => cost_level thấp -> prefer_cheap cao
    prefer_cheap = 10.0 - cost_level

    # weights v1
    w_cheap = 0.30
    w_dura  = 0.28
    w_prec  = 0.22
    w_speed = 0.12
    w_avail = 0.08

    rules_fired: List[str] = []
    if prefer_cheap >= 7:
        rules_fired.append("Prefer cheap: prioritize cheapness (low price)")
    if durability >= 7:
        rules_fired.append("Prefer durability: prioritize diem_do_ben")
    if precision >= 7:
        rules_fired.append("Prefer precision: prioritize surface quality")
    if speed >= 7:
        rules_fired.append("Prefer speed: prioritize stability & availability")

    ranked: List[Dict[str, Any]] = []
    qs = select_tool_candidates(limit=80)

    for t in qs:
        fs = _feature_scores(t)

        # Weighted matches (0..10 each)
        score_cheap = fs["cheapness"] * (prefer_cheap / 10.0)
        score_dura  = fs["durability"] * (durability / 10.0)
        score_prec  = fs["surface"] * (precision / 10.0)
        score_speed = fs["stability"] * (speed / 10.0)

        # availability nên phản ánh "tốc độ/leadtime" -> nhân theo speed_importance
        score_avail = fs["availability"] * (speed / 10.0)

        # Stock bonus
        stock_bonus = 1.0 if fs["stock"] > 0 else -3.0

        raw10 = (
            w_cheap * score_cheap +
            w_dura  * score_dura  +
            w_prec  * score_prec  +
            w_speed * score_speed +
            w_avail * score_avail
        )
        raw10 = raw10 + stock_bonus
        raw10 = clamp(raw10, 0.0, 10.0)
        final = raw10 * 10.0

        ranked.append({
            "id": t.id,
            "code": t.ma_tool,
            "name": t.ten_tool,
            "score": round(final, 2),
            "meta": {
                "ton_kho": t.ton_kho,
                "nhom_tool": t.nhom_tool,
                "dong_tool": t.dong_tool,
            }
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    ranked = ranked[:10]

    breakdown = {
        "weights": {
            "cheap": w_cheap,
            "durability": w_dura,
            "precision": w_prec,
            "speed": w_speed,
            "availability": w_avail
        },
        "user_preference": {
            "prefer_cheap": prefer_cheap,
            "durability": durability,
            "precision": precision,
            "speed": speed
        },
        "notes": [
            "v1 uses Tool.diem_* (1..5) mapped to 0..10 features.",
            "precision is mapped to surface_quality for now; can be extended later.",
            "membership_defs/fuzzified added for UI visualization (triangular sets on 0..10).",
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

    result = engine_result("tool", ENGINE_VERSION, inputs, ranked, rules_fired, breakdown)
    result["membership_defs"] = membership_defs
    result["fuzzified"] = fuzzified
    result["inputs_used_in_scoring"] = used_inputs

    return result
