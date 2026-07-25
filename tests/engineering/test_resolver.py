from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from embedded_copilot.engineering.resolver import (
    EngineeringResolutionError,
    TrustedEngineeringResolver,
)
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)


def _attachment(
    attachment_id: str,
    filename: str,
    media_type: AttachmentType,
    content_type: str,
    size_bytes: int,
) -> UserAttachment:
    return UserAttachment(
        id=attachment_id,
        filename=filename,
        media_type=media_type,
        content_type=content_type,
        size_bytes=size_bytes,
        metadata={
            "category": media_type.value,
            "format": Path(filename).suffix.removeprefix(".").casefold(),
        },
    )


def test_resolver_reads_only_explicit_supported_attachments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "esp32-s3.pdf"
    source = tmp_path / "main.c"
    secret = tmp_path / "private.txt"
    pdf.write_bytes(b"%PDF-explicit")
    source.write_text("void app_main(void) {}", encoding="utf-8")
    secret.write_text("PRIVATE_SENTINEL", encoding="utf-8")
    context = UnifiedInputContext(
        attachments=(
            _attachment(
                "datasheet-1",
                pdf.name,
                AttachmentType.DOCUMENT,
                "application/pdf",
                pdf.stat().st_size,
            ),
            _attachment(
                "source-1",
                source.name,
                AttachmentType.SOURCE_CODE,
                "text/x-c",
                source.stat().st_size,
            ),
        )
    )

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("directory scanning is forbidden")

    monkeypatch.setattr(Path, "glob", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)
    monkeypatch.setattr(Path, "iterdir", forbidden)

    resolved = TrustedEngineeringResolver(tmp_path).resolve(context)

    assert [item.reference.filename for item in resolved] == [
        "esp32-s3.pdf",
        "main.c",
    ]
    assert [item.data for item in resolved] == [
        b"%PDF-explicit",
        b"void app_main(void) {}",
    ]
    assert b"PRIVATE_SENTINEL" not in b"".join(item.data for item in resolved)


def test_resolver_rejects_size_changes_without_leaking_root(tmp_path: Path) -> None:
    source = tmp_path / "main.c"
    source.write_text("void app_main(void) {}", encoding="utf-8")
    context = UnifiedInputContext(
        attachments=(
            _attachment(
                "source-1",
                source.name,
                AttachmentType.SOURCE_CODE,
                "text/x-c",
                source.stat().st_size + 1,
            ),
        )
    )

    with pytest.raises(EngineeringResolutionError) as captured:
        TrustedEngineeringResolver(tmp_path).resolve(context)

    assert str(tmp_path) not in str(captured.value)
    assert "main.c" not in str(captured.value)


def test_resolver_rejects_multiple_datasheets(tmp_path: Path) -> None:
    attachments = []
    for index in (1, 2):
        path = tmp_path / f"part-{index}.pdf"
        path.write_bytes(b"%PDF")
        attachments.append(
            _attachment(
                f"datasheet-{index}",
                path.name,
                AttachmentType.DOCUMENT,
                "application/pdf",
                path.stat().st_size,
            )
        )

    with pytest.raises(EngineeringResolutionError, match="Datasheet input is invalid"):
        TrustedEngineeringResolver(tmp_path).resolve(
            UnifiedInputContext(attachments=tuple(attachments))
        )


def test_resolver_rejects_firmware_content_type_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "main.c"
    source.write_text("void app_main(void) {}", encoding="utf-8")
    attachment = _attachment(
        "source-1",
        source.name,
        AttachmentType.SOURCE_CODE,
        "application/octet-stream",
        source.stat().st_size,
    )

    with pytest.raises(EngineeringResolutionError, match="Firmware input is invalid"):
        TrustedEngineeringResolver(tmp_path).resolve(
            UnifiedInputContext(attachments=(attachment,))
        )


def test_resolver_rejects_file_change_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "main.c"
    source.write_text("void app_main(void) {}", encoding="utf-8")
    attachment = _attachment(
        "source-1",
        source.name,
        AttachmentType.SOURCE_CODE,
        "text/x-c",
        source.stat().st_size,
    )
    real_fstat = os.fstat
    calls = 0

    def changing_fstat(descriptor: int) -> object:
        nonlocal calls
        calls += 1
        current = real_fstat(descriptor)
        if calls == 1:
            return current
        return SimpleNamespace(
            st_mode=current.st_mode,
            st_size=current.st_size,
            st_dev=current.st_dev,
            st_ino=current.st_ino,
            st_mtime_ns=current.st_mtime_ns + 1,
        )

    monkeypatch.setattr(
        "embedded_copilot.engineering.resolver.os.fstat",
        changing_fstat,
    )

    with pytest.raises(EngineeringResolutionError):
        TrustedEngineeringResolver(tmp_path).resolve(
            UnifiedInputContext(attachments=(attachment,))
        )
