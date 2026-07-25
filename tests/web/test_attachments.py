from __future__ import annotations

from web.attachments import build_attachment_metadata


class _ContentBlindUpload:
    name = "camera.c"
    type = "text/x-c"
    size = 128

    def read(self) -> bytes:
        raise AssertionError("upload content must not be read")

    def getvalue(self) -> bytes:
        raise AssertionError("upload content must not be read")


def test_upload_metadata_builder_never_reads_content() -> None:
    attachment = build_attachment_metadata(_ContentBlindUpload(), "upload-1")

    assert attachment.filename == "camera.c"
    assert attachment.content_type == "text/x-c"
    assert attachment.size_bytes == 128
    assert attachment.metadata == {"category": "source_code", "format": "c"}
