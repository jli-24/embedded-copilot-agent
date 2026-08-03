from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from embedded_copilot.api.models import (
    AnalysisAgent,
    AnalysisOptions,
    AnalyzeRequest,
    AnalyzeResponse,
)
from embedded_copilot.input.models import UserAttachment
from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.services.execution import ExecutionSnapshot


ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class ProductApiError(RuntimeError):
    """Safe UI-facing Product API error."""


class ProductApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    def analyze(
        self,
        request: str,
        attachments: Sequence[UserAttachment],
        required_agents: Sequence[AnalysisAgent],
    ) -> AnalyzeResponse:
        try:
            payload = AnalyzeRequest(
                request=request,
                attachments=tuple(attachments),
                options=AnalysisOptions(required_agents=tuple(required_agents)),
            )
        except ValidationError:
            raise ProductApiError(
                "Product API 请求数据不符合要求，请检查输入。"
            ) from None
        response = self._request(
            "POST",
            "/api/v1/analyze",
            json=payload.model_dump(mode="json"),
        )
        return self._parse_response(response, AnalyzeResponse)

    def status(self, execution_id: str) -> ExecutionSnapshot:
        response = self._request("GET", f"/api/v1/status/{execution_id}")
        return self._parse_response(response, ExecutionSnapshot)

    def report(self, execution_id: str) -> EngineeringReport:
        response = self._request("GET", f"/api/v1/report/{execution_id}")
        return self._parse_response(response, EngineeringReport)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise ProductApiError("Product API 请求超时，请稍后重试。") from None
        except httpx.RequestError:
            raise ProductApiError("无法连接 Product API，请确认服务是否可用。") from None
        if response.is_error:
            raise ProductApiError("Product API 请求失败，请稍后重试。")
        return response

    @staticmethod
    def _parse_response(
        response: httpx.Response,
        model: type[ResponseModelT],
    ) -> ResponseModelT:
        try:
            payload = response.json()
        except ValueError:
            raise ProductApiError("Product API 返回格式无效，请联系管理员。") from None
        try:
            return model.model_validate(payload)
        except ValidationError:
            raise ProductApiError(
                "Product API 返回数据不符合预期，请联系管理员。"
            ) from None
