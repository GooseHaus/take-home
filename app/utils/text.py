import re

_WHITESPACE = re.compile(r"\s+")


def clean_text(text: str | None, max_chars: int) -> str | None:
    """Collapse whitespace and cap length on a word boundary. Empty -> None."""
    if not text:
        return None
    text = _WHITESPACE.sub(" ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text or None
