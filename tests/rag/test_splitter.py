from __future__ import annotations

from embedded_copilot.rag.loader import LoadedDocument
from embedded_copilot.rag.splitter import split_documents


def test_splitter_preserves_technical_tokens_and_stable_ids() -> None:
    document = LoadedDocument(
        text=(
            "# SPI configuration\n\n"
            "Use SPI2_HOST with clock_hz=10_000_000.\n\n"
            "A fault address such as 0x400D1234 must stay intact."
        ),
        source="knowledge/manual.md",
        filename="manual.md",
        page=None,
        checksum="source-checksum",
    )

    first = split_documents([document], chunk_size=70, chunk_overlap=10)
    second = split_documents([document], chunk_size=70, chunk_overlap=10)
    combined = "\n".join(chunk.text for chunk in first)

    assert "SPI2_HOST" in combined
    assert "0x400D1234" in combined
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.chunk_index for chunk in first] == list(range(len(first)))


def test_splitter_rejects_invalid_overlap() -> None:
    document = LoadedDocument(
        text="SPI",
        source="spi.md",
        filename="spi.md",
        page=None,
        checksum="checksum",
    )

    try:
        split_documents([document], chunk_size=20, chunk_overlap=20)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected invalid overlap to fail")
