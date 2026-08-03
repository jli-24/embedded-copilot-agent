from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from web.copilot.contracts import JsonObject


class ExperienceApiError(RuntimeError):
    """A safe Copilot API failure for browser presentation."""


class CopilotExperienceClient:
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
            trust_env=False,
        )

    def __enter__(self) -> "CopilotExperienceClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def create_session(
        self,
        *,
        session_id: str,
        project_name: str,
        requirement_summary: str,
        created_at: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            "/api/v1/copilot/sessions",
            json={
                "session_id": session_id,
                "project_name": project_name,
                "user_requirement": requirement_summary,
                "created_at": created_at,
            },
        )

    def get_workspace(self, session_id: str) -> JsonObject:
        return self._request("GET", f"{self._session_url(session_id)}/workspace")

    def get_artifacts(self, session_id: str) -> JsonObject:
        return self._request("GET", f"{self._session_url(session_id)}/artifact-view")

    def get_files(self, session_id: str) -> JsonObject:
        return self._request("GET", f"{self._session_url(session_id)}/files")

    def get_progress(self, session_id: str) -> JsonObject:
        return self._request("GET", f"{self._session_url(session_id)}/progress")

    def send_message(
        self,
        session_id: str,
        *,
        message_id: str,
        summary: str,
        created_at: str,
        references: tuple[str, ...] = (),
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/messages",
            json={
                "message_id": message_id,
                "content_summary": summary,
                "created_at": created_at,
                "references": list(references),
            },
        )

    def bind_attachment(
        self,
        session_id: str,
        *,
        reference_id: str,
        input_type: str,
        basename: str,
        summary: str,
        size_bytes: int,
        created_at: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/attachments",
            json={
                "reference_id": reference_id,
                "type": input_type,
                "basename": basename,
                "summary": summary,
                "size_bytes": size_bytes,
                "created_at": created_at,
            },
        )

    def analyze_vision(
        self,
        session_id: str,
        *,
        reference_id: str,
        instruction_summary: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/vision",
            json={
                "reference_id": reference_id,
                "instruction_summary": instruction_summary,
            },
        )

    def analyze_file(
        self,
        session_id: str,
        *,
        file_id: str,
        instruction_summary: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/files/analyze",
            json={
                "file_id": file_id,
                "instruction_summary": instruction_summary,
            },
        )

    def analyze_datasheet(
        self,
        session_id: str,
        *,
        file_id: str,
        instruction_summary: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/datasheets/analyze",
            json={
                "file_id": file_id,
                "instruction_summary": instruction_summary,
            },
        )

    def compose_engineering_context(
        self,
        session_id: str,
        *,
        task_intent: str,
        reference_ids: tuple[str, ...],
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/context",
            json={
                "task_intent": task_intent,
                "reference_ids": list(reference_ids),
            },
        )

    def analyze_reasoning(
        self,
        session_id: str,
        *,
        task_intent: str,
        context_id: str,
        reference_ids: tuple[str, ...],
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/reasoning",
            json={
                "task_intent": task_intent,
                "context_id": context_id,
                "reference_ids": list(reference_ids),
            },
        )

    def get_model_status(self) -> JsonObject:
        return self._request("GET", "/api/v1/copilot/models/status")

    def get_memory_candidates(self) -> JsonObject:
        return self._request("GET", "/api/memory/candidates")

    def approve_memory(
        self,
        *,
        memory_id: str,
        candidate_fingerprint: str,
        reviewer: str,
        decision: str,
        reviewed_at: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            "/api/memory/approve",
            json={
                "memory_id": memory_id,
                "candidate_fingerprint": candidate_fingerprint,
                "reviewer": reviewer,
                "decision": decision,
                "reviewed_at": reviewed_at,
            },
        )

    def query_intelligence(self, *, project_id: str, question: str) -> JsonObject:
        return self._request(
            "POST",
            "/api/intelligence/query",
            json={"project_id": project_id, "question": question},
        )

    def get_intelligence_context(self, project_id: str) -> JsonObject:
        identifier = project_id.strip()
        if not identifier:
            raise ExperienceApiError("Project identity is required.")
        return self._request("GET", f"/api/intelligence/context/{quote(identifier, safe=':_-.')}")

    def query_reasoning(
        self,
        *,
        recommendation_id: str,
        mode: str,
        question: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            "/api/reasoning/query",
            json={
                "recommendation_id": recommendation_id,
                "mode": mode,
                "question": question,
            },
        )

    def record_review(
        self,
        session_id: str,
        *,
        intent_id: str,
        artifact_id: str,
        action: str,
        comment_summary: str | None,
        timestamp: str,
    ) -> JsonObject:
        return self._request(
            "POST",
            f"{self._session_url(session_id)}/review",
            json={
                "intent_id": intent_id,
                "artifact_id": artifact_id,
                "action": action,
                "comment_summary": comment_summary,
                "timestamp": timestamp,
            },
        )

    def _session_url(self, session_id: str) -> str:
        identifier = session_id.strip()
        if not identifier:
            raise ExperienceApiError("Session identity is required.")
        return f"/api/v1/copilot/sessions/{quote(identifier, safe=':')}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> JsonObject:
        try:
            response = self._client.request(method, url, json=json)
        except httpx.TimeoutException as error:
            raise ExperienceApiError("Copilot API request timed out.") from error
        except httpx.HTTPError as error:
            raise ExperienceApiError("Copilot API is unavailable.") from error
        if response.is_error:
            detail = "Copilot API request failed."
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, Mapping) and isinstance(payload.get("detail"), str):
                detail = " ".join(payload["detail"].split())[:512]
            raise ExperienceApiError(detail)
        try:
            payload = response.json()
        except ValueError as error:
            raise ExperienceApiError(
                "Copilot API returned an invalid response."
            ) from error
        if not isinstance(payload, Mapping):
            raise ExperienceApiError("Copilot API returned an invalid response.")
        return {str(key): value for key, value in payload.items()}
