from __future__ import annotations

import chromadb
import pytest

from embedded_copilot.knowledge.models import DocumentMetadata
from embedded_copilot.rag.embedding import HashEmbedding
from embedded_copilot.rag.hybrid_retriever import HybridRetriever
from embedded_copilot.rag.index import index_chunks
from embedded_copilot.rag.loader import LoadedDocument
from embedded_copilot.rag.metadata_filter import GENERIC_CHIP
from embedded_copilot.rag.retriever import ChromaRetriever
from embedded_copilot.rag.splitter import split_documents


def _document(
    *,
    text: str,
    source: str,
    metadata: DocumentMetadata,
) -> LoadedDocument:
    return LoadedDocument(
        text=text,
        source=source,
        filename=source.rsplit("/", maxsplit=1)[-1],
        page=None,
        checksum=f"checksum-{source}",
        metadata=metadata,
    )


def _collection(name: str):
    return chromadb.EphemeralClient().get_or_create_collection(
        name,
        metadata={"hnsw:space": "cosine"},
    )


def test_metadata_change_updates_in_place_and_remains_idempotent() -> None:
    collection = _collection("phase2_metadata_update")
    embedding = HashEmbedding(dimension=64)
    original = _document(
        text="ESP32-S3 SPI transfer guidance.",
        source="esp32/spi.md",
        metadata=DocumentMetadata(chip="ESP32-S3", chapter="SPI"),
    )
    changed = _document(
        text=original.text,
        source=original.source,
        metadata=DocumentMetadata(chip="ESP32-S3", chapter="SPI DMA"),
    )
    original_chunks = split_documents([original], chunk_size=200, chunk_overlap=20)
    changed_chunks = split_documents([changed], chunk_size=200, chunk_overlap=20)

    first = index_chunks(original_chunks, collection, embedding)
    second = index_chunks(changed_chunks, collection, embedding)
    third = index_chunks(changed_chunks, collection, embedding)

    assert original_chunks[0].metadata.chapter == "SPI"
    assert changed_chunks[0].metadata.chapter == "SPI DMA"
    assert first.inserted == 1
    assert second.updated == 1
    assert third.unchanged == 1
    assert collection.count() == 1
    stored = collection.get(include=["metadatas"])["metadatas"][0]
    assert stored["chapter"] == "SPI DMA"
    assert stored["chip"] == "ESP32-S3"


def test_index_flattens_metadata_and_marks_generic_documents() -> None:
    collection = _collection("phase2_flat_metadata")
    embedding = HashEmbedding(dimension=64)
    document = _document(
        text="SPI is a synchronous serial protocol.",
        source="protocols/spi.md",
        metadata=DocumentMetadata(
            category="protocol",
            chapter="SPI",
            page=7,
            document_type="protocol",
        ),
    )

    index_chunks(
        split_documents([document], chunk_size=200, chunk_overlap=20),
        collection,
        embedding,
    )

    stored = collection.get(include=["metadatas"])["metadatas"][0]
    assert stored["chip"] == GENERIC_CHIP
    assert stored["category"] == "protocol"
    assert stored["chapter"] == "SPI"
    assert stored["page"] == 7
    assert all(not isinstance(value, dict) for value in stored.values())


def test_hybrid_retriever_excludes_other_chips_and_keeps_generic() -> None:
    collection = _collection("phase2_chip_filter")
    embedding = HashEmbedding(dimension=64)
    documents = [
        _document(
            text="ESP32-S3 SPI DMA transfer.",
            source="esp32_s3_spi.md",
            metadata=DocumentMetadata(chip="ESP32-S3", chapter="SPI"),
        ),
        _document(
            text="STM32F103 SPI DMA transfer.",
            source="stm32f103_spi.md",
            metadata=DocumentMetadata(chip="STM32F103", chapter="SPI"),
        ),
        _document(
            text="Generic SPI transfer framing.",
            source="protocols/spi.md",
            metadata=DocumentMetadata(category="protocol", chapter="SPI"),
        ),
    ]
    index_chunks(
        split_documents(documents, chunk_size=200, chunk_overlap=20),
        collection,
        embedding,
    )
    retriever = HybridRetriever(
        retriever=ChromaRetriever(collection=collection, embedding=embedding)
    )

    results = retriever.retrieve("ESP32-S3 SPI", top_k=3, score_threshold=0.0)

    sources = [result.citation.source for result in results]
    assert sources[0] == "esp32_s3_spi.md"
    assert "protocols/spi.md" in sources
    assert "stm32f103_spi.md" not in sources
    assert results[0].metadata.chip == "ESP32-S3"


def test_exact_chip_always_precedes_multi_entity_generic_document() -> None:
    collection = _collection("phase2_exact_chip_tier")
    embedding = HashEmbedding(dimension=64)
    documents = [
        _document(
            text="Target-specific peripheral guidance.",
            source="esp32_s3.md",
            metadata=DocumentMetadata(chip="ESP32-S3"),
        ),
        _document(
            text="Generic SPI ESP-IDF DMA guidance.",
            source="generic.md",
            metadata=DocumentMetadata(
                chapter="SPI",
                document_type="esp_idf",
            ),
        ),
    ]
    index_chunks(
        split_documents(documents, chunk_size=200, chunk_overlap=20),
        collection,
        embedding,
    )
    vector_retriever = ChromaRetriever(collection=collection, embedding=embedding)
    query = "ESP32-S3 SPI ESP-IDF DMA"
    before = vector_retriever.retrieve_filtered(
        query,
        top_k=6,
        score_threshold=0.0,
        metadata_filter={
            "$or": [
                {"chip": "ESP32-S3"},
                {"chip": GENERIC_CHIP},
            ]
        },
    )

    results = HybridRetriever(retriever=vector_retriever).retrieve(
        query,
        top_k=2,
        score_threshold=0.0,
    )

    assert results[0].citation.source == "esp32_s3.md"
    assert {item.chunk_id: item.citation.score for item in results} == {
        item.chunk_id: item.citation.score for item in before
    }


@pytest.mark.parametrize(
    ("query", "matching_source"),
    [("SPI", "chapter-match.md"), ("ESP-IDF", "framework-match.md")],
)
def test_hybrid_retriever_reranks_metadata_matches(
    query: str,
    matching_source: str,
) -> None:
    collection = _collection(f"phase2_rerank_{query.replace('-', '_')}")
    embedding = HashEmbedding(dimension=64)
    documents = [
        _document(
            text="Peripheral transfer guidance.",
            source="chapter-match.md",
            metadata=DocumentMetadata(chapter="SPI"),
        ),
        _document(
            text="Framework driver guidance.",
            source="framework-match.md",
            metadata=DocumentMetadata(document_type="esp_idf"),
        ),
        _document(
            text=f"Repeated lexical match {query} {query}.",
            source="vector-match.md",
            metadata=DocumentMetadata(chapter="UART", document_type="reference"),
        ),
    ]
    index_chunks(
        split_documents(documents, chunk_size=200, chunk_overlap=20),
        collection,
        embedding,
    )
    retriever = HybridRetriever(
        retriever=ChromaRetriever(collection=collection, embedding=embedding)
    )

    results = retriever.retrieve(query, top_k=3, score_threshold=0.0)

    assert results[0].citation.source == matching_source
    assert 0.0 <= results[0].citation.score <= 1.0
