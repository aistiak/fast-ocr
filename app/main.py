import logging

from fastapi import FastAPI, Request
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

setup_logging()

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


@app.middleware("http")
async def log_incoming_request(request: Request, call_next) -> Response:
    if request.url.path not in _SKIP_REQUEST_LOG:
        logging.getLogger("app.http").info(
            "incoming %s %s",
            request.method,
            request.url.path,
        )
    return await call_next(request)
