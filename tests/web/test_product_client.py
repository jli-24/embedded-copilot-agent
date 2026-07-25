from __future__ import annotations

import httpx
import pytest

from embedded_copilot.services.execution import ExecutionStatus
from web.client import ProductApiClient, ProductApiError


def test_product_client_validates_status_and_report_contracts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/status/exec-1":
            return httpx.Response(
                200,
                json={"execution_id": "exec-1", "status": "running", "error": None},
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )
    assert client.status("exec-1").status is ExecutionStatus.RUNNING
    with pytest.raises(ProductApiError, match="not found"):
        client.report("missing")


def test_product_client_maps_transport_errors_without_leaking_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("PRIVATE_NETWORK_PATH", request=request)

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProductApiError, match="Product API is unavailable") as exc:
        client.status("exec-1")
    assert "PRIVATE_NETWORK_PATH" not in str(exc.value)
