from typing import Any, Protocol


class OcrResultRepository(Protocol):
    async def get(self, image_hash: str) -> dict[str, Any] | None: ...

    async def save(
        self,
        image_hash: str,
        *,
        text: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> None: ...


class JobRepository(Protocol):
    async def begin(
        self,
        idempotency_key: str,
    ) -> dict[str, Any]: ...

    async def get(self, job_id: str) -> dict[str, Any] | None: ...

    async def complete(
        self,
        job_id: str,
        *,
        status: str,
        success_count: int,
        failure_count: int,
        result: list[dict[str, Any]],
        error: str | None = None,
    ) -> None: ...
