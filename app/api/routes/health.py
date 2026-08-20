from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "message": "fast-ocr is running",
    }


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}
