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
