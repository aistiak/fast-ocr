from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    400: {"description": "No files, more than 5 files, or missing/invalid Idempotency-Key."},
    413: {"description": "One or more files are larger than 10MB."},
    429: {"description": "More than 4 batch requests per minute."},
    503: {"description": "Could not create the job."},
}

JOB_STATUS_RESPONSES = {
    200: {"model": JobStatusResponse, "description": "Current job status."},
    404: {"description": "Unknown job_id."},
}
