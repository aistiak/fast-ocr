from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(description="Machine-readable code.")
    message: str = Field(description="Human-readable explanation.")


def error_payload(error: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"error": error, "message": message}
    body.update(extra)
    return body
