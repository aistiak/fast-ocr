from __future__ import annotations

import logging
import time
from typing import Any

from app.domain.errors import OcrError
from app.helpers.image import MAX_IMAGE_BYTES, is_supported_image
from app.repositories.base import JobRepository
from app.repositories.firestore_jobs import FirestoreJobRepository
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

MAX_BATCH_FILES = 5


def _item(
    *,
    filename: str,
    success: bool,
    text: str = "",
    confidence: float = 0.0,
    processing_time_ms: int = 0,
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "filename": filename,
        "success": success,
        "text": text,
        "confidence": confidence,
        "processing_time_ms": processing_time_ms,
        "metadata": metadata or {},
        "error": error,
    }


class JobService:
    def __init__(self, repository: JobRepository | None = None) -> None:
        self._repository = repository or FirestoreJobRepository()

    async def begin_job(self, idempotency_key: str) -> dict[str, Any]:
        return await self._repository.begin(idempotency_key)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        return await self._repository.get(job_id)

    async def process_batch(self, job_id: str, files: list[tuple[str, bytes]]) -> None:
        logger.info("JobService start job_id=%s files=%s", job_id, len(files))
        results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0

        try:
            for filename, image_bytes in files:
                item = await self._process_file(filename, image_bytes)
                results.append(item)
                if item["success"]:
                    success_count += 1
                else:
                    failure_count += 1

            status = "success" if success_count >= 1 else "failed"
            error = None if success_count >= 1 else "All images failed to process"
            await self._repository.complete(
                job_id,
                status=status,
                success_count=success_count,
                failure_count=failure_count,
                result=results,
                error=error,
            )
            logger.info(
                "JobService done job_id=%s status=%s success_count=%s failure_count=%s",
                job_id,
                status,
                success_count,
                failure_count,
            )
        except Exception:
            logger.exception("JobService aborted job_id=%s", job_id)
            try:
                await self._repository.complete(
                    job_id,
                    status="failed",
                    success_count=success_count,
                    failure_count=failure_count + (len(files) - len(results)),
                    result=results,
                    error="Batch processing failed",
                )
            except Exception:
                logger.exception("JobService could not persist failure job_id=%s", job_id)

    async def _process_file(self, filename: str, image_bytes: bytes) -> dict[str, Any]:
        started = time.perf_counter()

        def elapsed_ms() -> int:
            return max(0, int((time.perf_counter() - started) * 1000))

        if not image_bytes:
            return _item(
                filename=filename,
                success=False,
                processing_time_ms=elapsed_ms(),
                error="Empty upload.",
            )
        if len(image_bytes) > MAX_IMAGE_BYTES:
            return _item(
                filename=filename,
                success=False,
                processing_time_ms=elapsed_ms(),
                error="File larger than 10MB.",
            )
        if not is_supported_image(image_bytes):
            return _item(
                filename=filename,
                success=False,
                processing_time_ms=elapsed_ms(),
                error="Not a JPEG, PNG, or GIF.",
            )

        try:
            text, confidence, metadata = await ocr_service.extract_text(image_bytes)
        except OcrError as exc:
            return _item(
                filename=filename,
                success=False,
                processing_time_ms=elapsed_ms(),
                metadata=exc.metadata,
                error=str(exc) or "Vision OCR failed.",
            )

        return _item(
            filename=filename,
            success=True,
            text=text,
            confidence=confidence,
            processing_time_ms=elapsed_ms(),
            metadata=metadata,
        )


job_service = JobService()
