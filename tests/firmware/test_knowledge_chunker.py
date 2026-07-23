import pytest

from embedded_copilot.firmware.knowledge.chunker import FirmwareChunker
from embedded_copilot.firmware.knowledge.models import FirmwareDocument


def _document() -> FirmwareDocument:
    return FirmwareDocument(
        id="source-1",
        title="SPI Guide",
        platform="STM32",
        framework="HAL",
        content="alpha beta gamma delta epsilon zeta eta theta",
        metadata={"source": "stm32/spi.md", "license": "test"},
    )


def test_chunker_preserves_provenance_and_stable_ids() -> None:
    chunker = FirmwareChunker(chunk_size=20, chunk_overlap=5)

    first = chunker.chunk([_document()])
    second = chunker.chunk([_document()])

    assert len(first) > 1
    assert [item.id for item in first] == [item.id for item in second]
    assert all(item.platform == "STM32" for item in first)
    assert first[0].metadata["source_document_id"] == "source-1"
    assert first[0].metadata["source"] == "stm32/spi.md"
    assert [item.metadata["chunk_index"] for item in first] == list(range(len(first)))


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_chunker_rejects_invalid_windows(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        FirmwareChunker(chunk_size=chunk_size, chunk_overlap=overlap)
