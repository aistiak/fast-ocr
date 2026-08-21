from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.controllers.ocr_controller import extract_text
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
