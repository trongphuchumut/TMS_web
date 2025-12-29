from typing import Dict, Any, List

def engine_result(domain: str, engine_version: str, inputs: Dict[str, Any],
                  ranked: List[Dict[str, Any]], rules_fired: List[str], breakdown: Dict[str, Any]) -> Dict[str, Any]:
    top_score = ranked[0]["score"] if ranked else 0.0
    label = "best_match" if top_score >= 80 else "good" if top_score >= 65 else "ok" if top_score >= 45 else "weak"

    return {
        "engine_version": engine_version,
        "domain": domain,
        "user_inputs": inputs,
        "decision": {
            "score": round(top_score, 2),
            "label": label,
        },
        "ranked": ranked,           # [{id, code, name, score, meta}]
        "rules_fired": rules_fired, # list string
        "breakdown": breakdown,     # detail weights + feature scores
    }
