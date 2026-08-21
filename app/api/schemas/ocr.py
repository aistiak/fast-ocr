from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.errors import ErrorResponse


class ExtractTextResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "text": "Extracted text from the image.",
                "confidence": 0.95,
                "processing_time_ms": 1234,
                "metadata": {
                    "format": "png",
                    "width": 1514,
                    "height": 470,
                    "Title": "Fast OCR sample image two",
                    "Author": "Sample User",
                    "Comment": "Synthetic metadata added for local testing",
                },
                "error": None,
                "message": None,
            }
        }
    )

    success: bool = Field(description="Whether OCR completed successfully.")
    text: str = Field(description="Cleaned text from the image. Empty on failure.")
    confidence: float = Field(
        ge=0,
        le=1,
        description="Mean Vision confidence for the detected text (0–1).",
    )
    processing_time_ms: int = Field(
        ge=0,
        description="Wall-clock time for this request, including the Vision call.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Image material when available (format, width, height, and PNG/JPEG text tags). Empty object otherwise.",
    )
    error: str | None = Field(
        default=None,
        description="Machine-readable code on failure. Null on success.",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable explanation on failure. Null on success.",
    )


EXTRACT_TEXT_RESPONSES = {
    200: {"model": ExtractTextResponse, "description": "Text extracted."},
    400: {"model": ExtractTextResponse, "description": "Empty upload."},
    413: {"model": ExtractTextResponse, "description": "File larger than 10MB."},
    415: {
        "model": ExtractTextResponse,
        "description": "Not a JPEG, PNG, or GIF (file signature).",
    },
    422: {"model": ErrorResponse, "description": "Missing `image` form field."},
    429: {"model": ExtractTextResponse, "description": "More than 20 requests per minute."},
    500: {"model": ExtractTextResponse, "description": "Unexpected server error."},
    502: {"model": ExtractTextResponse, "description": "Vision API error."},
}


def extract_text_payload(
    *,
    success: bool,
    text: str = "",
    confidence: float = 0.0,
    processing_time_ms: int = 0,
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    return ExtractTextResponse(
        success=success,
        text=text,
        confidence=confidence,
        processing_time_ms=processing_time_ms,
        metadata=metadata or {},
        error=error,
        message=message,
    ).model_dump()
