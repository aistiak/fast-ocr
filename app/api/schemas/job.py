from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.errors import ErrorResponse


class BatchItemResult(BaseModel):
    filename: str = Field(description="Original upload filename.")
    success: bool
    text: str = ""
    confidence: float = 0.0
    processing_time_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(
        default=None,
        description="Set when this file failed. Null on success.",
    )


class JobAcceptedResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "3f1c0a8e-2b7a-4d9c-9e11-7c2d4b8a1f00",
                "status": "processing",
            }
        }
    )

    job_id: str
    status: str = Field(
        description="processing on first accept; current job status if the Idempotency-Key is replayed.",
    )


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "3f1c0a8e-2b7a-4d9c-9e11-7c2d4b8a1f00",
                "status": "success",
                "success_count": 4,
                "failure_count": 1,
                "error": None,
                "result": [
                    {
                        "filename": "page1.jpg",
                        "success": True,
                        "text": "Hello",
                        "confidence": 0.95,
                        "processing_time_ms": 400,
                        "metadata": {"format": "jpeg", "width": 800, "height": 600},
                        "error": None,
                    }
                ],
            }
        }
    )

    job_id: str
    status: str = Field(description="processing, success, or failed.")
    success_count: int = Field(ge=0, description="Files that completed OCR successfully.")
    failure_count: int = Field(ge=0, description="Files that failed validation or OCR.")
    error: str | None = Field(
        default=None,
        description="Job-level error when status is failed.",
    )
    result: list[BatchItemResult] | None = Field(
        default=None,
        description="Per-file results, same order as the upload. Null while processing.",
    )


JOB_ACCEPTED_RESPONSES = {
    202: {"model": JobAcceptedResponse, "description": "Job created and running."},
    400: {"model": ErrorResponse, "description": "No files, more than 5 files, missing/invalid Idempotency-Key, or empty uploads."},
    413: {"model": ErrorResponse, "description": "One or more files are larger than 10MB."},
    415: {"model": ErrorResponse, "description": "One or more files are not JPEG, PNG, or GIF."},
    429: {"model": ErrorResponse, "description": "More than 4 batch requests per minute."},
    422: {"model": ErrorResponse, "description": "Missing `images` form field or Idempotency-Key."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Could not create the job."},
}

JOB_STATUS_RESPONSES = {
    200: {"model": JobStatusResponse, "description": "Current job status."},
    404: {"model": ErrorResponse, "description": "Unknown job_id."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Could not load the job."},
}
