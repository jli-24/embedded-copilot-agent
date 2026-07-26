from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from embedded_copilot.file_intelligence.extractor import (
    TemporaryFileSummary,
)
from embedded_copilot.file_intelligence.reader import (
    FileReadRejected,
    SecureFileReader,
)
from embedded_copilot.file_intelligence.security import (
    RootedReferenceResolver,
)
from embedded_copilot.multimodal.context import AttachmentBinding
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)

CREATED = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)


def _binding(path: Path, *, size_bytes: int | None = None) -> AttachmentBinding:
    return AttachmentBinding(
        session_id="session:1",
        input=MultimodalInput(
            type=MultimodalInputType.FILE,
            reference_id="file:1",
            summary="Referenced PDF metadata.",
        ),
        basename=path.name,
        size_bytes=path.stat().st_size if size_bytes is None else size_bytes,
        created_at=CREATED,
    )


@pytest.mark.parametrize(
    "configured_path",
    (
        "../private.pdf",
        "nested/../../private.pdf",
        "C:/private/file.pdf",
        "/private/file.pdf",
    ),
)
def test_rooted_resolver_rejects_absolute_and_traversal_paths(
    tmp_path: Path,
    configured_path: str,
) -> None:
    with pytest.raises(ValueError, match="resolver"):
        RootedReferenceResolver(tmp_path, {"file:1": configured_path})


def test_secure_reader_rejects_size_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "reference.pdf"
    source.write_bytes(b"safe fixture")
    reader = SecureFileReader(
        RootedReferenceResolver(tmp_path, {"file:1": source.name})
    )

    with pytest.raises(FileReadRejected, match="validation failed"):
        reader.extract(
            _binding(source, size_bytes=source.stat().st_size + 1), _Extractor()
        )


def test_secure_reader_closes_request_scoped_stream(tmp_path: Path) -> None:
    source = tmp_path / "reference.pdf"
    source.write_bytes(b"safe fixture")
    extractor = _Extractor()
    reader = SecureFileReader(
        RootedReferenceResolver(tmp_path, {"file:1": source.name})
    )

    summary = reader.extract(_binding(source), extractor)

    assert summary == TemporaryFileSummary(
        reference_id="file:1",
        summary="Temporary PDF summary.",
        metadata={"page_count": 1},
    )
    assert extractor.stream is not None
    assert extractor.stream.closed
    assert "content" not in summary.model_dump(mode="json")
    assert "bytes" not in summary.model_dump(mode="json")


def test_secure_reader_rejects_symlink(tmp_path: Path) -> None:
    source = tmp_path / "real.pdf"
    source.write_bytes(b"safe fixture")
    link = tmp_path / "reference.pdf"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    reader = SecureFileReader(RootedReferenceResolver(tmp_path, {"file:1": link.name}))

    with pytest.raises(FileReadRejected, match="validation failed"):
        reader.extract(_binding(link), _Extractor())


class _Extractor:
    def __init__(self) -> None:
        self.stream: io.BufferedReader | None = None

    def extract(
        self,
        stream: io.BufferedReader,
        *,
        binding: AttachmentBinding,
    ) -> TemporaryFileSummary:
        self.stream = stream
        assert stream.read() == b"safe fixture"
        return TemporaryFileSummary(
            reference_id=binding.input.reference_id,
            summary="Temporary PDF summary.",
            metadata={"page_count": 1},
        )
