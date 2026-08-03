from __future__ import annotations

from collections.abc import Callable

from embedded_copilot.reasoning.contracts import ReasoningRequest, ReasoningResponse
from embedded_copilot.reasoning.exceptions import ReasoningRuntimeUnavailable


class LocalModelReasoningAdapter:
    __slots__ = ("_invoker",)

    def __init__(
        self,
        invoker: Callable[[ReasoningRequest], ReasoningResponse] | None = None,
    ) -> None:
        self._invoker = invoker

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        if self._invoker is None:
            raise ReasoningRuntimeUnavailable()
        result = self._invoker(request)
        if type(result) is not ReasoningResponse:
            raise ReasoningRuntimeUnavailable()
        return result


__all__ = ["LocalModelReasoningAdapter"]
