from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.services.vision_ocr import OcrError, extract_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ocr"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024
FORMAT_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
}


class ExtractTextResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "text": "Extracted text from the image.",
                "confidence": 0.95,
                "processing_time_ms": 1234,
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


EXTRACT_TEXT_RESPONSES = {
    200: {"model": ExtractTextResponse, "description": "Text extracted."},
    400: {"model": ExtractTextResponse, "description": "Empty upload."},
    413: {"model": ExtractTextResponse, "description": "File larger than 10MB."},
    415: {
        "model": ExtractTextResponse,
        "description": "Not a JPEG, PNG, or GIF, or extension does not match the file signature.",
    },
    422: {"description": "Missing `image` form field."},
    502: {"model": ExtractTextResponse, "description": "Vision API error."},
}


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _response(
    *,
    success: bool,
    text: str,
    confidence: float,
    started: float,
    status_code: int = 200,
) -> JSONResponse:
    body = ExtractTextResponse(
        success=success,
        text=text,
        confidence=confidence,
        processing_time_ms=_elapsed_ms(started),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _image_suffix(filename: str | None) -> str | None:
    suffix = Path(filename or "").suffix.lower()
    if suffix in FORMAT_SIGNATURES:
        return suffix
    return None


def _matches_signature(suffix: str, image_bytes: bytes) -> bool:
    return any(image_bytes.startswith(signature) for signature in FORMAT_SIGNATURES[suffix])


@router.post(
    "/extract-text",
    response_model=ExtractTextResponse,
    responses=EXTRACT_TEXT_RESPONSES,
    summary="Extract text from an image",
    description=(
        "Upload a JPEG, PNG, or GIF (`multipart/form-data` field `image`, max 10MB). "
        "The filename extension must match the file signature. "
        "Uses Google Cloud Vision document text detection."
    ),
)
async def extract_text_from_image(
    image: Annotated[
        UploadFile,
        File(description="JPEG, PNG, or GIF file. Field name: `image`. Max 10MB."),
    ],
) -> JSONResponse:
    started = time.perf_counter()

    suffix = _image_suffix(image.filename)
    if suffix is None:
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=415,
        )

    image_bytes = await image.read()
    if not image_bytes:
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=400,
        )
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=413,
        )
    if not _matches_signature(suffix, image_bytes):
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=415,
        )

    try:
        text, confidence = await asyncio.to_thread(extract_text, image_bytes)
    except OcrError:
        logger.exception("Vision OCR failed")
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=502,
        )

    return _response(
        success=True,
        text=text,
        confidence=confidence,
        started=started,
    )
