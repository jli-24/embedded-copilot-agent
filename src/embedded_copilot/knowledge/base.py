from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar, runtime_checkable


DocumentT = TypeVar("DocumentT", contravariant=True)
ResultT = TypeVar("ResultT", covariant=True)


@runtime_checkable
class KnowledgeRetriever(Protocol[DocumentT, ResultT]):
    """Storage-agnostic knowledge retrieval contract."""

    def search(self, query: str) -> Sequence[ResultT]: ...

    def add_documents(self, documents: Sequence[DocumentT]) -> None: ...
