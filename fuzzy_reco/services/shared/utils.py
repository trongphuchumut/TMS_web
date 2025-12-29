from typing import Optional

def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo: return lo
    if x > hi: return hi
    return x

def safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

def norm_1to5_to_0to10(v) -> Optional[float]:
    """
    Convert điểm 1..5 (Tool) -> 0..10
    1 -> 0, 3 -> 5, 5 -> 10
    """
    if v is None:
        return None
    x = safe_float(v, default=0.0)
    x = clamp(x, 1.0, 5.0)
    return (x - 1.0) * 2.5

def inv_norm_1to5_to_0to10(v) -> Optional[float]:
    """
    Inverse: 1 (rẻ) nên thành score cao theo 'prefer cheap'
    1 -> 10, 5 -> 0
    """
    nv = norm_1to5_to_0to10(v)
    if nv is None:
        return None
    return 10.0 - nv

def norm_percent_good(remaining_percent: Optional[float]) -> Optional[float]:
    """
    0..100% -> 0..10
    """
    if remaining_percent is None:
        return None
    x = clamp(safe_float(remaining_percent, 0.0), 0.0, 100.0)
    return x / 10.0
