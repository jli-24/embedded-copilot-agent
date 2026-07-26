from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingConflict,
    AttachmentBindingNotFound,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)

CREATED = datetime(2026, 7, 26, 9, 0, tzinfo=timezone.utc)


def _binding(
    *,
    session_id: str = "session:1",
    reference_id: str = "image:1",
) -> AttachmentBinding:
    return AttachmentBinding(
        session_id=session_id,
        input=MultimodalInput(
            type=MultimodalInputType.IMAGE,
            reference_id=reference_id,
            summary="ESP32 schematic image reference.",
        ),
        basename="esp32-schematic.png",
        size_bytes=1024,
        created_at=CREATED,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("bytes", b"private"),
        ("base64", "cHJpdmF0ZQ=="),
        ("binary", bytearray(b"private")),
        ("content", "private file content"),
        ("path", "C:/private/schematic.png"),
    ),
)
def test_multimodal_input_rejects_content_and_location_fields(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        MultimodalInput.model_validate(
            {
                "type": "IMAGE",
                "reference_id": "image:1",
                "summary": "ESP32 schematic image reference.",
                field: value,
            }
        )


def test_attachment_repository_isolates_snapshots_and_sessions() -> None:
    repository = ProcessLocalAttachmentBindingRepository()
    binding = _binding()

    repository.bind(binding)

    assert repository.get("session:1", "image:1") == binding
    assert repository.list("session:1") == (binding,)
    with pytest.raises(AttachmentBindingNotFound):
        repository.get("session:2", "image:1")
    with pytest.raises(AttachmentBindingConflict):
        repository.bind(_binding(reference_id="IMAGE:1"))


def test_attachment_repository_cannot_persist_binary_or_file_content() -> None:
    repository = ProcessLocalAttachmentBindingRepository()
    repository.bind(_binding())

    serialized = repository.list("session:1")[0].model_dump(mode="json")

    assert set(serialized) == {
        "session_id",
        "input",
        "basename",
        "size_bytes",
        "created_at",
    }
    assert set(serialized["input"]) == {"type", "reference_id", "summary"}
    assert b"private" not in repr(serialized).encode()
