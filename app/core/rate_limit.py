import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.api.schemas.errors import error_payload
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


def _is_single_extract(request: Request) -> bool:
    return request.url.path.rstrip("/").endswith("/extract-text")


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    logger.warning("rate limit exceeded ip=%s", client_ip(request))
    message = "Too many requests. Try again in 60 seconds."
    if _is_single_extract(request):
        content = extract_text_payload(
            success=False,
            error="rate_limited",
            message=message,
        )
    else:
        content = error_payload("rate_limited", message)
    return JSONResponse(
        status_code=429,
        content=content,
        headers={"Retry-After": "60"},
    )
