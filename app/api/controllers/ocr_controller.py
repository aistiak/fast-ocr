from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import UploadFile
from fastapi.responses import JSONResponse

from app.api.schemas.ocr import extract_text_payload
from app.domain.errors import OcrError
from app.helpers.image import MAX_IMAGE_BYTES, is_supported_image
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _response(
    *,
    success: bool,
    text: str,
    confidence: float,
    started: float,
    status_code: int = 200,
    metadata: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=extract_text_payload(
            success=success,
            text=text,
            confidence=confidence,
            processing_time_ms=_elapsed_ms(started),
            metadata=metadata,
        ),
    )


async def extract_text(image: UploadFile) -> JSONResponse:
    started = time.perf_counter()
    filename = image.filename or "unknown"

    image_bytes = await image.read()
    logger.info("controller received filename=%s size=%s", filename, len(image_bytes))

    if not image_bytes:
        logger.warning("controller rejected empty upload filename=%s", filename)
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=400,
        )
    if len(image_bytes) > MAX_IMAGE_BYTES:
        logger.warning(
            "controller rejected oversized upload filename=%s size=%s",
            filename,
            len(image_bytes),
        )
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=413,
        )
    if not is_supported_image(image_bytes):
        logger.warning("controller rejected unsupported type filename=%s", filename)
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=415,
        )

    logger.info("controller calling OcrService")
    try:
        text, confidence, metadata = await ocr_service.extract_text(image_bytes)
    except OcrError as exc:
        logger.exception("controller Vision OCR failed filename=%s", filename)
        return _response(
            success=False,
            text="",
            confidence=0.0,
            started=started,
            status_code=502,
            metadata=exc.metadata,
        )

    elapsed = _elapsed_ms(started)
    logger.info(
        "controller done chars=%s confidence=%s ms=%s",
        len(text),
        confidence,
        elapsed,
    )
    return _response(
        success=True,
        text=text,
        confidence=confidence,
        started=started,
        metadata=metadata,
    )
