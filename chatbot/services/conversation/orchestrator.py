from typing import Dict, Any, Optional
import logging
import json
from pathlib import Path

from .router import route
from .state import get_state, set_state, set_fuzzy_last
from ..response.formatters import html_paragraphs, system_note

logger = logging.getLogger("chatbot")

# ===================== LLM (optional) =====================
LLM_READY = False
TPL = ""

try:
    from chatbot.services.llm.client import ollama_chat, build_prompt  # bạn tự implement
    TPL = Path("chatbot/services/llm/prompts/chat_response.md").read_text(encoding="utf-8")
    LLM_READY = True
except Exception:
    LLM_READY = False
    logger.exception("LLM prompt/client not ready (will fallback to static replies)")

# ===================== LOOKUP =====================
try:
    from lookup.services.tool.lookup_by_name import lookup_tool_by_name
    from lookup.services.tool.similar_by_code import similar_tool_by_code
    from lookup.services.holder.lookup_by_name import lookup_holder_by_name
    from lookup.services.holder.similar_by_code import similar_holder_by_code
    LOOKUP_READY = True
except Exception:
    LOOKUP_READY = False
    logger.exception("LOOKUP import failed")

# ===================== FUZZY =====================
try:
    from fuzzy_reco.services.tool.engine import score_tool_candidates
    from fuzzy_reco.services.holder.engine import score_holder_candidates
    FUZZY_READY = True
except Exception:
    FUZZY_READY = False
    logger.exception("FUZZY import failed")


def _looks_like_code_only(msg: str) -> bool:
    s = (msg or "").strip()
    return (len(s) >= 6) and (" " not in s)


