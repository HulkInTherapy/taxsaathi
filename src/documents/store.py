"""
In-memory store for documents uploaded during one task.

Safety boundary from the plan: uploaded documents are processed in memory and deleted after
the session. Nothing here touches the disk; `clear()` is called when the task ends.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass

MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
ALLOWED_TYPES = {".pdf"}


@dataclass
class StoredDocument:
    id: str
    filename: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


class DocumentStore:
    def __init__(self):
        self._docs: dict[str, StoredDocument] = {}
        self._lock = threading.Lock()

    def add(self, filename: str, data: bytes) -> str:
        ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        if ext not in ALLOWED_TYPES:
            raise ValueError(f"only {', '.join(sorted(ALLOWED_TYPES))} files are accepted")
        if len(data) > MAX_BYTES:
            raise ValueError(f"file is larger than {MAX_BYTES // (1024 * 1024)} MB")
        if not data:
            raise ValueError("file is empty")
        doc_id = "doc_" + hashlib.sha1(data).hexdigest()[:10]
        with self._lock:
            self._docs[doc_id] = StoredDocument(doc_id, filename, data)
        return doc_id

    def get(self, doc_id: str) -> StoredDocument:
        with self._lock:
            if doc_id not in self._docs:
                raise KeyError(f"no uploaded document with id {doc_id!r}; available: {sorted(self._docs)}")
            return self._docs[doc_id]

    def list(self) -> list[dict]:
        with self._lock:
            return [{"id": d.id, "filename": d.filename, "size": d.size} for d in self._docs.values()]

    def delete(self, doc_id: str) -> None:
        with self._lock:
            self._docs.pop(doc_id, None)

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()

    def __len__(self) -> int:
        return len(self._docs)
