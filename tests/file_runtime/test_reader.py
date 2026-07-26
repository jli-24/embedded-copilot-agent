from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from embedded_copilot.file_runtime import (
    DocumentSummary,
    FileReference,
    FileReferenceConflict,
    FileReferenceNotFound,
    FileReferenceRequest,
    FileRuntimeUnavailable,
    FileType,
)
from embedded_copilot.file_runtime.reader.resolver import RootedFileResolver
from embedded_copilot.file_runtime.reader.stream import SecureFileReader


class _Catalog:
    def __init__(self, reference: FileReference) -> None:
        self._reference = reference

    def resolve(self, session_id: str, file_id: str) -> FileReference | None:
        if (
            session_id.casefold() != self._reference.session_id.casefold()
            or file_id.casefold() != self._reference.file_id.casefold()
        ):
            return None
        return self._reference.model_copy(deep=True)


class _Extractor:
    def __init__(self, *, fail: bool = False) -> None:
        self.stream: io.BufferedReader | None = None
        self.fail = fail

    def extract(
        self,
        stream: io.BufferedReader,
        *,
        reference: FileReference,
    ) -> DocumentSummary:
        self.stream = stream
        assert stream.read() == b"line one\nline two\n"
        if self.fail:
            raise RuntimeError(
                r"C:\workspace\private\main.py must never escape the runtime"
            )
        return DocumentSummary(
            file_id=reference.file_id,
            document_type=reference.document_type,
            line_count=2,
            character_count=18,
        )


def _request(
    *,
    session_id: str = "session:1",
    file_type: FileType = FileType.UNKNOWN,
) -> FileReferenceRequest:
    return FileReferenceRequest(
        session_id=session_id,
        file_id="file:1",
        file_type=file_type,
        instruction_summary="Inspect the referenced file structure.",
    )


def _reference(
    path: Path,
    *,
    size_bytes: int | None = None,
    document_type: FileType = FileType.SOURCE_CODE,
) -> FileReference:
    return FileReference(
        session_id="session:1",
        file_id="file:1",
        basename=path.name,
        document_type=document_type,
        size_bytes=path.stat().st_size if size_bytes is None else size_bytes,
        relative_path=path.name,
    )


def test_reader_closes_request_scoped_stream_after_extraction(
    tmp_path: Path,
) -> None:
    source = tmp_path / "main.py"
    source.write_bytes(b"line one\nline two\n")
    extractor = _Extractor()
    reader = SecureFileReader(
        RootedFileResolver(tmp_path, _Catalog(_reference(source))),
        max_size_bytes=1024,
    )

    summary = reader.extract(_request(), extractor)

    assert summary == DocumentSummary(
        file_id="file:1",
        document_type=FileType.SOURCE_CODE,
        line_count=2,
        character_count=18,
    )
    assert extractor.stream is not None
    assert extractor.stream.closed


def test_reader_closes_stream_and_redacts_extractor_failure(tmp_path: Path) -> None:
    source = tmp_path / "main.py"
    source.write_bytes(b"line one\nline two\n")
    extractor = _Extractor(fail=True)
    reader = SecureFileReader(
        RootedFileResolver(tmp_path, _Catalog(_reference(source)))
    )

    with pytest.raises(FileRuntimeUnavailable) as raised:
        reader.extract(_request(), extractor)

    assert str(raised.value) == "file_unavailable"
    assert repr(raised.value) == "FileRuntimeUnavailable()"
    assert "workspace" not in str(raised.value)
    assert extractor.stream is not None
    assert extractor.stream.closed


def test_reader_rejects_cross_session_and_size_conflicts(tmp_path: Path) -> None:
    source = tmp_path / "main.py"
    source.write_bytes(b"line one\nline two\n")
    reader = SecureFileReader(
        RootedFileResolver(
            tmp_path,
            _Catalog(_reference(source, size_bytes=source.stat().st_size + 1)),
        )
    )

    with pytest.raises(FileReferenceNotFound):
        reader.extract(_request(session_id="session:2"), _Extractor())
    with pytest.raises(FileReferenceConflict):
        reader.extract(_request(), _Extractor())


@pytest.mark.parametrize(
    "relative_path",
    (
        "../private.py",
        "nested/../../private.py",
        "C:/private.py",
        r"\\server\share\private.py",
        "/private.py",
    ),
)
def test_file_reference_rejects_unsafe_relative_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    source = tmp_path / "main.py"
    source.write_bytes(b"line one\nline two\n")

    with pytest.raises(ValueError):
        FileReference(
            session_id="session:1",
            file_id="file:1",
            basename=source.name,
            document_type=FileType.SOURCE_CODE,
            size_bytes=source.stat().st_size,
            relative_path=relative_path,
        )


def test_reader_rejects_symlink_escape(tmp_path: Path) -> None:
    real = tmp_path / "real.py"
    real.write_bytes(b"line one\nline two\n")
    link = tmp_path / "main.py"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    reader = SecureFileReader(RootedFileResolver(tmp_path, _Catalog(_reference(link))))

    with pytest.raises(FileReferenceConflict):
        reader.extract(_request(), _Extractor())


def test_reader_rejects_mismatched_document_type(tmp_path: Path) -> None:
    source = tmp_path / "main.py"
    source.write_bytes(b"line one\nline two\n")
    reader = SecureFileReader(
        RootedFileResolver(
            tmp_path,
            _Catalog(_reference(source, document_type=FileType.TEXT)),
        )
    )

    with pytest.raises(FileReferenceConflict):
        reader.extract(_request(), _Extractor())


def test_reader_accepts_windows_ctime_settling_at_descriptor_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import embedded_copilot.file_runtime.reader.resolver as resolver_module

    source = tmp_path / "main.py"
    source.write_bytes(b"line one\nline two\n")
    original_snapshot = resolver_module._file_snapshot
    calls = 0

    def settling_snapshot(value: os.stat_result):
        nonlocal calls
        calls += 1
        snapshot = original_snapshot(value)
        if calls in {3, 4}:
            return (*snapshot[:-1], snapshot[-1] - 1)
        return snapshot

    monkeypatch.setattr(resolver_module, "_file_snapshot", settling_snapshot)
    reader = SecureFileReader(
        RootedFileResolver(tmp_path, _Catalog(_reference(source)))
    )

    summary = reader.extract(_request(), _Extractor())

    assert summary.file_id == "file:1"


def test_resolver_rejects_leaf_descriptor_from_replaced_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    original_parent = root / "nested"
    original_parent.mkdir(parents=True)
    original = original_parent / "main.py"
    original.write_bytes(b"line one\nline two\n")
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"line one\nline two\n")
    reference = FileReference(
        session_id="session:1",
        file_id="file:1",
        basename="main.py",
        document_type=FileType.SOURCE_CODE,
        size_bytes=original.stat().st_size,
        relative_path=Path("nested/main.py"),
    )
    resolver = RootedFileResolver(root, _Catalog(reference))
    real_open = os.open

    class _SubstitutingOpenResolver:
        def resolve(self, request: FileReferenceRequest):
            with monkeypatch.context() as context:
                context.setattr(
                    os,
                    "open",
                    lambda path, flags: real_open(outside, flags),
                )
                return resolver.resolve(request)

    reader = SecureFileReader(_SubstitutingOpenResolver())

    with pytest.raises(FileReferenceConflict):
        reader.extract(_request(), _Extractor())
