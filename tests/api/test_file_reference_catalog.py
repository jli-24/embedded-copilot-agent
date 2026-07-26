from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from embedded_copilot.api.file_reference_catalog import (
    CopilotFileReferenceCatalog,
)
from embedded_copilot.file_runtime import FileType
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)


def _repository() -> ProcessLocalAttachmentBindingRepository:
    repository = ProcessLocalAttachmentBindingRepository()
    repository.bind(
        AttachmentBinding(
            session_id="session:1",
            input=MultimodalInput(
                type=MultimodalInputType.FILE,
                reference_id="file:1",
                summary="Referenced source file metadata.",
            ),
            basename="main.py",
            size_bytes=42,
            created_at=datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
        )
    )
    return repository


def test_copilot_catalog_projects_attachment_to_private_file_reference() -> None:
    catalog = CopilotFileReferenceCatalog(
        _repository(),
        {("session:1", "file:1"): Path("private/main.py")},
    )

    reference = catalog.resolve("session:1", "file:1")

    assert reference is not None
    assert reference.session_id == "session:1"
    assert reference.file_id == "file:1"
    assert reference.basename == "main.py"
    assert reference.document_type is FileType.SOURCE_CODE
    assert reference.relative_path == Path("private/main.py")
    assert "private" not in str(reference)
    assert "relative_path" not in reference.model_dump(mode="json")


def test_copilot_catalog_is_session_bound_and_read_only() -> None:
    catalog = CopilotFileReferenceCatalog(
        _repository(),
        {("session:1", "file:1"): "main.py"},
    )

    assert catalog.resolve("session:2", "file:1") is None
    for forbidden in ("create", "bind", "update", "delete", "save", "write"):
        assert not hasattr(catalog, forbidden)
