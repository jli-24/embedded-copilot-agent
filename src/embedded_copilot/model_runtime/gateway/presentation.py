from __future__ import annotations

import asyncio
import copy
import re
from dataclasses import dataclass

from pydantic import ValidationError

from embedded_copilot.intelligence.exceptions import ModelGatewayError
from embedded_copilot.intelligence.models import ModelInput
from embedded_copilot.model_runtime.gateway.model import ModelGateway
from embedded_copilot.reasoning_runtime import (
    PresentationPatch,
    ReasoningContextSnapshot,
    ReasoningPort,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningSummary,
)
from embedded_copilot.schemas.model import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)

_SENTENCE = re.compile(r"[^.!?]+[.!?]")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+_.-]*")
_FORBIDDEN = re.compile(
    r"\b(?:wrong|incorrect|broken|incompatible|failure|failed|verified|confirmed|"
    r"root\s+cause|change|reconfigure|write|patch|apply|execute|generate|build|"
    r"flash|replace|repair|fix)\b",
    re.IGNORECASE,
)
_UNCERTAINTY_PHRASES = (
    "may",
    "might",
    "could",
    "requires verification",
    "should be reviewed",
    "engineer review",
    "additional verification",
)
_PRESENTATION_WORDS = frozenset(
    {
        "a",
        "additional",
        "an",
        "and",
        "are",
        "available",
        "be",
        "candidate",
        "candidates",
        "context",
        "could",
        "engineer",
        "for",
        "further",
        "guidance",
        "in",
        "is",
        "may",
        "might",
        "of",
        "or",
        "required",
        "requires",
        "review",
        "reviewed",
        "should",
        "source",
        "sources",
        "subject",
        "summary",
        "the",
        "this",
        "those",
        "to",
        "verification",
        "with",
    }
)


@dataclass(frozen=True, slots=True)
class AllowedEnhancementPolicy:
    max_characters: int = 512
    minimum_sentences: int = 1
    maximum_sentences: int = 2


@dataclass(frozen=True, slots=True)
class ReasoningEnhancementValidator:
    _policy: AllowedEnhancementPolicy = AllowedEnhancementPolicy()

    def validate(
        self,
        text: str,
        snapshot: ReasoningContextSnapshot,
        response: ReasoningResponse,
    ) -> PresentationPatch:
        patch = PresentationPatch(summary=text)
        normalized = patch.summary.casefold()
        sentences = tuple(_SENTENCE.findall(patch.summary))
        if (
            len(patch.summary) > self._policy.max_characters
            or not self._policy.minimum_sentences
            <= len(sentences)
            <= self._policy.maximum_sentences
            or "".join(sentences).strip() != patch.summary.strip()
            or not any(phrase in normalized for phrase in _UNCERTAINTY_PHRASES)
            or _FORBIDDEN.search(patch.summary)
        ):
            raise ValueError("presentation enhancement is unsafe")

        allowed = set(_PRESENTATION_WORDS)
        allowed.update(
            _token_value(item)
            for item in _TOKEN.findall(response.reasoning_summary.summary)
        )
        allowed.update(_candidate_tokens(snapshot))
        if any(
            _token_value(token) not in allowed
            for token in _TOKEN.findall(patch.summary)
        ):
            raise ValueError("presentation enhancement adds unsupported content")
        return patch


def _candidate_tokens(snapshot: ReasoningContextSnapshot) -> set[str]:
    tokens: set[str] = set()
    for datasheet in snapshot.datasheet_candidates:
        component = datasheet.component_candidate
        if component is not None:
            tokens.update(
                _token_value(item) for item in _TOKEN.findall(component.family)
            )
            if component.model is not None:
                tokens.update(
                    _token_value(item) for item in _TOKEN.findall(component.model)
                )
        for interface in datasheet.interfaces:
            tokens.update(_token_value(item) for item in _TOKEN.findall(interface.name))
        for section in datasheet.sections:
            tokens.update(_token_value(item) for item in _TOKEN.findall(section.name))
    return tokens


def _token_value(value: str) -> str:
    return value.casefold().strip(".!?")


def merge_presentation(
    response: ReasoningResponse,
    patch: PresentationPatch,
) -> ReasoningResponse:
    canonical = ReasoningResponse.model_validate(
        copy.deepcopy(response.model_dump(mode="python"))
    )
    summary = canonical.reasoning_summary
    return ReasoningResponse(
        reasoning_summary=ReasoningSummary(
            summary=summary.summary,
            presentation_summary=patch.summary,
            confidence=summary.confidence,
            assumptions=summary.assumptions,
        ),
        risks=canonical.risks,
        next_steps=canonical.next_steps,
        trace=canonical.trace,
        review_required=canonical.review_required,
    )


@dataclass(frozen=True, slots=True)
class PresentationReasoningPort:
    _base: ReasoningPort
    _gateway: ModelGateway
    _validator: ReasoningEnhancementValidator = ReasoningEnhancementValidator()

    async def analyze(self, request: ReasoningRequest) -> ReasoningResponse:
        canonical = await self._base.analyze(request)
        try:
            model_response = await self._gateway.generate(
                ModelRequest(
                    task_type=ModelTaskType.REASONING,
                    input_type=ModelInputType.TEXT,
                    context_ids=(request.context_snapshot.snapshot_fingerprint,),
                ),
                ModelInput(
                    message_summary=canonical.reasoning_summary.summary,
                    context_summaries=(
                        f"Confidence: {canonical.reasoning_summary.confidence}.",
                        f"Risk candidate count: {len(canonical.risks)}.",
                        f"Suggested next step count: {len(canonical.next_steps)}.",
                    ),
                ),
            )
            patch = self._validator.validate(
                model_response.text,
                request.context_snapshot,
                canonical,
            )
            return merge_presentation(canonical, patch)
        except asyncio.CancelledError:
            raise
        except (ModelGatewayError, ValidationError, ValueError):
            return canonical


@dataclass(frozen=True, slots=True)
class GatewayPresentationEnhancer:
    _gateway: ModelGateway

    def wrap(self, base: ReasoningPort) -> ReasoningPort:
        if not isinstance(base, ReasoningPort):
            raise TypeError("reasoning port is invalid")
        return PresentationReasoningPort(base, self._gateway)
