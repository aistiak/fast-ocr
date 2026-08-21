import asyncio
import logging
from typing import Any

from app.domain.errors import OcrError
from app.helpers.image_meta import extract_image_metadata
from app.services.vision_ocr import extract_text as vision_extract_text

logger = logging.getLogger(__name__)


class OcrService:
    async def extract_text(self, image_bytes: bytes) -> tuple[str, float, dict[str, Any]]:
        metadata = extract_image_metadata(image_bytes)
        logger.info(
            "OcrService calling VisionService format=%s",
            metadata.get("format", "unknown"),
        )
        try:
            text, confidence = await asyncio.to_thread(vision_extract_text, image_bytes)
        except OcrError as exc:
            exc.metadata = metadata
            raise
        return text, confidence, metadata


ocr_service = OcrService()
