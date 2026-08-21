from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.controllers.job_controller import create_batch_job, get_job_status
from app.api.controllers.ocr_controller import extract_text
from app.api.schemas.job import (
    JOB_ACCEPTED_RESPONSES,
    JOB_STATUS_RESPONSES,
    JobAcceptedResponse,
    JobStatusResponse,
)
from app.api.schemas.ocr import EXTRACT_TEXT_RESPONSES, ExtractTextResponse
from app.core.rate_limit import limiter

router = APIRouter(tags=["ocr"])


@router.post(
    "/extract-text",
    response_model=ExtractTextResponse,
    responses=EXTRACT_TEXT_RESPONSES,
    summary="Extract text from an image",
    description=(
        "Upload a JPEG, PNG, or GIF (`multipart/form-data` field `image`, max 10MB). "
        "The file is identified by its signature, not the filename extension. "
        "Uses Google Cloud Vision document text detection. "
        "Limited to 20 requests per minute per client IP."
    ),
)
@limiter.limit("20/minute")
async def extract_text_from_image(
    request: Request,
    image: Annotated[
        UploadFile,
        File(description="JPEG, PNG, or GIF file. Field name: `image`. Max 10MB."),
    ],
) -> JSONResponse:
    return await extract_text(image)


@router.post(
    "/extract-text/batch",
    response_model=JobAcceptedResponse,
    responses=JOB_ACCEPTED_RESPONSES,
    status_code=202,
    summary="Extract text from up to 5 images",
    description=(
        "Upload 1–5 JPEG, PNG, or GIF files (`multipart/form-data` field `images`, max 10MB each). "
        "Creates a job and returns immediately with status processing. "
        "Requires the Idempotency-Key header; the same key returns the same job_id. "
        "Poll GET /jobs/{job_id} for results. "
        "Limited to 4 requests per minute per client IP. "
        "Each file uses the same hash cache as POST /extract-text."
    ),
)
@limiter.limit("4/minute")
async def extract_text_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    images: Annotated[
        list[UploadFile],
        File(description="1–5 image files. Field name: `images`. Max 10MB each."),
    ],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Required. Replay with the same key returns the original job.",
        ),
    ] = None,
) -> JSONResponse:
    return await create_batch_job(images, background_tasks, idempotency_key)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses=JOB_STATUS_RESPONSES,
    summary="Get batch job status",
    description="Look up a batch job by id. Status is processing, success, or failed.",
)
async def job_status(job_id: str) -> JSONResponse:
    return await get_job_status(job_id)
