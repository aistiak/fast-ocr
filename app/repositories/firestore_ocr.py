from __future__ import annotations

import asyncio
from typing import Any

from google.cloud import firestore

from app.core.config import settings

_client: firestore.Client | None = None


def _client_for_project() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=settings.google_cloud_project)
    return _client


class FirestoreOcrResultRepository:
    def __init__(self, collection: str | None = None) -> None:
        self._collection_name = collection or settings.firestore_collection

    def _document(self, image_hash: str) -> firestore.DocumentReference:
        return _client_for_project().collection(self._collection_name).document(image_hash)

    def _get_sync(self, image_hash: str) -> dict[str, Any] | None:
        snapshot = self._document(image_hash).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        text = data.get("text")
        confidence = data.get("confidence")
        metadata = data.get("metadata")
        if not isinstance(text, str) or not isinstance(confidence, (int, float)):
            return None
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "text": text,
            "confidence": float(confidence),
            "metadata": metadata,
        }

    def _save_sync(
        self,
        image_hash: str,
        *,
        text: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> None:
        self._document(image_hash).set(
            {
                "text": text,
                "confidence": confidence,
                "metadata": metadata,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    async def get(self, image_hash: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_sync, image_hash)

    async def save(
        self,
        image_hash: str,
        *,
        text: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> None:
        await asyncio.to_thread(
            self._save_sync,
            image_hash,
            text=text,
            confidence=confidence,
            metadata=metadata,
        )
