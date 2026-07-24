from __future__ import annotations

from pathlib import Path

import pytest

from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.loader import InputLoader
from embedded_copilot.input.models import AttachmentType


def test_loader_returns_only_safe_deterministic_file_metadata(tmp_path: Path) -> None:
    path = tmp_path / "BOARD.KICAD_PCB"
    path.write_bytes(b"PRIVATE PCB CONTENT")
    before = sorted(entry.name for entry in tmp_path.iterdir())

    attachment = InputLoader(tmp_path).load(
        "BOARD.KICAD_PCB",
        attachment_id="board-1",
        content_type="application/x-kicad-pcb",
    )

    assert attachment.id == "board-1"
    assert attachment.filename == "BOARD.KICAD_PCB"
    assert attachment.media_type is AttachmentType.EDA
    assert attachment.content_type == "application/x-kicad-pcb"
    assert attachment.size_bytes == 19
    assert attachment.metadata == {"category": "eda", "format": "kicad_pcb"}
    serialized = attachment.model_dump_json()
    assert "PRIVATE PCB CONTENT" not in serialized
    assert str(tmp_path) not in serialized
    assert sorted(entry.name for entry in tmp_path.iterdir()) == before


def test_loader_does_not_open_or_read_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "serial.log").write_bytes(b"PRIVATE LOG CONTENT")

    def reject_content_access(*args: object, **kwargs: object) -> object:
        raise AssertionError("file content access is forbidden")

    monkeypatch.setattr(Path, "open", reject_content_access)
    monkeypatch.setattr(Path, "read_text", reject_content_access)
    monkeypatch.setattr(Path, "read_bytes", reject_content_access)

    attachment = InputLoader(tmp_path).load(
        "serial.log",
        attachment_id="log-1",
    )

    assert attachment.size_bytes == 19
    assert attachment.media_type is AttachmentType.LOG


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside.log",
        "nested/../../outside.log",
        "C:/Users/private/serial.log",
        "\\\\server\\share\\serial.log",
        ".",
    ],
)
def test_loader_rejects_traversal_and_absolute_paths_without_leak(
    tmp_path: Path,
    relative_path: str,
) -> None:
    with pytest.raises(
        InputValidationError,
        match="attachment metadata is invalid",
    ) as captured:
        InputLoader(tmp_path).load(relative_path, attachment_id="log-1")

    assert relative_path not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "oversize"])
def test_loader_rejects_invalid_file_state_with_fixed_error(
    tmp_path: Path,
    kind: str,
) -> None:
    relative = "serial.log"
    if kind == "directory":
        (tmp_path / relative).mkdir()
    elif kind == "empty":
        (tmp_path / relative).touch()
    elif kind == "oversize":
        (tmp_path / relative).write_bytes(b"12345")

    loader = InputLoader(tmp_path, max_size_bytes=4)
    with pytest.raises(InputValidationError) as captured:
        loader.load(relative, attachment_id="log-1")

    assert str(captured.value) in {
        "attachment metadata is invalid",
        "attachment size is invalid",
    }
    assert str(tmp_path) not in str(captured.value)
    assert captured.value.__cause__ is None


def test_loader_rejects_unknown_extension_and_mime_mismatch(tmp_path: Path) -> None:
    (tmp_path / "archive.zip").write_bytes(b"1234")
    (tmp_path / "board.png").write_bytes(b"1234")
    loader = InputLoader(tmp_path)

    with pytest.raises(InputValidationError, match="attachment type is invalid"):
        loader.load("archive.zip", attachment_id="archive-1")
    with pytest.raises(InputValidationError, match="attachment type is invalid"):
        loader.load(
            "board.png",
            attachment_id="image-1",
            content_type="application/pdf",
        )


def test_loader_rejects_target_and_parent_symlinks(tmp_path: Path) -> None:
    real = tmp_path / "real.log"
    real.write_bytes(b"1234")
    target_link = tmp_path / "target.log"
    directory = tmp_path / "directory"
    directory.mkdir()
    (directory / "nested.log").write_bytes(b"1234")
    directory_link = tmp_path / "linked"
    try:
        target_link.symlink_to(real)
        directory_link.symlink_to(directory, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    loader = InputLoader(tmp_path)
    for path in ("target.log", "linked/nested.log"):
        with pytest.raises(
            InputValidationError,
            match="attachment metadata is invalid",
        ):
            loader.load(path, attachment_id="log-1")


def test_loader_rejects_invalid_root_and_size_limit(tmp_path: Path) -> None:
    with pytest.raises(InputValidationError, match="input root is invalid"):
        InputLoader(tmp_path / "missing")
    with pytest.raises(InputValidationError, match="input size limit is invalid"):
        InputLoader(tmp_path, max_size_bytes=0)
