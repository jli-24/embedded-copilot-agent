from __future__ import annotations

from embedded_copilot.context_runtime.contracts import ContextDocumentType
from embedded_copilot.reasoning_runtime.contracts import RuleResult
from embedded_copilot.reasoning_runtime.rules.context import RuleContext


def firmware_configuration_review_required(context: RuleContext) -> RuleResult:
    references = tuple(
        item.file_id
        for item in context.file_summaries
        if item.document_type is ContextDocumentType.SOURCE_CODE
    )
    return RuleResult(
        rule_id="firmware_configuration_review_required",
        rule_source="firmware",
        triggered=bool(references),
        references=references,
        reason=(
            "Source structure summaries cannot validate firmware configuration."
            if references
            else "No source structure summary requires firmware configuration review."
        ),
    )
