from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest
from pydantic import ValidationError

from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)


def _attachment(
    attachment_id: str = "image-1",
    *,
    metadata: Mapping[str, object] | None = None,
) -> UserAttachment:
    return UserAttachment(
        id=attachment_id,
        filename="board.png",
        media_type=AttachmentType.IMAGE,
        content_type="image/png",
        size_bytes=128,
        metadata=(
            metadata
            if metadata is not None
            else {"format": "png", "category": "image"}
        ),
    )


def test_user_attachment_is_frozen_extra_forbidden_and_deterministic() -> None:
    attachment = _attachment()

    assert attachment.model_dump(mode="json") == {
        "id": "image-1",
        "filename": "board.png",
        "media_type": "image",
        "content_type": "image/png",
        "size_bytes": 128,
        "metadata": {"category": "image", "format": "png"},
    }
    with pytest.raises(ValidationError):
        attachment.filename = "other.png"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        UserAttachment(
            id="image-1",
            filename="board.png",
            media_type="image",
            content_type="image/png",
            size_bytes=128,
            metadata={"format": "png", "category": "image"},
            content=b"forbidden",
        )


def test_attachment_metadata_is_copied_and_has_no_mutable_state() -> None:
    source: dict[str, object] = {"format": "png", "category": "image"}
    attachment = _attachment(metadata=source)
    source["format"] = "jpeg"

    assert attachment.metadata == {"category": "image", "format": "png"}
    with pytest.raises(TypeError):
        attachment.metadata["format"] = "jpeg"  # type: ignore[index]


@pytest.mark.parametrize(
    "metadata",
    [
        {"format": "png", "category": "image", "path": "board.png"},
        {"format": "png", "category": "image", "content": "private"},
        {"format": "png", "category": "document"},
    ],
)
def test_attachment_metadata_allows_only_matching_safe_provenance(
    metadata: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        _attachment(metadata=metadata)


def test_user_attachment_rejects_paths_blank_ids_and_empty_files() -> None:
    valid = {
        "id": "attachment-1",
        "filename": "board.png",
        "media_type": "image",
        "content_type": "image/png",
        "size_bytes": 1,
        "metadata": {"format": "png", "category": "image"},
    }

    for update in (
        {"id": " "},
        {"filename": "C:/Users/private/board.png"},
        {"filename": "../board.png"},
        {"size_bytes": 0},
    ):
        with pytest.raises(ValidationError):
            UserAttachment(**{**valid, **update})


def test_unified_context_uses_tuple_and_isolates_all_input_values() -> None:
    attachment = _attachment()
    attachments = [attachment]
    metadata: dict[str, object] = {"source": "user_upload", "attempt": 1}

    context = UnifiedInputContext(
        text="  Review this board  ",
        attachments=attachments,
        metadata=metadata,
    )
    attachments.clear()
    metadata["source"] = "changed"

    assert context.text == "Review this board"
    assert context.attachments == (attachment,)
    assert isinstance(context.attachments, tuple)
    assert context.metadata == {"attempt": 1, "source": "user_upload"}
    with pytest.raises(TypeError):
        context.metadata["source"] = "changed"  # type: ignore[index]


@pytest.mark.parametrize(
    "metadata",
    [
        {"nested": {"mutable": True}},
        {"nested": ["mutable"]},
        {"path": "relative/private.txt"},
        {"home_directory": "private"},
        {"token": "secret"},
        {"source": "C:/Users/private"},
    ],
)
def test_unified_context_rejects_mutable_or_sensitive_metadata(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        UnifiedInputContext(metadata=metadata)


def test_unified_context_rejects_duplicate_ids_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="duplicate attachment id"):
        UnifiedInputContext(
            attachments=(_attachment("LOG-1"), _attachment("log-1")),
        )


def test_unified_context_is_frozen_and_forbids_extra_fields() -> None:
    context = UnifiedInputContext()

    with pytest.raises(ValidationError):
        context.text = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        UnifiedInputContext(unexpected=True)


def test_input_model_validation_errors_hide_rejected_sensitive_values() -> None:
    with pytest.raises(ValidationError) as attachment_error:
        UserAttachment(
            id="image-1",
            filename="C:/Users/PRIVATE_SENTINEL/board.png",
            media_type="image",
            content_type="image/png",
            size_bytes=128,
            metadata={"format": "png", "category": "image"},
        )
    with pytest.raises(ValidationError) as context_error:
        UnifiedInputContext(
            metadata={"source": "C:/Users/PRIVATE_SENTINEL/private.txt"}
        )

    for error in (attachment_error.value, context_error.value):
        rendered = str(error)
        assert "PRIVATE_SENTINEL" not in rendered
        assert "Users" not in rendered


def test_input_metadata_copy_failure_is_mapped_without_exception_leak() -> None:
    class FailingMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            raise RuntimeError("PRIVATE_SENTINEL")

        def __iter__(self) -> Iterator[str]:
            raise RuntimeError("PRIVATE_SENTINEL")

        def __len__(self) -> int:
            return 1

        def __deepcopy__(self, memo: dict[int, object]) -> "FailingMapping":
            raise RuntimeError("PRIVATE_SENTINEL")

    with pytest.raises(ValidationError) as captured:
        UnifiedInputContext(metadata=FailingMapping())

    assert "PRIVATE_SENTINEL" not in str(captured.value)
