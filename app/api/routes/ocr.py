from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.vision_ocr import OcrError, extract_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ocr"])

MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/tif",
}
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


class ExtractTextResponse(BaseModel):
    success: bool
    text: str
    confidence: float
    processing_time_ms: int = Field(ge=0)


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


def _is_allowed_image(upload: UploadFile) -> bool:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type in ALLOWED_CONTENT_TYPES:
        return True
    filename = (upload.filename or "").lower()
    return any(filename.endswith(suffix) for suffix in ALLOWED_SUFFIXES)


@router.post("/extract-text")
async def extract_text_from_image(
    image: Annotated[UploadFile, File(description="Image file to OCR")],
) -> JSONResponse:
    started = time.perf_counter()

    if not image.filename:
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=400,
        )

    if not _is_allowed_image(image):
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
