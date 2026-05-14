"""In-process HTTP rate limiting (slowapi), keyed by client IP via ``request.client``."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _make_limiter() -> Limiter:
    s = get_settings()
    if s.rate_limit_enabled:
        return Limiter(key_func=get_remote_address, enabled=True, default_limits=[s.rate_limit_default])
    return Limiter(key_func=get_remote_address, enabled=False)


limiter = _make_limiter()
