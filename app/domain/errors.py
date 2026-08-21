from typing import Any


class OcrError(Exception):
    def __init__(self, message: str = "", *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}
