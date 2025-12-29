import re

def extract_code_candidate(text: str) -> str:
    """
    Cố gắng bốc ra 1 "mã" từ câu user.
    - giữ lại token có chữ+số / dấu '-' '_' '.'
    """
    s = (text or "").strip()
    if not s:
        return ""

    # ưu tiên token dài nhất có vẻ giống mã hàng
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\._/]{2,}", s)
    if not tokens:
        return s
    tokens.sort(key=len, reverse=True)
    return tokens[0]

def tool_prefix(code: str) -> str:
    """
    prefix cho ma_tool:
    - nếu có '-' thì lấy phần trước '-' đầu tiên
    - nếu không có thì lấy 6-8 ký tự đầu (tuỳ độ dài)
    """
    c = (code or "").strip()
    if "-" in c:
        return c.split("-", 1)[0]
    if len(c) >= 8:
        return c[:8]
    if len(c) >= 6:
        return c[:6]
    return c

def normalize(s: str) -> str:
    return (s or "").strip()
