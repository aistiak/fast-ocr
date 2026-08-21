import logging

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPIError
from google.cloud import vision

from app.core.config import settings
from app.domain.errors import OcrError
from app.helpers.text import clean_text

logger = logging.getLogger(__name__)

_client: vision.ImageAnnotatorClient | None = None


def _client_for_project() -> vision.ImageAnnotatorClient:
    global _client
    if _client is None:
        client_options = None
        if settings.google_cloud_project:
            client_options = ClientOptions(quota_project_id=settings.google_cloud_project)
        _client = vision.ImageAnnotatorClient(client_options=client_options)
    return _client


def _mean_confidence(annotation: vision.TextAnnotation) -> float:
    word_scores: list[float] = []
    for page in annotation.pages:
        if page.confidence:
            word_scores.append(page.confidence)
            continue
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    if word.confidence:
                        word_scores.append(word.confidence)
    if not word_scores:
        return 0.0
    return round(sum(word_scores) / len(word_scores), 4)


def extract_text(image_bytes: bytes) -> tuple[str, float]:
    logger.info("VisionService document_text_detection")
    image = vision.Image(content=image_bytes)
    try:
        response = _client_for_project().document_text_detection(image=image)
    except GoogleAPIError as exc:
        raise OcrError(str(exc)) from exc

    if response.error.message:
        raise OcrError(response.error.message)

    annotation = response.full_text_annotation
    text = (annotation.text or "").strip()
    if not text:
        return "", 0.0
    return clean_text(text), _mean_confidence(annotation)
