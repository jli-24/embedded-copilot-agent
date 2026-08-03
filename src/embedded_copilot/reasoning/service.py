from __future__ import annotations

import copy
import hashlib
import json

from pydantic import ValidationError

from .context import ReasoningInputProjection, validate_reasoning_input
from .contracts import (
    ReasoningMode,
    ReasoningPort,
    ReasoningRequest,
    ReasoningResponse,
)
from .exceptions import ReasoningRequestRejected, ReasoningRuntimeUnavailable


class ReasoningService:
    __slots__ = ("_port",)

    def __init__(self, port: ReasoningPort) -> None:
        if port is None or not callable(getattr(port, "reason", None)):
            raise ReasoningRuntimeUnavailable()
        self._port = port

    def reason(
        self,
        request: ReasoningRequest | None = None,
        *,
        projection: ReasoningInputProjection | None = None,
        question: str | None = None,
        reasoning_mode: ReasoningMode | None = None,
        request_id: str | None = None,
        recommendation_id: str | None = None,
    ) -> ReasoningResponse:
        try:
            if request is None:
                if projection is None or question is None or reasoning_mode is None:
                    raise ValueError("reasoning request is incomplete")
                checked_projection = validate_reasoning_input(projection)
                request = ReasoningRequest(
                    request_id=request_id
                    or self._request_id(checked_projection, question, reasoning_mode),
                    project_id=checked_projection.context_snapshot.project_id,
                    recommendation_id=(
                        recommendation_id
                        or checked_projection.recommendation.recommendation_id
                    ),
                    context_fingerprint=checked_projection.context_snapshot.context_fingerprint,
                    evidence_references=checked_projection.evidence_references,
                    question=question,
                    reasoning_mode=reasoning_mode,
                    context_snapshot=checked_projection.context_snapshot,
                    recommendation=checked_projection.recommendation,
                )
            checked_request = ReasoningRequest.model_validate(copy.deepcopy(request))
            result = self._port.reason(checked_request)
            if type(result) is not ReasoningResponse:
                raise ValueError("reasoning response is invalid")
            return ReasoningResponse.model_validate(copy.deepcopy(result))
        except (ReasoningRuntimeUnavailable, ReasoningRequestRejected):
            raise
        except (TypeError, ValueError, ValidationError) as error:
            raise ReasoningRequestRejected() from error
        except Exception as error:
            raise ReasoningRuntimeUnavailable() from error

    @staticmethod
    def _request_id(
        projection: ReasoningInputProjection,
        question: str,
        reasoning_mode: ReasoningMode,
    ) -> str:
        material = {
            "recommendation_id": projection.recommendation.recommendation_id,
            "context_fingerprint": projection.context_snapshot.context_fingerprint,
            "question": question,
            "reasoning_mode": reasoning_mode.value,
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        return "request-" + hashlib.sha256(encoded).hexdigest()[:32]


__all__ = ["ReasoningService"]
