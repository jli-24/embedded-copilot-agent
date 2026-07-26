from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from embedded_copilot.file_runtime import (
    FileReference,
    FileReferenceRequest,
    FileRuntimeUnavailable,
    FileType,
    create_file_runtime,
)
from embedded_copilot.services.config import Settings


class _Catalog:
    def __init__(self, reference: FileReference | None) -> None:
        self._reference = reference

    def resolve(self, session_id: str, file_id: str) -> FileReference | None:
        if self._reference is None:
            return None
        if (
            self._reference.session_id.casefold() != session_id.casefold()
            or self._reference.file_id.casefold() != file_id.casefold()
        ):
            return None
        return self._reference.model_copy(deep=True)


def _request(file_type: FileType = FileType.UNKNOWN) -> FileReferenceRequest:
    return FileReferenceRequest(
        session_id="session:1",
        file_id="file:1",
        file_type=file_type,
        instruction_summary="Do not echo this private instruction.",
    )


def test_factory_composes_structural_file_port_without_runtime_leaks(
    tmp_path: Path,
) -> None:
    source = tmp_path / "main.c"
    source.write_bytes(b"int value;\n")
    reference = FileReference(
        session_id="session:1",
        file_id="file:1",
        basename=source.name,
        document_type=FileType.SOURCE_CODE,
        size_bytes=source.stat().st_size,
        relative_path=source.name,
    )
    runtime = create_file_runtime(
        Settings(
            _env_file=None,
            file_workspace_root=tmp_path,
            file_max_size_bytes=1024,
        ),
        _Catalog(reference),
    )

    response = asyncio.run(runtime.file_port().analyze(_request()))

    assert response.summary == "SOURCE_CODE file structure: 1 lines, 11 characters."
    assert "private instruction" not in response.summary
    for forbidden in (
        "reader",
        "extractor",
        "resolver",
        "catalog",
        "root",
        "settings",
        "configuration",
    ):
        assert not hasattr(runtime, forbidden)
        assert not hasattr(runtime.file_port(), forbidden)


def test_factory_defaults_to_unavailable_when_root_is_not_configured() -> None:
    runtime = create_file_runtime(Settings(_env_file=None), _Catalog(None))

    with pytest.raises(FileRuntimeUnavailable) as raised:
        asyncio.run(runtime.file_port().analyze(_request()))

    assert str(raised.value) == "file_unavailable"


def test_datasheet_request_remains_structural_with_empty_candidates(
    tmp_path: Path,
) -> None:
    import fitz

    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(payload)
    reference = FileReference(
        session_id="session:1",
        file_id="file:1",
        basename=source.name,
        document_type=FileType.DATASHEET,
        size_bytes=source.stat().st_size,
        relative_path=source.name,
    )
    runtime = create_file_runtime(
        Settings(_env_file=None, file_workspace_root=tmp_path),
        _Catalog(reference),
    )

    response = asyncio.run(runtime.file_port().analyze(_request(FileType.DATASHEET)))

    assert response.summary == "DATASHEET file structure: 1 pages."
    assert "chip" not in response.summary.casefold()
    assert "interface" not in response.summary.casefold()


def test_file_runtime_settings_use_safe_defaults_and_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    defaults = Settings(_env_file=None)

    assert defaults.file_workspace_root is None
    assert defaults.file_max_size_bytes == 25 * 1024 * 1024

    monkeypatch.setenv("EMBEDDED_COPILOT_FILE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("EMBEDDED_COPILOT_FILE_MAX_SIZE_BYTES", "4096")
    configured = Settings(_env_file=None)

    assert configured.file_workspace_root == tmp_path
    assert configured.file_max_size_bytes == 4096
