from __future__ import annotations

import json
import re

import httpx
import pytest

from embedded_copilot.input.models import AttachmentType, UserAttachment
from embedded_copilot.services.execution import ExecutionStatus
from web.client import ProductApiClient, ProductApiError


def test_product_client_analyze_sends_contract_payload_and_parses_accepted_response() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/analyze"
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            202,
            json={"execution_id": "exec-1", "status": "queued"},
        )

    attachment = UserAttachment(
        id="datasheet-1",
        filename="sensor.pdf",
        media_type=AttachmentType.DOCUMENT,
        content_type="application/pdf",
        size_bytes=1024,
        metadata={"category": "document", "format": "pdf"},
    )
    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )

    response = client.analyze(
        "Analyze sensor integration",
        [attachment],
        ["hardware", "firmware"],
    )

    assert captured_payload == {
        "request": "Analyze sensor integration",
        "attachments": [
            {
                "id": "datasheet-1",
                "filename": "sensor.pdf",
                "media_type": "document",
                "content_type": "application/pdf",
                "size_bytes": 1024,
                "metadata": {"category": "document", "format": "pdf"},
            }
        ],
        "options": {"required_agents": ["hardware", "firmware"]},
    }
    assert response.execution_id == "exec-1"
    assert response.status is ExecutionStatus.QUEUED


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
    with pytest.raises(
        ProductApiError,
        match=re.escape("Product API 请求失败，请稍后重试。"),
    ):
        client.report("missing")


def test_product_client_maps_transport_errors_without_leaking_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "request=/api/v1/status/private token=SECRET_TOKEN",
            request=request,
        )

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(
        ProductApiError,
        match=re.escape("无法连接 Product API，请确认服务是否可用。"),
    ) as exc:
        client.status("exec-1")
    assert str(exc.value) == "无法连接 Product API，请确认服务是否可用。"
    assert all(
        value not in str(exc.value)
        for value in ("request", "/api/v1/status/private", "SECRET_TOKEN", "ConnectError")
    )


def test_product_client_maps_timeout_without_leaking_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "request=/api/v1/status/private token=SECRET_TOKEN",
            request=request,
        )

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProductApiError) as exc:
        client.status("exec-1")

    assert str(exc.value) == "Product API 请求超时，请稍后重试。"
    assert "SECRET_TOKEN" not in str(exc.value)
    assert "/api/v1/status/private" not in str(exc.value)


def test_product_client_maps_http_error_without_using_server_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "detail": "request=/internal/private token=SECRET_TOKEN upstream failed"
            },
        )

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProductApiError) as exc:
        client.status("exec-1")

    assert str(exc.value) == "Product API 请求失败，请稍后重试。"
    assert "SECRET_TOKEN" not in str(exc.value)
    assert "/internal/private" not in str(exc.value)


def test_product_client_maps_invalid_json_without_leaking_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"{request=/internal/private token=SECRET_TOKEN",
        )

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProductApiError) as exc:
        client.status("exec-1")

    assert str(exc.value) == "Product API 返回格式无效，请联系管理员。"
    assert "SECRET_TOKEN" not in str(exc.value)
    assert "/internal/private" not in str(exc.value)


def test_product_client_maps_schema_failure_without_leaking_validation_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "execution_id": "exec-1",
                "status": "token=SECRET_TOKEN request=/internal/private",
                "error": None,
            },
        )

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProductApiError) as exc:
        client.status("exec-1")

    assert str(exc.value) == "Product API 返回数据不符合预期，请联系管理员。"
    assert "SECRET_TOKEN" not in str(exc.value)
    assert "/internal/private" not in str(exc.value)


def test_product_client_maps_request_schema_failure_without_leaking_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid request must not reach the transport")

    client = ProductApiClient(
        "http://api",
        transport=httpx.MockTransport(handler),
    )
    private_request = "token=SECRET_TOKEN " + ("x" * 20_000)

    with pytest.raises(ProductApiError) as exc:
        client.analyze(private_request, [], [])

    assert str(exc.value) == "Product API 请求数据不符合要求，请检查输入。"
    assert "SECRET_TOKEN" not in str(exc.value)
    assert private_request not in str(exc.value)
