import re

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPIError
from google.cloud import vision

from app.core.config import settings


class OcrError(Exception):
    pass


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


_SENTENCE_END = frozenset(".!?")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return ""

    paragraphs = [lines[0]]
    for line in lines[1:]:
        previous = paragraphs[-1]
        if previous[-1] in _SENTENCE_END:
            paragraphs.append(line)
        else:
            paragraphs[-1] = f"{previous} {line}"
    return "\n\n".join(paragraphs)


def extract_text(image_bytes: bytes) -> tuple[str, float]:
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
