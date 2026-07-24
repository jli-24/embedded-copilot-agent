from __future__ import annotations

from pathlib import Path

import pytest

from embedded_copilot.input import InputLoader
from embedded_copilot.pcb.exceptions import PCBParseError
from embedded_copilot.pcb.parser import (
    KiCadPCBParser,
    PCBParser,
    RootedPCBSourceResolver,
)
from tests.pcb.parser.fixtures import COMPLETE_KICAD_BOARD


def _attachment(root: Path, relative_path: str = "boards/demo.kicad_pcb"):
    return InputLoader(root).load(
        relative_path,
        attachment_id="board-1",
        content_type="application/x-kicad-pcb",
    )


def test_parser_protocol_and_resolver_use_explicit_attachment_mapping(
    tmp_path: Path,
) -> None:
    board = tmp_path / "boards" / "demo.kicad_pcb"
    board.parent.mkdir()
    board.write_text(COMPLETE_KICAD_BOARD, encoding="utf-8")
    attachment = _attachment(tmp_path)
    resolver = RootedPCBSourceResolver(
        tmp_path,
        {attachment.id: "boards/demo.kicad_pcb"},
    )
    parser = KiCadPCBParser(resolver)

    assert isinstance(parser, PCBParser)
    assert resolver.resolve(attachment) == board.resolve()
    assert parser.parse(attachment).board_name == "demo"


def test_parser_does_not_scan_directories_or_read_sibling_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.kicad_pcb"
    target.write_text(COMPLETE_KICAD_BOARD, encoding="utf-8")
    sibling = tmp_path / "private.kicad_pcb"
    sibling.write_text("PRIVATE_SIBLING_SENTINEL", encoding="utf-8")
    attachment = _attachment(tmp_path, "target.kicad_pcb")
    parser = KiCadPCBParser(
        RootedPCBSourceResolver(tmp_path, {attachment.id: "target.kicad_pcb"})
    )
    before = {path.name: path.read_bytes() for path in (target, sibling)}

    def reject_scan(*args: object, **kwargs: object) -> None:
        raise AssertionError("directory scanning is forbidden")

    monkeypatch.setattr(Path, "iterdir", reject_scan)
    monkeypatch.setattr(Path, "glob", reject_scan)
    monkeypatch.setattr(Path, "rglob", reject_scan)

    model = parser.parse(attachment)

    monkeypatch.undo()
    after = {path.name: path.read_bytes() for path in (target, sibling)}
    assert model.board_name == "target"
    assert after == before
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "private.kicad_pcb",
        "target.kicad_pcb",
    ]


def test_resolver_rejects_unknown_escape_and_absolute_mappings(tmp_path: Path) -> None:
    board = tmp_path / "demo.kicad_pcb"
    board.write_text(COMPLETE_KICAD_BOARD, encoding="utf-8")
    attachment = _attachment(tmp_path, "demo.kicad_pcb")

    with pytest.raises(PCBParseError):
        RootedPCBSourceResolver(tmp_path, {}).resolve(attachment)
    with pytest.raises(PCBParseError):
        RootedPCBSourceResolver(tmp_path, {attachment.id: "../demo.kicad_pcb"})
    with pytest.raises(PCBParseError):
        RootedPCBSourceResolver(tmp_path, {attachment.id: board.resolve()})


def test_parser_module_has_no_agent_supervisor_or_knowledge_dependency() -> None:
    parser_root = Path(__file__).parents[3] / "src" / "embedded_copilot" / "pcb" / "parser"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in parser_root.glob("*.py")
    )

    assert "embedded_copilot.pcb.agent" not in source
    assert "embedded_copilot.supervisor" not in source
    assert "embedded_copilot.knowledge" not in source
