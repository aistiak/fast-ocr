import logging
from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
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
_OPENAPI_TAGS = [
    {
        "name": "ocr",
        "description": "Extract text from an uploaded image, including async batches.",
    },
    {
        "name": "health",
        "description": "Liveness checks.",
    },
]


def _api_description(base_url: str) -> str:
    base = base_url.rstrip("/")
    return f"""
OCR API backed by Google Cloud Vision.

**Try it out:** open an endpoint, click **Try it out**, upload a JPEG/PNG/GIF (max 10MB), then **Execute**.

**cURL**

```bash
curl -X POST -F "image=@sample-images/image1.JPG" {base}/extract-text
```

**Batch (max 5 files, 10MB each)**

```bash
curl -X POST \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -F "images=@sample-images/image1.JPG" \\
  -F "images=@sample-images/image2.JPG" \\
  {base}/extract-text/batch

curl {base}/jobs/{{job_id}}
```
"""


def _public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto")
    scheme = proto.split(",")[0].strip() if proto else request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        return str(request.base_url).rstrip("/")
    return f"{scheme}://{host}"


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=_api_description("http://localhost:8080"),
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    openapi_tags=_OPENAPI_TAGS,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(api_router)


@lru_cache(maxsize=8)
def _openapi_schema(base_url: str) -> dict:
    return get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=_api_description(base_url),
        routes=app.routes,
        tags=app.openapi_tags,
        servers=[{"url": base_url}],
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_json(request: Request) -> JSONResponse:
    return JSONResponse(_openapi_schema(_public_base_url(request)))


@app.get("/docs", include_in_schema=False)
async def swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_name} - Docs",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui() -> HTMLResponse:
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_name} - ReDoc",
    )


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
