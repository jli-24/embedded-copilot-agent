from __future__ import annotations

import re
from collections.abc import Sequence

from embedded_copilot.pcb.knowledge.models import PCBRuleDocument


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_+\-]*|[\u4e00-\u9fff]+", text)
    }


class PCBKnowledgeRetriever:
    """Deterministic in-memory PCB rule knowledge retriever."""

    def __init__(
        self,
        documents: Sequence[PCBRuleDocument] | None = None,
        *,
        top_k: int = 4,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self._top_k = top_k
        self._documents: dict[str, PCBRuleDocument] = {}
        if documents is not None:
            self.add_documents(documents)

    def add_documents(self, documents: Sequence[PCBRuleDocument]) -> None:
        for document in documents:
            self._documents[document.id] = document

    def search(self, query: str) -> Sequence[PCBRuleDocument]:
        return self.retrieve(query)

    def retrieve(self, query: str) -> list[PCBRuleDocument]:
        query_tokens = _tokens(query.strip())
        if not query_tokens:
            return []

        ranked: list[tuple[int, int, PCBRuleDocument]] = []
        for position, document in enumerate(self._documents.values()):
            document_tokens = _tokens(
                "\n".join((document.title, document.category, document.content))
            )
            score = len(query_tokens & document_tokens)
            if score:
                ranked.append((score, position, document))
        ranked.sort(key=lambda item: (-item[0], item[1]))

        return [
            document.model_copy(
                update={
                    "metadata": {
                        **document.metadata,
                        "retrieval_score": score,
                        "retrieval_score_kind": "keyword_overlap",
                    }
                }
            )
            for score, _, document in ranked[: self._top_k]
        ]
