from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from chromadb.api.models.Collection import Collection

from embedded_copilot.rag.embedding import EmbeddingProvider
from embedded_copilot.rag.splitter import DocumentChunk


@dataclass(frozen=True, slots=True)
class IngestionReport:
    inserted: int
    updated: int
    unchanged: int
    deleted: int = 0


def _metadata(chunk: DocumentChunk) -> dict[str, str | int]:
    metadata: dict[str, str | int] = {
        "source": chunk.source,
        "filename": chunk.filename,
        "chunk_index": chunk.chunk_index,
        "content_hash": chunk.content_hash,
        "source_checksum": chunk.source_checksum,
    }
    if chunk.page is not None:
        metadata["page"] = chunk.page
    if chunk.section is not None:
        metadata["section"] = chunk.section
    return metadata


def index_chunks(
    chunks: Sequence[DocumentChunk],
    collection: Collection,
    embedding: EmbeddingProvider,
    *,
    active_sources: Sequence[str] | None = None,
) -> IngestionReport:
    if not chunks and active_sources is None:
        return IngestionReport(inserted=0, updated=0, unchanged=0, deleted=0)

    ids = [chunk.chunk_id for chunk in chunks]
    existing: dict[str, dict[str, Any]] = {}
    existing_result = (
        collection.get(ids=ids, include=["metadatas"])
        if ids
        else {"ids": [], "metadatas": []}
    )
    for item_id, metadata in zip(
        existing_result.get("ids", []),
        existing_result.get("metadatas", []),
        strict=True,
    ):
        existing[item_id] = metadata or {}

    existing_all = collection.get(include=["metadatas"])
    existing_metadata = {
        item_id: metadata or {}
        for item_id, metadata in zip(
            existing_all.get("ids", []),
            existing_all.get("metadatas", []),
            strict=True,
        )
    }
    incoming_ids = set(ids)
    incoming_sources = {chunk.source for chunk in chunks}
    source_scope = (
        set(active_sources) if active_sources is not None else incoming_sources
    )
    if active_sources is not None:
        stale_ids = [
            item_id
            for item_id, metadata in existing_metadata.items()
            if (
                metadata.get("source") not in source_scope
                or item_id not in incoming_ids
            )
        ]
    else:
        stale_ids = [
            item_id
            for item_id, metadata in existing_metadata.items()
            if metadata.get("source") in source_scope and item_id not in incoming_ids
        ]
    if stale_ids:
        collection.delete(ids=stale_ids)

    changed = [
        chunk
        for chunk in chunks
        if existing.get(chunk.chunk_id, {}).get("content_hash") != chunk.content_hash
    ]
    inserted = sum(chunk.chunk_id not in existing for chunk in changed)
    updated = len(changed) - inserted
    unchanged = len(chunks) - len(changed)

    if changed:
        collection.upsert(
            ids=[chunk.chunk_id for chunk in changed],
            documents=[chunk.text for chunk in changed],
            metadatas=[_metadata(chunk) for chunk in changed],
            embeddings=embedding.embed_documents([chunk.text for chunk in changed]),
        )
    return IngestionReport(
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        deleted=len(stale_ids),
    )
