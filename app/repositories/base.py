from typing import Any, Protocol


class OcrResultRepository(Protocol):
    """Persistence for OCR results. Unused until a database is added."""

    async def save(
        self,
        *,
        text: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> None: ...
