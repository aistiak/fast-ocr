from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import Any

from google.cloud import firestore

from app.core.config import settings

_client: firestore.Client | None = None


def _client_for_project() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=settings.google_cloud_project)
    return _client


def _idempotency_document_id(idempotency_key: str) -> str:
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()


class FirestoreJobRepository:
    def __init__(
        self,
        collection: str | None = None,
        idempotency_collection: str | None = None,
    ) -> None:
        self._collection_name = collection or settings.firestore_jobs_collection
        self._idempotency_collection = (
            idempotency_collection or settings.firestore_idempotency_collection
        )

    def _document(self, job_id: str) -> firestore.DocumentReference:
        return _client_for_project().collection(self._collection_name).document(job_id)

    def _idempotency_document(self, idempotency_key: str) -> firestore.DocumentReference:
        return (
            _client_for_project()
            .collection(self._idempotency_collection)
            .document(_idempotency_document_id(idempotency_key))
        )

    def _job_payload(self, *, idempotency_key: str) -> dict[str, Any]:
        return {
            "status": "processing",
            "success_count": 0,
            "failure_count": 0,
            "error": None,
            "result": None,
            "idempotency_key": idempotency_key,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

    def _begin_sync(self, idempotency_key: str) -> dict[str, Any]:
        client = _client_for_project()
        key_ref = self._idempotency_document(idempotency_key)
        transaction = client.transaction()

        @firestore.transactional
        def _create(transaction: firestore.Transaction) -> dict[str, Any]:
            snapshot = key_ref.get(transaction=transaction)
            if snapshot.exists:
                data = snapshot.to_dict() or {}
                existing_job_id = data.get("job_id")
                if not isinstance(existing_job_id, str) or not existing_job_id:
                    raise ValueError("Invalid idempotency record.")
                job_snapshot = self._document(existing_job_id).get(transaction=transaction)
                status = "processing"
                if job_snapshot.exists:
                    job_data = job_snapshot.to_dict() or {}
                    job_status = job_data.get("status")
                    if job_status in {"processing", "success", "failed"}:
                        status = job_status
                return {"job_id": existing_job_id, "created": False, "status": status}

            job_id = str(uuid.uuid4())
            transaction.set(
                key_ref,
                {
                    "key": idempotency_key,
                    "job_id": job_id,
                    "created_at": firestore.SERVER_TIMESTAMP,
                },
            )
            transaction.set(self._document(job_id), self._job_payload(idempotency_key=idempotency_key))
            return {"job_id": job_id, "created": True, "status": "processing"}

        return _create(transaction)

    def _get_sync(self, job_id: str) -> dict[str, Any] | None:
        snapshot = self._document(job_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        status = data.get("status")
        if status not in {"processing", "success", "failed"}:
            return None
        result = data.get("result")
        if result is not None and not isinstance(result, list):
            result = None
        return {
            "status": status,
            "success_count": int(data.get("success_count") or 0),
            "failure_count": int(data.get("failure_count") or 0),
            "error": data.get("error"),
            "result": result,
        }

    def _complete_sync(
        self,
        job_id: str,
        *,
        status: str,
        success_count: int,
        failure_count: int,
        result: list[dict[str, Any]],
        error: str | None,
    ) -> None:
        self._document(job_id).update(
            {
                "status": status,
                "success_count": success_count,
                "failure_count": failure_count,
                "error": error,
                "result": result,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

    async def begin(self, idempotency_key: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._begin_sync, idempotency_key)

    async def get(self, job_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_sync, job_id)

    async def complete(
        self,
        job_id: str,
        *,
        status: str,
        success_count: int,
        failure_count: int,
        result: list[dict[str, Any]],
        error: str | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._complete_sync,
            job_id,
            status=status,
            success_count=success_count,
            failure_count=failure_count,
            result=result,
            error=error,
        )