def handle_message(request, message: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    ctx: { model, explain_fuzzy, request_id }
    return: { reply: "<html...>" }
    """
    rid = ctx.get("request_id", "noid")
    state = get_state(request)

    r = route(message, state_domain=state.get("domain"))
    domain = r.get("domain") or None
    intent = r.get("intent")

    logger.debug(f"[{rid}] ROUTE_RESULT intent={intent} domain={domain} state_domain={state.get('domain')}")
    logger.debug(f"[{rid}] READY lookup={LOOKUP_READY} fuzzy={FUZZY_READY} llm={LLM_READY}")

    # Escape hatch: mã hàng thì LOOKUP luôn
    if _looks_like_code_only(message) and intent == "CHAT":
        intent = "LOOKUP"
        logger.debug(f"[{rid}] ESCAPE_HATCH: force intent=LOOKUP for code-like input")

    if domain:
        set_state(request, domain=domain)

    if intent == "LOOKUP":
        return _handle_lookup(request, message, domain, ctx, rid)

    if intent == "FUZZY":
        if not domain:
            set_state(request, pending_intent="FUZZY", missing_fields=["domain"])
            return {
                "reply": html_paragraphs([
                    "Ok 😄 Bạn muốn mình <b>đề xuất fuzzy</b> cho <b>Tool</b> hay <b>Holder</b>?",
                    "• <b>Tool</b> (dao, mũi khoan, taro...)",
                    "• <b>Holder</b> (bầu kẹp, chuẩn gá, collet...)",
                    system_note("Gợi ý: gõ 'tool: ...' hoặc 'holder: ...' để mình hiểu ngay."),
                ])
            }
        return _handle_fuzzy(request, message, domain, ctx, rid)

    # CHAT fallback (thân thiện)
    return {
        "reply": html_paragraphs([
            "Chào bạn 👋 Mình là trợ lý kho công cụ TMS.",
            "Bạn muốn <b>tra cứu</b> hay <b>đề xuất</b> theo nhu cầu?",
            "",
            "🔎 <b>Tra cứu</b>: gửi <b>mã</b> hoặc <b>tên</b> (vd: <b>SER8350A0B11</b>, <b>EM12-...</b>)",
            "✨ <b>Đề xuất fuzzy</b>: (vd: <b>tool: khá rẻ nhưng cần bền</b> / <b>holder: ưu tiên chính xác, độ đảo thấp</b>)",
            system_note("Tip: Bạn không cần gõ 'là gì', chỉ gửi mã thôi cũng được."),
        ])
    }


def _handle_lookup(request, message: str, domain: Optional[str], ctx: Dict[str, Any], rid: str) -> Dict[str, Any]:
    if not LOOKUP_READY:
        logger.debug(f"[{rid}] LOOKUP not ready -> stub reply")
        return {
            "reply": html_paragraphs([
                "<b>Lookup</b> đang ở chế độ stub (chưa viết app lookup).",
                system_note("Bạn đã tạo app lookup rồi, nếu vẫn thấy dòng này => import path đang sai."),
            ])
        }

    text = (message or "").strip()
    lower = text.lower()
    want_similar = ("tương tự" in lower) or ("similar" in lower)

    logger.debug(f"[{rid}] LOOKUP start domain={domain} want_similar={want_similar} text='{text}'")

    def run_tool():
        return similar_tool_by_code(text) if want_similar else lookup_tool_by_name(text)

    def run_holder():
        return similar_holder_by_code(text) if want_similar else lookup_holder_by_name(text)

    # domain rõ -> chạy đúng
# domain rõ -> chạy đúng (nhưng có fallback khi đoán nhầm)
    if domain == "tool":
        data = run_tool()
        logger.debug(f"[{rid}] LOOKUP tool found={data.get('found')} query={data.get('query')}")
        if data.get("found"):
            return _render_lookup_with_llm(data, ctx, rid)

        # FALLBACK: tool không thấy -> thử holder
        data2 = run_holder()
        logger.debug(f"[{rid}] LOOKUP fallback holder found={data2.get('found')} query={data2.get('query')}")
        if data2.get("found"):
            set_state(request, domain="holder")  # cập nhật state cho lần sau
            return _render_lookup_with_llm(data2, ctx, rid)

        return _render_lookup_with_llm(data, ctx, rid)  # hoặc trả not found chung


    if domain == "holder":
        data = run_holder()
        logger.debug(f"[{rid}] LOOKUP holder found={data.get('found')} query={data.get('query')}")
        if data.get("found"):
            return _render_lookup_with_llm(data, ctx, rid)

        # FALLBACK: holder không thấy -> thử tool
        data2 = run_tool()
        logger.debug(f"[{rid}] LOOKUP fallback tool found={data2.get('found')} query={data2.get('query')}")
        if data2.get("found"):
            set_state(request, domain="tool")
            return _render_lookup_with_llm(data2, ctx, rid)

        return _render_lookup_with_llm(data, ctx, rid)

    # domain chưa rõ -> thử tool rồi holder
    data1 = run_tool()
    logger.debug(f"[{rid}] LOOKUP auto tool found={data1.get('found')} query={data1.get('query')}")
    if data1.get("found"):
        set_state(request, domain="tool")
        return _render_lookup_with_llm(data1, ctx, rid)

    data2 = run_holder()
    logger.debug(f"[{rid}] LOOKUP auto holder found={data2.get('found')} query={data2.get('query')}")
    if data2.get("found"):
        set_state(request, domain="holder")
        return _render_lookup_with_llm(data2, ctx, rid)

    return {
        "reply": html_paragraphs([
            "Mình chưa tìm thấy mã/tên này trong <b>Tool</b> và <b>Holder</b> 😅",
            "Bạn thử giúp mình 1 trong các cách sau nhé:",
            "• Gửi lại <b>mã chính xác</b> (không thừa ký tự)",
            "• Hoặc thêm tiền tố: <b>tool: ...</b> / <b>holder: ...</b>",
            "• Hoặc gõ: <b>... tương tự</b> để mình tìm mã gần giống",
            system_note("Ví dụ: 'tool: EM12-ABC' hoặc 'holder: BT40-...'"),
        ])
    }

def normalize_lookup_text(text: str) -> str:
    """
    Giữ nguyên nội dung, chỉ chuẩn hoá xuống dòng cho dễ đọc
    """
    if not text:
        return ""

    t = text

    # 1. Chuẩn hoá dấu phân cách
    t = t.replace(" | ", "\n")
    t = t.replace("| ", "\n")
    t = t.replace(" |", "\n")

    # 2. Gom các dòng, bỏ dòng rỗng
    lines = []
    for line in t.splitlines():
        line = line.strip()
        if line:
            lines.append(line)

    # 3. Trả về HTML-friendly
    return "<br>".join(lines)

def _render_lookup_with_llm(data: dict, ctx: Dict[str, Any], rid: str) -> Dict[str, Any]:
    """
    data: JSON từ lookup app (found, reply, item, similar...)
    - Nếu LLM ready: dùng prompt để LLM nói lại thân thiện
    - Nếu không: fallback data['reply']
    """
    if not data.get("found"):
        # không cần LLM cho not found (hoặc có thể dùng cũng được)
        return {
            "reply": html_paragraphs([
                data.get("reply", "Mình chưa tìm thấy."),
                system_note("Bạn có thể thử: nhập đúng mã hơn, hoặc thêm 'tương tự'."),
            ])
        }

    base_reply = normalize_lookup_text(data.get("reply", "OK"))


    if not LLM_READY:
        return {"reply": base_reply}

    try:
        prompt = build_prompt(
            TPL,
            user_message=str(ctx.get("user_message", "")) or "",
            mode="LOOKUP",
            domain=str(ctx.get("domain_override") or "unknown"),
            explain_fuzzy="0",
            payload_json=json.dumps(data, ensure_ascii=False),
        )
        model = (ctx.get("model") or "gemma3:4b").strip()
        ai_reply = ollama_chat(model, prompt)
        logger.debug(f"[{rid}] LLM lookup reply_len={len(ai_reply or '')}")
        return {"reply": ai_reply or base_reply}
    except Exception:
        logger.exception(f"[{rid}] LLM lookup failed -> fallback static")
        return {"reply": base_reply}


def _handle_fuzzy(request, message: str, domain: str, ctx: Dict[str, Any], rid: str) -> Dict[str, Any]:
    model = ctx.get("model")
    explain_fuzzy = bool(ctx.get("explain_fuzzy"))

    logger.debug(f"[{rid}] FUZZY start domain={domain} model={model} explain={explain_fuzzy}")

    parse = _stub_parse_to_scores(message, domain)
    logger.debug(f"[{rid}] FUZZY parse_status={parse.get('status')} inputs={parse.get('inputs')}")

    if parse["status"] == "need_more_info":
        set_state(request, pending_intent="FUZZY", missing_fields=parse.get("missing_fields", []))
        return {"reply": parse["clarifying_question"]}

    if FUZZY_READY:
        fuzzy_out = score_tool_candidates(parse["inputs"]) if domain == "tool" else score_holder_candidates(parse["inputs"])
        logger.debug(f"[{rid}] FUZZY engine={fuzzy_out.get('engine_version')}")
    else:
        fuzzy_out = _demo_fuzzy_score(parse["inputs"], domain)
        logger.debug(f"[{rid}] FUZZY fallback demo")

    top3 = (fuzzy_out.get("ranked") or [])[:3]
    logger.debug(f"[{rid}] FUZZY top3={[(x.get('code'), x.get('score')) for x in top3]}")
    logger.debug(f"[{rid}] FUZZY rules={fuzzy_out.get('rules_fired')}")

    payload = {"parse": parse, "fuzzy": fuzzy_out}

    set_fuzzy_last(request, {
        "domain": domain,
        "model": model,
        "explain_fuzzy": explain_fuzzy,
        "parse": parse,
        "fuzzy": fuzzy_out,
    })

    # Nếu có LLM thì để LLM giải thích cho mượt
    if LLM_READY:
        try:
            prompt = build_prompt(
                TPL,
                user_message=message,
                mode="FUZZY",
                domain=domain,
                explain_fuzzy="1" if explain_fuzzy else "0",
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
            ai_reply = ollama_chat(model, prompt)
            logger.debug(f"[{rid}] LLM fuzzy reply_len={len(ai_reply or '')}")
            if ai_reply:
                return {"reply": ai_reply}
        except Exception:
            logger.exception(f"[{rid}] LLM fuzzy failed -> fallback static")

    # fallback static
    reply_lines = [
        f"Ok, mình đã chạy fuzzy cho <b>{domain.upper()}</b> ✅",
        "",
        "🎛️ <b>Nhu cầu bạn nói:</b>",
        f"• Mức giá: <b>{parse['inputs']['cost_level']}/10</b>",
        f"• Ưu tiên: bền <b>{parse['inputs'].get('durability_importance')}</b>/10, "
        f"chính xác <b>{parse['inputs'].get('precision_importance')}</b>/10, "
        f"tốc độ <b>{parse['inputs'].get('speed_importance')}</b>/10",
        "",
        system_note("Bấm icon 📈 để xem JSON fuzzy gần nhất (debug)."),
    ]
    return {"reply": html_paragraphs(reply_lines)}


# ===================== Stub parse & demo =====================
def _stub_parse_to_scores(text: str, domain: str) -> Dict[str, Any]:
    t = text.lower()

    if "khá rẻ" in t or ("rẻ" in t and "đắt" not in t):
        cost = 3
    elif "tầm trung" in t or "trung bình" in t:
        cost = 5
    elif "đắt" in t or "cao cấp" in t or "xịn" in t:
        cost = 8
    else:
        cost = None

    precision = 8 if ("chính xác" in t or "độ đảo" in t or "runout" in t) else 5
    durability = 8 if ("bền" in t or "tuổi thọ" in t) else 5
    speed = 7 if ("tốc" in t or "nhanh" in t) else 4

    if cost is None:
        return {
            "status": "need_more_info",
            "missing_fields": ["cost_level"],
            "clarifying_question": html_paragraphs([
                "Bạn muốn mức giá nào?",
                "• <b>Rẻ</b> (khá rẻ)  • <b>Tầm trung</b>  • <b>Cao cấp</b> (đắt/xịn)",
                system_note("Ví dụ: 'khá rẻ nhưng cần bền'"),
            ]),
            "inputs": {}
        }

    return {
        "status": "ok",
        "domain": domain,
        "inputs": {
            "cost_level": cost,
            "precision_importance": precision,
            "durability_importance": durability,
            "speed_importance": speed,
        },
        "missing_fields": [],
        "confidence": 0.7
    }


def _demo_fuzzy_score(inputs: Dict[str, Any], domain: str) -> Dict[str, Any]:
    cost = inputs.get("cost_level", 5)
    prec = inputs.get("precision_importance", 5)
    dura = inputs.get("durability_importance", 5)
    speed = inputs.get("speed_importance", 5)

    score = (10 - cost) * 6 + prec * 7 + dura * 4 + speed * 3
    score = max(0, min(100, score / 2))

    return {
        "engine_version": "demo_v1",
        "domain": domain,
        "decision": {
            "score": round(score, 2),
            "label": "best_match" if score >= 75 else "good" if score >= 60 else "ok" if score >= 40 else "weak",
        },
        "ranked": [],
        "rules_fired": [],
        "breakdown": {"inputs": inputs},
    }
