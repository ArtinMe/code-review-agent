import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(title: str, max_length: int = 60) -> str:
    """Turn a title into a URL-safe slug."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _NON_WORD.sub("-", ascii_only.lower()).strip("-")
    return slug[:max_length].rstrip("-")
