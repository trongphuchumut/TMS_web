from html import escape

def link_html(label: str, url: str) -> str:
    return f"<a class='chatbot-link' href='{escape(url, quote=True)}' target='_blank' rel='noopener noreferrer'>{escape(label)}</a>"

def br(lines):
    return "<br>".join(lines)

def safe(v):
    return escape("" if v is None else str(v))
