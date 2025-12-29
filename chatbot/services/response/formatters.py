from html import escape

def html_paragraphs(lines):
    return "<br>".join(lines)

def system_note(text: str) -> str:
    return f"<span style='color:#64748b'>{escape(text)}</span>"

def link(label: str, url: str) -> str:
    safe_label = escape(label)
    safe_url = escape(url, quote=True)
    return f"<a class='chatbot-link' href='{safe_url}' target='_blank' rel='noopener noreferrer'>{safe_label}</a>"

def bullet_list(items):
    # items are already safe HTML strings or escaped outside
    return "<br>".join([f"• {i}" for i in items])
