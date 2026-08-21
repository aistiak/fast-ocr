import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from app.api.routes import api_router
from app.api.schemas.errors import error_payload
from app.api.schemas.ocr import extract_text_payload
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

setup_logging()

logger = logging.getLogger("app.http")

_SKIP_REQUEST_LOG = frozenset({"/", "/ping", "/docs", "/redoc", "/openapi.json"})

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="""
OCR API backed by Google Cloud Vision.

**Try it out:** open an endpoint, click **Try it out**, upload a JPEG/PNG/GIF (max 10MB), then **Execute**.

**cURL**

```bash
curl -X POST -F "image=@sample-images/image1.JPG" http://localhost:8080/extract-text
```

**Batch (max 5 files, 10MB each)**

```bash
curl -X POST \
  -H "Idempotency-Key: $(uuidgen)" \
  -F "images=@sample-images/image1.JPG" \
  -F "images=@sample-images/image2.JPG" \
  http://localhost:8080/extract-text/batch

curl http://localhost:8080/jobs/{job_id}
```
""",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "ocr",
            "description": "Extract text from an uploaded image, including async batches.",
        },
        {
            "name": "health",
            "description": "Liveness checks.",
        },
    ],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(api_router)


def _is_single_extract(request: Request) -> bool:
    return request.url.path.rstrip("/").endswith("/extract-text")


def _internal_error_body(request: Request) -> dict:
    message = "An unexpected error occurred."
    if _is_single_extract(request):
        return extract_text_payload(
            success=False,
            error="internal_error",
            message=message,
        )
    return error_payload("internal_error", message)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc_parts = [str(part) for part in first.get("loc", ()) if part != "body"]
    loc = ".".join(loc_parts)
    detail = first.get("msg") or "Invalid request."
    message = f"{loc}: {detail}" if loc else detail
    logger.warning("validation error %s %s: %s", request.method, request.url.path, message)
    return JSONResponse(
        status_code=422,
        content=error_payload("validation_error", message),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content=_internal_error_body(request))


@app.middleware("http")
async def log_incoming_request(request: Request, call_next) -> Response:
    if request.url.path not in _SKIP_REQUEST_LOG:
        logger.info(
            "incoming %s %s",
            request.method,
            request.url.path,
        )
    return await call_next(request)
