from pathlib import Path

from .contracts import KnowledgeWriterPort
from .writer import FileKnowledgeWriter


def create_knowledge_writer(root: Path) -> KnowledgeWriterPort:
    return FileKnowledgeWriter(root)

