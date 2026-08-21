from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from app.api.routes import health, ocr
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

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
""",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "ocr",
            "description": "Extract text from an uploaded image.",
        },
        {
            "name": "health",
            "description": "Liveness checks.",
        },
    ],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(health.router)
app.include_router(ocr.router)
