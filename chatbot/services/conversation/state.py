from typing import Any, Dict, Optional

SESSION_KEY = "tms_chatbot_state"
FUZZY_LAST_KEY = "tms_fuzzy_last"

def get_state(request) -> Dict[str, Any]:
    state = request.session.get(SESSION_KEY)
    if not isinstance(state, dict):
        state = {
            "domain": None,          # "tool" | "holder" | None
            "pending_intent": None,  # ví dụ: "fuzzy" khi đang hỏi thiếu thông tin
            "missing_fields": [],
        }
        request.session[SESSION_KEY] = state
    return state

def set_state(request, **kwargs) -> Dict[str, Any]:
    state = get_state(request)
    state.update(kwargs)
    request.session[SESSION_KEY] = state
    request.session.modified = True
    return state

def set_fuzzy_last(request, payload: Dict[str, Any]) -> None:
    request.session[FUZZY_LAST_KEY] = payload
    request.session.modified = True

def get_fuzzy_last_for_debug(request) -> Optional[Dict[str, Any]]:
    data = request.session.get(FUZZY_LAST_KEY)
    return data if isinstance(data, dict) else None
