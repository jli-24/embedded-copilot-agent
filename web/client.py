from __future__ import annotations

from collections.abc import Sequence

import httpx

from embedded_copilot.api.models import (
    AnalysisAgent,
    AnalysisOptions,
    AnalyzeRequest,
    AnalyzeResponse,
)
from embedded_copilot.input.models import UserAttachment
from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.services.execution import ExecutionSnapshot


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
        payload = AnalyzeRequest(
            request=request,
            attachments=tuple(attachments),
            options=AnalysisOptions(required_agents=tuple(required_agents)),
        )
        response = self._request(
            "POST",
            "/api/v1/analyze",
            json=payload.model_dump(mode="json"),
        )
        return AnalyzeResponse.model_validate(response.json())

    def status(self, execution_id: str) -> ExecutionSnapshot:
        response = self._request("GET", f"/api/v1/status/{execution_id}")
        return ExecutionSnapshot.model_validate(response.json())

    def report(self, execution_id: str) -> EngineeringReport:
        response = self._request("GET", f"/api/v1/report/{execution_id}")
        return EngineeringReport.model_validate(response.json())

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise ProductApiError("Product API is unavailable.") from None
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            message = detail if isinstance(detail, str) else "Product API request failed."
            raise ProductApiError(message)
        return response
