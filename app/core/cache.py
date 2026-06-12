import time
from app.core.config import settings

# In-memory cache: { cache_key: {"answer": str, "expires_at": float} }
_cache: dict[str, dict] = {}


def _make_key(user_id: int, document_id: int, question: str) -> str:
    """Create a unique cache key from user + document + question."""
    return f"{user_id}:{document_id}:{question.strip().lower()}"


def get_cached_answer(user_id: int, document_id: int, question: str) -> tuple[str, list[int]] | None:
    """Return cached (answer, sources) if it exists and hasn't expired.
    Returns None if not found or expired."""
    key = _make_key(user_id, document_id, question)
    entry = _cache.get(key)

    if entry is None:
        return None

    # Check if expired
    if time.time() > entry["expires_at"]:
        del _cache[key]
        return None

    return entry["answer"], entry.get("sources", [])


def set_cached_answer(user_id: int, document_id: int, question: str, answer: str, sources: list[int]) -> None:
    """Save an answer to cache with TTL expiry."""
    key = _make_key(user_id, document_id, question)
    _cache[key] = {
        "answer": answer,
        "sources": sources,
        "expires_at": time.time() + settings.CACHE_TTL_SECONDS
    }
