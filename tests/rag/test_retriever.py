from __future__ import annotations

import chromadb

from embedded_copilot.rag.embedding import HashEmbedding
from embedded_copilot.rag.index import index_chunks
from embedded_copilot.rag.loader import LoadedDocument
from embedded_copilot.rag.retriever import ChromaRetriever
from embedded_copilot.rag.splitter import split_documents


def _chunks():
    documents = [
        LoadedDocument(
            text="ESP32 SPI configuration uses SCLK, MOSI, MISO and chip select.",
            source="knowledge/embedded_basics.md",
            filename="embedded_basics.md",
            page=None,
            checksum="checksum-1",
        ),
        LoadedDocument(
            text="A Guru Meditation Backtrace is observable debug evidence.",
            source="knowledge/debug_basics.md",
            filename="debug_basics.md",
            page=None,
            checksum="checksum-2",
        ),
    ]
    return split_documents(documents, chunk_size=200, chunk_overlap=20)


def test_indexing_is_idempotent() -> None:
    collection = chromadb.EphemeralClient().get_or_create_collection(
        "test_indexing",
        metadata={"hnsw:space": "cosine"},
    )
    embedding = HashEmbedding(dimension=64)
    chunks = _chunks()

    first = index_chunks(chunks, collection, embedding)
    second = index_chunks(chunks, collection, embedding)

    assert first.inserted == len(chunks)
    assert first.unchanged == 0
    assert second.inserted == 0
    assert second.unchanged == len(chunks)
    assert collection.count() == len(chunks)


def test_indexing_removes_stale_chunks_when_source_shrinks() -> None:
    collection = chromadb.EphemeralClient().get_or_create_collection(
        "test_source_shrink",
        metadata={"hnsw:space": "cosine"},
    )
    embedding = HashEmbedding(dimension=64)
    long_document = LoadedDocument(
        text=" ".join(["ESP32 SPI register configuration"] * 20),
        source="spi.md",
        filename="spi.md",
        page=None,
        checksum="long-checksum",
    )
    short_document = LoadedDocument(
        text="ESP32 SPI mode.",
        source="spi.md",
        filename="spi.md",
        page=None,
        checksum="short-checksum",
    )
    long_chunks = split_documents([long_document], chunk_size=100, chunk_overlap=10)
    short_chunks = split_documents([short_document], chunk_size=100, chunk_overlap=10)

    index_chunks(long_chunks, collection, embedding)
    report = index_chunks(short_chunks, collection, embedding)

    assert len(long_chunks) > len(short_chunks)
    assert report.deleted == len(long_chunks) - len(short_chunks)
    assert collection.count() == len(short_chunks)
    assert collection.get()["ids"] == [short_chunks[0].chunk_id]


def test_indexing_removes_chunks_for_deleted_sources() -> None:
    collection = chromadb.EphemeralClient().get_or_create_collection(
        "test_source_delete",
        metadata={"hnsw:space": "cosine"},
    )
    embedding = HashEmbedding(dimension=64)
    chunks = _chunks()
    active_chunks = [chunk for chunk in chunks if chunk.source.endswith("embedded_basics.md")]
    index_chunks(chunks, collection, embedding)

    report = index_chunks(
        active_chunks,
        collection,
        embedding,
        active_sources={"knowledge/embedded_basics.md"},
    )

    assert report.deleted == len(chunks) - len(active_chunks)
    assert collection.count() == len(active_chunks)
    assert {
        metadata["source"]
        for metadata in collection.get(include=["metadatas"])["metadatas"]
    } == {"knowledge/embedded_basics.md"}


def test_retriever_returns_citations_and_filters_low_scores() -> None:
    collection = chromadb.EphemeralClient().get_or_create_collection(
        "test_retrieval",
        metadata={"hnsw:space": "cosine"},
    )
    embedding = HashEmbedding(dimension=64)
    index_chunks(_chunks(), collection, embedding)
    retriever = ChromaRetriever(collection=collection, embedding=embedding)

    results = retriever.retrieve("ESP32 SPI", top_k=2, score_threshold=0.05)
    empty = retriever.retrieve(
        "completely unrelated cooking recipe",
        top_k=2,
        score_threshold=0.95,
    )

    assert results
    assert results[0].citation.filename == "embedded_basics.md"
    assert results[0].citation.chunk_id == results[0].chunk_id
    assert results[0].citation.score >= 0.05
    assert empty == []
