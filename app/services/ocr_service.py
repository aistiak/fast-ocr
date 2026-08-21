import asyncio
import logging
from typing import Any

from app.domain.errors import OcrError
from app.helpers.image import image_hash
from app.helpers.image_meta import extract_image_metadata
from app.repositories.base import OcrResultRepository
from app.repositories.firestore_ocr import FirestoreOcrResultRepository
from app.services.vision_ocr import extract_text as vision_extract_text

logger = logging.getLogger(__name__)


class OcrService:
    def __init__(self, repository: OcrResultRepository | None = None) -> None:
        self._repository = repository or FirestoreOcrResultRepository()

    async def extract_text(self, image_bytes: bytes) -> tuple[str, float, dict[str, Any]]:
        digest = image_hash(image_bytes)
        logger.info("OcrService cache lookup hash=%s", digest[:12])

        cached = await self._get_cached(digest)
        if cached is not None:
            logger.info("OcrService cache hit")
            return cached["text"], cached["confidence"], cached["metadata"]

        metadata = extract_image_metadata(image_bytes)
        logger.info(
            "OcrService cache miss, calling VisionService format=%s",
            metadata.get("format", "unknown"),
        )
        try:
            text, confidence = await asyncio.to_thread(vision_extract_text, image_bytes)
        except OcrError as exc:
            exc.metadata = metadata
            raise

        await self._save_cached(
            digest,
            text=text,
            confidence=confidence,
            metadata=metadata,
        )
        return text, confidence, metadata

    async def _get_cached(self, digest: str) -> dict[str, Any] | None:
        try:
            return await self._repository.get(digest)
        except Exception as exc:
            logger.error("OcrService cache lookup failed: %s", exc)
            return None

    async def _save_cached(
        self,
        digest: str,
        *,
        text: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> None:
        try:
            await self._repository.save(
                digest,
                text=text,
                confidence=confidence,
                metadata=metadata,
            )
        except Exception as exc:
            logger.error("OcrService cache save failed: %s", exc)


ocr_service = OcrService()
