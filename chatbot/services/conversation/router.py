from __future__ import annotations

from typing import Dict, Optional, Tuple
import re

# ----------------------------
# HINTS / KEYWORDS
# ----------------------------

TOOL_HINTS = [
    "endmill", "end mill", "dao", "mũi", "cutter", "mill", "phay",
    "drill", "khoan", "ream", "tarô", "tap", "carbide", "hss",
    "flute", "coating", "altn", "tin", "ticn",
    "đường kính", "phi", "ø", "d", "mm", "r", "corner", "radius",
]
HOLDER_HINTS = [
    "holder", "collet", "taper", "hsk", "bt", "cat", "sk",
    "pull stud", "pullstud", "stud", "gauge", "runout",
    "độ đảo", "chuôi", "bầu kẹp", "arbor", "shank",
]

LOOKUP_HINTS = [
    "là gì", "mô tả", "catalog", "link", "datasheet", "thông số",
    "tương tự", "similar", "mã", "model", "part number", "p/n", "pn",
    "spec", "specs", "thông tin", "hình", "ảnh", "manual",
]
FUZZY_HINTS = [
    "đề xuất", "gợi ý", "phù hợp", "nên chọn", "ưu tiên",
    "khá rẻ", "giá rẻ", "tầm trung", "đắt", "bền", "chính xác",
    "tốc độ", "fuzzy", "tư vấn", "recommend", "suggest", "best",
]

# Những từ hay xuất hiện khi user muốn "đề xuất tool để gia công vật liệu"
MACHINING_HINTS = [
    "gia công", "phay", "khoan", "tiện", "cắt", "c45", "skd", "inox", "sus",
    "nhôm", "al", "gang", "thép", "hardened", "heat treat", "p20", "s45c"
]

# ----------------------------
# REGEX HELPERS
# ----------------------------

PREFIX_RE = re.compile(r"^\s*(tool|holder)\s*:\s*(.+)\s*$", re.IGNORECASE)

# “mã” phổ biến: chữ/số/_/-, không có khoảng trắng, dài vừa phải
CODE_TOKEN_RE = re.compile(r"^[A-Z0-9][A-Z0-9_\-\.]{2,40}$", re.IGNORECASE)

# Nếu tail là 1 token và "trông như mã" -> khả năng lookup cao
def _looks_like_code_only(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if len(s.split()) != 1:
        return False
    return bool(CODE_TOKEN_RE.match(s))


# ----------------------------
# SCORING / GUESSING
# ----------------------------

def _count_hits(t: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if k in t)

def guess_domain(text: str, default: Optional[str] = None) -> Optional[str]:
    t = (text or "").lower()

    tool_score = _count_hits(t, TOOL_HINTS)
    holder_score = _count_hits(t, HOLDER_HINTS)

    if tool_score == 0 and holder_score == 0:
        return default

    return "tool" if tool_score >= holder_score else "holder"

def guess_intent(text: str) -> str:
    """
    Priority:
    1) Explicit lookup signals
    2) Explicit fuzzy/recommendation signals
    3) If it smells like machining request -> FUZZY (because often user asks "tool nào gia công X")
    4) else CHAT
    """
    t = (text or "").lower()

    if any(k in t for k in LOOKUP_HINTS):
        return "LOOKUP"

    if any(k in t for k in FUZZY_HINTS):
        return "FUZZY"

    # If the user is clearly asking about machining/material but didn't say "đề xuất"
    if any(k in t for k in MACHINING_HINTS) and any(k in t for k in ["tool", "dao", "mũi", "endmill", "drill", "khoan", "phay"]):
        return "FUZZY"

    return "CHAT"


# ----------------------------
# ROUTE
# ----------------------------

def route(text: str, state_domain: Optional[str] = None) -> Dict[str, str]:
    """
    Returns dict:
      - intent: LOOKUP | FUZZY | CHAT
      - domain: tool | holder | "" (unknown)
      - (optional) norm_text: text cleaned from prefix (handy for orchestrator)
    """

    raw = text or ""
    t = raw.strip()
    low = t.lower()

    # 0) Prefix handling: "tool: ..." or "holder: ..."
    # Rule:
    # - If prefix present:
    #   - if tail looks like code-only -> LOOKUP
    #   - else -> FUZZY by default (user intentionally tells domain)
    m = PREFIX_RE.match(t)
    if m:
        prefix = m.group(1).lower().strip()       # tool|holder
        tail = m.group(2).strip()

        # Domain is explicit by prefix
        domain = prefix

        # Intent by tail
        if _looks_like_code_only(tail):
            intent = "LOOKUP"
        else:
            # If the tail contains lookup hints (catalog, datasheet...) keep LOOKUP
            # else default to FUZZY because prefix indicates "work context"
            intent = "LOOKUP" if any(k in tail.lower() for k in LOOKUP_HINTS) else "FUZZY"

        return {"domain": domain, "intent": intent, "norm_text": tail}

    # 1) No prefix: normal guessing
    domain = guess_domain(t, default=state_domain)
    intent = guess_intent(t)

    # 2) Safety refinement: if intent is LOOKUP but domain unknown -> keep domain from state if any
    #    (you said orchestrator can ask back if still empty)
    if intent in ("LOOKUP", "FUZZY") and not domain:
        domain = state_domain

    # 3) Extra refinement: if message is a single code token -> more likely LOOKUP than CHAT
    if intent == "CHAT" and _looks_like_code_only(t):
        intent = "LOOKUP"

    return {"domain": domain or "", "intent": intent, "norm_text": t}
