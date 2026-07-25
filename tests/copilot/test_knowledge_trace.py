from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.events import KnowledgeTrace
from embedded_copilot.copilot.models import KnowledgeTraceAction


def test_knowledge_trace_binds_result_count_to_sources() -> None:
    empty = KnowledgeTrace(
        query="Search the existing knowledge index.",
        source_ids=(),
        result_count=0,
        action=KnowledgeTraceAction.VIEWED,
    )
    populated = KnowledgeTrace(
        query="Search existing Datasheet evidence.",
        source_ids=("datasheet:1", "datasheet:2"),
        result_count=3,
        action=KnowledgeTraceAction.USED,
    )

    assert empty.source_ids == ()
    assert populated.source_ids == ("datasheet:1", "datasheet:2")


@pytest.mark.parametrize(
    ("source_ids", "result_count"),
    (
        ((), 1),
        (("datasheet:1",), 0),
        (("datasheet:1", "datasheet:2"), 1),
        (("datasheet:1", "DATASHEET:1"), 2),
    ),
)
def test_knowledge_trace_rejects_unbound_or_ambiguous_sources(
    source_ids: tuple[str, ...],
    result_count: int,
) -> None:
    with pytest.raises(ValidationError):
        KnowledgeTrace(
            query="Search existing evidence.",
            source_ids=source_ids,
            result_count=result_count,
            action=KnowledgeTraceAction.SAVED,
        )


@pytest.mark.parametrize(
    "query",
    (
        "first line\nsecond line",
        r"Read C:\Users\private\datasheet.pdf",
        "api_key=sk-privatecredential",
        b"PDF binary content",
    ),
)
def test_knowledge_trace_rejects_sensitive_query(query: object) -> None:
    with pytest.raises(ValidationError):
        KnowledgeTrace(
            query=query,
            source_ids=(),
            result_count=0,
            action=KnowledgeTraceAction.VIEWED,
        )
