from typing import Any, Dict, List, Optional

def ok_reply(intent: str, domain: str, reply: str, item: Optional[Dict[str, Any]] = None,
             similar: Optional[List[Dict[str, Any]]] = None, query: str = "") -> Dict[str, Any]:
    return {
        "intent": intent,
        "domain": domain,
        "query": query,
        "found": True,
        "item": item,
        "similar": similar or [],
        "reply": reply,
    }

def not_found_reply(intent: str, domain: str, reply: str, query: str = "") -> Dict[str, Any]:
    return {
        "intent": intent,
        "domain": domain,
        "query": query,
        "found": False,
        "item": None,
        "similar": [],
        "reply": reply,
    }
