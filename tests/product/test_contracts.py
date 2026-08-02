from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.product import (
    CreateProjectRequest,
    ProductStage,
    create_product_runtime,
)
from tests.product.conftest import make_request


def test_facade_exposes_only_stateless_workspace_port() -> None:
    runtime = create_product_runtime()
    assert set(name for name in dir(runtime) if not name.startswith("_")) == {
        "product_workspace_port"
    }


def test_request_is_frozen_strict_tuple_only_and_utc(product_sources) -> None:
    request = make_request(product_sources)
    with pytest.raises(ValidationError):
        request.project_name = "changed"
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(
            {**request.model_dump(mode="python"), "decisions": list(request.decisions)}
        )
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(
            {**request.model_dump(mode="python"), "created_at": datetime(2026, 8, 11)}
        )
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(
            {**request.model_dump(mode="python"), "extra": "forbidden"}
        )


def test_workspace_contains_only_safe_references(product_sources) -> None:
    workspace = (
        create_product_runtime()
        .product_workspace_port()
        .create_project(make_request(product_sources))
    )
    assert tuple(item.stage for item in workspace.stage_references) == tuple(
        ProductStage
    )
    assert workspace.session.project_id == workspace.project_id
    payload = workspace.model_dump(mode="json")
    forbidden = {
        "requirement",
        "plan",
        "context",
        "hardware_proposal",
        "firmware_proposal",
        "validation_report",
        "artifact_contract",
        "execution_report",
        "feedback_report",
        "optimization_report",
        "source_code",
        "binary",
        "raw_log",
    }

    def keys(value):
        if isinstance(value, dict):
            yield from value
            for nested in value.values():
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    assert forbidden.isdisjoint(set(keys(payload)))
