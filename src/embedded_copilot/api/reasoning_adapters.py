from __future__ import annotations

import asyncio

from pydantic import ValidationError

from embedded_copilot.api.copilot_models import CopilotReasoningRequest
from embedded_copilot.context_runtime import EngineeringContextPort
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextConflict,
    EngineeringContextReferenceNotFound,
    EngineeringContextRejected,
    EngineeringContextTimeout,
    EngineeringContextUnavailable,
)
from embedded_copilot.reasoning_runtime import (
    ReasoningAnalysisTimeout,
    ReasoningContextConflict,
    ReasoningContextNotFound,
    ReasoningPort,
    ReasoningRequest,
    ReasoningRequestRejected,
    ReasoningResponse,
    ReasoningRuntimeUnavailable,
    build_reasoning_context_snapshot,
)


class ContextBackedReasoningService:
    __slots__ = ("_context_port", "_reasoning_port")

    def __init__(
        self,
        context_port: EngineeringContextPort,
        reasoning_port: ReasoningPort,
    ) -> None:
        if not isinstance(context_port, EngineeringContextPort):
            raise ReasoningRuntimeUnavailable()
        if not isinstance(reasoning_port, ReasoningPort):
            raise ReasoningRuntimeUnavailable()
        self._context_port = context_port
        self._reasoning_port = reasoning_port

    async def analyze(
        self,
        *,
        session_id: str,
        trace_id: str,
        payload: CopilotReasoningRequest,
    ) -> ReasoningResponse:
        context_request = payload.to_context_request(session_id)
        try:
            context_response = await self._context_port.compose(context_request)
        except asyncio.CancelledError:
            raise
        except EngineeringContextReferenceNotFound:
            raise ReasoningContextNotFound() from None
        except EngineeringContextConflict:
            raise ReasoningContextConflict() from None
        except EngineeringContextRejected:
            raise ReasoningRequestRejected() from None
        except EngineeringContextTimeout:
            raise ReasoningAnalysisTimeout() from None
        except EngineeringContextUnavailable:
            raise ReasoningRuntimeUnavailable() from None
        except Exception:
            raise ReasoningRuntimeUnavailable() from None

        try:
            snapshot = build_reasoning_context_snapshot(
                context_request,
                context_response,
                expected_context_id=payload.context_id,
            )
            request = ReasoningRequest(
                session_id=session_id,
                trace_id=trace_id,
                context_snapshot=snapshot,
            )
            return await self._reasoning_port.analyze(request)
        except asyncio.CancelledError:
            raise
        except (ReasoningContextConflict, ReasoningRequestRejected):
            raise
        except ValidationError:
            raise ReasoningRequestRejected() from None
        except ReasoningRuntimeUnavailable:
            raise
        except ReasoningAnalysisTimeout:
            raise
        except Exception:
            raise ReasoningRuntimeUnavailable() from None
