import time
from collections import defaultdict
from fastapi import HTTPException, status
from app.core.config import settings

_request_log: dict[str, list[float]] = defaultdict(list)

def check_rate_limit(user_email:str) -> None:
    """Check user has exceeded the rate limit"""
    now = time.time()
    window = 60.0 # 1 minute window

    # Remove timestamps older than 1 minute
    _request_log[user_email] = [
        ts for ts in _request_log[user_email]
        if now - ts < window
    ]

    # Check for limit exceeded
    if len(_request_log[user_email]) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {settings.RATE_LIMIT_PER_MINUTE} requests per minute allowed."
        )
    
    # Log this request
    _request_log[user_email].append(now)