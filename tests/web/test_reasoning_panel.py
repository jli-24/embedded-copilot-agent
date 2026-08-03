from __future__ import annotations

import json

import httpx

from web.copilot.client import CopilotExperienceClient
from web.copilot.reasoning import ReasoningPanel


def test_reasoning_client_sends_only_safe_query_fields() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "summary": "summary",
                "explanation": "explanation",
                "tradeoffs": [],
                "risks": [],
                "references": ["evidence-1"],
                "confidence": 0.5,
                "fingerprint": "sha256:private",
                "provider": "private",
            },
        )

    client = CopilotExperienceClient(
        "http://api", transport=httpx.MockTransport(handler)
    )
    result = ReasoningPanel(client).query(
        recommendation_id="recommendation-1",
        mode="EXPLAIN",
        question="Explain the recommendation.",
    )
    assert captured == {
        "recommendation_id": "recommendation-1",
        "mode": "EXPLAIN",
        "question": "Explain the recommendation.",
    }
    assert set(result) == {
        "summary",
        "explanation",
        "tradeoffs",
        "risks",
        "references",
        "confidence",
    }
    client.close()
