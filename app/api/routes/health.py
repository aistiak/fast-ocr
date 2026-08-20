from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(tags=["health"])


class RootResponse(BaseModel):
    service: str
    status: str
    message: str


class PingResponse(BaseModel):
    message: str = Field(examples=["pong"])


@router.get(
    "/",
    response_model=RootResponse,
    summary="Service info",
)
def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        status="ok",
        message="fast-ocr is running",
    )


@router.get(
    "/ping",
    response_model=PingResponse,
    summary="Ping",
)
def ping() -> PingResponse:
    return PingResponse(message="pong")
