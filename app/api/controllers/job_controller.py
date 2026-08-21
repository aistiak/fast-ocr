from __future__ import annotations

import logging

from fastapi import BackgroundTasks, UploadFile
from fastapi.responses import JSONResponse

from app.api.schemas.errors import error_payload
from app.api.schemas.job import JobAcceptedResponse, JobStatusResponse
from app.helpers.image import MAX_IMAGE_BYTES, is_supported_image
from app.services.job_service import MAX_BATCH_FILES, job_service

logger = logging.getLogger(__name__)

_MAX_IDEMPOTENCY_KEY_LENGTH = 256


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip()
    if not key or len(key) > _MAX_IDEMPOTENCY_KEY_LENGTH:
        return None
    if any(ord(char) < 32 for char in key):
        return None
    return key


def _file_issue(filename: str, image_bytes: bytes) -> dict[str, str] | None:
    if not image_bytes:
        return {
            "filename": filename,
            "error": "empty_upload",
            "message": "Empty upload.",
        }
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return {
            "filename": filename,
            "error": "payload_too_large",
            "message": "Each image must be 10MB or smaller.",
        }
    if not is_supported_image(image_bytes):
        return {
            "filename": filename,
            "error": "unsupported_media_type",
            "message": "Not a JPEG, PNG, or GIF.",
        }
    return None


def _rejected_files_response(issues: list[dict[str, str]]) -> JSONResponse:
    codes = {item["error"] for item in issues}
    if codes == {"payload_too_large"}:
        status_code = 413
        error = "payload_too_large"
        message = "Each image must be 10MB or smaller."
    elif codes == {"unsupported_media_type"}:
        status_code = 415
        error = "unsupported_media_type"
        message = "Not a JPEG, PNG, or GIF."
    elif codes == {"empty_upload"}:
        status_code = 400
        error = "empty_upload"
        message = "Empty upload."
    else:
        status_code = 400
        error = "invalid_files"
        message = "One or more files were rejected."
    logger.warning("controller rejected batch files=%s", issues)
    return JSONResponse(
        status_code=status_code,
        content=error_payload(error, message, files=issues),
    )


async def create_batch_job(
    images: list[UploadFile],
    background_tasks: BackgroundTasks,
    idempotency_key: str | None,
) -> JSONResponse:
    key = _normalize_idempotency_key(idempotency_key)
    if key is None:
        return JSONResponse(
            status_code=400,
            content=error_payload(
                "missing_idempotency_key",
                "Header Idempotency-Key is required (1–256 characters).",
            ),
        )
    if not images:
        return JSONResponse(
            status_code=400,
            content=error_payload(
                "invalid_batch",
                "Upload between 1 and 5 files in the images field.",
            ),
        )
    if len(images) > MAX_BATCH_FILES:
        return JSONResponse(
            status_code=400,
            content=error_payload(
                "too_many_files",
                f"Maximum {MAX_BATCH_FILES} files per batch.",
            ),
        )

    files: list[tuple[str, bytes]] = []
    issues: list[dict[str, str]] = []
    for image in images:
        filename = image.filename or "unknown"
        image_bytes = await image.read()
        files.append((filename, image_bytes))
        issue = _file_issue(filename, image_bytes)
        if issue is not None:
            issues.append(issue)

    if issues:
        return _rejected_files_response(issues)

    try:
        begun = await job_service.begin_job(key)
    except Exception:
        logger.exception("controller could not create job")
        return JSONResponse(
            status_code=503,
            content=error_payload("job_create_failed", "Could not create job."),
        )

    job_id = begun["job_id"]
    if begun["created"]:
        background_tasks.add_task(job_service.process_batch, job_id, files)
        logger.info("controller accepted batch job_id=%s files=%s", job_id, len(files))
    else:
        logger.info("controller idempotent replay job_id=%s", job_id)

    return JSONResponse(
        status_code=202,
        content=JobAcceptedResponse(job_id=job_id, status=begun["status"]).model_dump(),
    )


async def get_job_status(job_id: str) -> JSONResponse:
    try:
        job = await job_service.get_job(job_id)
    except Exception:
        logger.exception("controller could not load job_id=%s", job_id)
        return JSONResponse(
            status_code=503,
            content=error_payload("job_lookup_failed", "Could not load job."),
        )
    if job is None:
        return JSONResponse(
            status_code=404,
            content=error_payload("job_not_found", "Job not found."),
        )

    error = job.get("error")
    if error is not None and not isinstance(error, str):
        error = str(error)

    body = JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        success_count=job["success_count"],
        failure_count=job["failure_count"],
        error=error,
        result=job.get("result"),
    )
    return JSONResponse(status_code=200, content=body.model_dump())
