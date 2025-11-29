# chatbot/handlers_fuzzy.py
from .fuzzy import run_fuzzy_suggest


def handle_fuzzy_suggest(user_message: str, debug: bool = False) -> str:
    result = run_fuzzy_suggest(user_message, debug=debug)
    return result["message"]
