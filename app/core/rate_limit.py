import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.api.schemas.ocr import extract_text_payload

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=client_ip, default_limits=[])


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    logger.warning("rate limit exceeded ip=%s", client_ip(request))
    return JSONResponse(
        status_code=429,
        content=extract_text_payload(success=False),
        headers={"Retry-After": "60"},
    )
