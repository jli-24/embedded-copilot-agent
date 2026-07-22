from __future__ import annotations

from dataclasses import dataclass

from chromadb.api.models.Collection import Collection

from embedded_copilot.rag.embedding import EmbeddingProvider
from embedded_copilot.schemas.result import SourceCitation


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    citation: SourceCitation


class ChromaRetriever:
    def __init__(
        self,
        *,
        collection: Collection,
        embedding: EmbeddingProvider,
    ) -> None:
        self._collection = collection
        self._embedding = embedding

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        if not query.strip() or self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[self._embedding.embed_query(query)],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        retrieved: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=True,
        ):
            score = max(0.0, min(1.0, 1.0 - float(distance)))
            if score < score_threshold:
                continue
            source_metadata = metadata or {}
            citation = SourceCitation(
                source=str(source_metadata["source"]),
                filename=str(source_metadata["filename"]),
                page=source_metadata.get("page"),
                chunk_id=chunk_id,
                score=score,
            )
            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=text or "",
                    citation=citation,
                )
            )
        return retrieved
