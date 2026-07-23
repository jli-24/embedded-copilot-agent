import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult


def _result_metadata(metadata: dict[str, object]) -> KnowledgeResult:
    return KnowledgeResult(
        id="doc",
        title="Title",
        content="Technical token handling is legitimate document content.",
        source="LOCAL",
        metadata=metadata,
    )


@pytest.mark.parametrize(
    "metadata",
    [
        {"token": "value"},
        {"nested": {"api_secret": "value"}},
        {"nested": [{"credential_name": "value"}]},
        {"password_hint": "value"},
        {"local_path": "relative.txt"},
    ],
)
def test_gateway_metadata_rejects_sensitive_keys_recursively(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _result_metadata(metadata)


@pytest.mark.parametrize(
    "path",
    [
        "C:/Users/private/document.md",
        "C:\\Users\\private\\document.md",
        "\\\\server\\share\\document.md",
        "/home/private/document.md",
    ],
)
def test_gateway_metadata_rejects_absolute_local_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        _result_metadata({"reference": {"value": path}})


def test_gateway_metadata_allows_urls_and_technical_token_text() -> None:
    result = _result_metadata(
        {"reference_url": "https://example.com/docs", "topic": "token handling"}
    )

    assert result.metadata["reference_url"] == "https://example.com/docs"
    assert "token" in result.content


def test_knowledge_query_applies_the_same_recursive_metadata_policy() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(
            query="SPI",
            metadata={"filters": {"credential": "private"}},
        )


def test_gateway_metadata_checks_unordered_nested_collections() -> None:
    with pytest.raises(ValidationError):
        _result_metadata({"references": {"C:/Users/private/document.md"}})
