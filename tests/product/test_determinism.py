from __future__ import annotations

from embedded_copilot.product import canonical_product_json, create_product_runtime
from tests.product.conftest import make_request


def test_product_projection_is_deterministic_across_100_calls(product_sources) -> None:
    request = make_request(product_sources)
    before = request.model_dump(mode="json")
    port = create_product_runtime().product_workspace_port()

    workspaces = tuple(port.create_project(request) for _ in range(100))
    dashboards = tuple(port.get_progress(item) for item in workspaces)
    reports = tuple(port.generate_report(item) for item in workspaces)

    assert len({item.fingerprint for item in workspaces}) == 1
    assert len({item.fingerprint for item in dashboards}) == 1
    assert len({item.fingerprint for item in reports}) == 1
    assert len({hash(item) for item in workspaces}) == 1
    assert len({canonical_product_json(item) for item in workspaces}) == 1
    assert len({canonical_product_json(item) for item in dashboards}) == 1
    assert len({canonical_product_json(item) for item in reports}) == 1
    assert request.model_dump(mode="json") == before
