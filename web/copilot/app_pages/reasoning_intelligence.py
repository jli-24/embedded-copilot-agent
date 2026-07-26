from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import JsonObject
from web.copilot.state import active_session_id

_CONTEXT_ID = re.compile(r"^context:[a-f0-9]{24}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_RISK_CATEGORIES = {
    "context_completeness",
    "component_identity",
    "interface_compatibility",
    "firmware_configuration",
    "visual_interpretation",
}
_RISK_SEVERITIES = {"low", "medium", "high"}
_SOURCE_TYPES = {"FILE", "DATASHEET", "VISION"}
_RULE_SOURCES = {"context", "component", "interface", "firmware", "vision"}
_CAPABILITIES = (
    "context_analysis",
    "risk_detection",
    "verification_planning",
)
_GENERATED_SECTIONS = {"summary", "risk", "next_step"}
_DISCLAIMER = "This output is engineering guidance only.\nEngineer validation required."


def render() -> None:
    st.title("Reasoning Intelligence")
    session_id = active_session_id()
    if not session_id:
        st.info("Enter a session ID to analyze referenced engineering context.")
        return

    with st.form("reasoning_intelligence_form"):
        task_intent = st.text_area(
            "Task intent",
            max_chars=512,
            placeholder="Review referenced engineering context.",
        )
        context_id = st.text_input(
            "Context ID",
            placeholder="context:0123456789abcdef01234567",
        )
        raw_reference_ids = st.text_area(
            "Reference IDs",
            max_chars=4096,
            placeholder="file:datasheet-1\nimage:1",
        )
        submitted = st.form_submit_button(
            "Analyze context",
            icon=":material/psychology:",
        )
    if not submitted:
        return

    reference_ids = tuple(
        line.strip() for line in raw_reference_ids.splitlines() if line.strip()
    )
    try:
        with api_client() as client:
            result = client.analyze_reasoning(
                session_id,
                task_intent=task_intent,
                context_id=context_id,
                reference_ids=reference_ids,
            )
        summary, risks, next_steps, trace = _reasoning_result(
            result,
            context_id=context_id,
        )
    except (ExperienceApiError, ValueError) as error:
        show_api_error(ExperienceApiError(str(error)))
        return

    _show_analysis(summary)
    _show_risks(risks)
    _show_supporting_references(risks)
    _show_next_steps(next_steps)
    _show_trace(trace)
    st.warning(_DISCLAIMER)


def _reasoning_result(
    result: Mapping[str, object],
    *,
    context_id: str,
) -> tuple[JsonObject, tuple[JsonObject, ...], tuple[JsonObject, ...], JsonObject]:
    _require_keys(
        result,
        {
            "output_type",
            "reasoning_summary",
            "risks",
            "next_steps",
            "trace",
            "review_required",
        },
    )
    if (
        result.get("output_type") != "reasoning_suggestion"
        or result.get("review_required") is not True
    ):
        _invalid_response()

    summary = _summary(result.get("reasoning_summary"))
    risks = _risk_candidates(result.get("risks"))
    next_steps = _next_steps(result.get("next_steps"))
    trace = _trace(result.get("trace"), context_id=context_id, has_risks=bool(risks))
    return summary, risks, next_steps, trace


def _summary(value: object) -> JsonObject:
    summary = _object(value)
    _require_keys(
        summary,
        {"summary", "presentation_summary", "confidence", "assumptions"},
    )
    _text(summary.get("summary"), max_length=1024)
    presentation = summary.get("presentation_summary")
    if presentation is not None:
        _text(presentation, max_length=512)
    if summary.get("confidence") not in {"low", "medium"}:
        _invalid_response()
    _text_items(summary.get("assumptions"), max_items=16, max_length=512)
    return summary


def _risk_candidates(value: object) -> tuple[JsonObject, ...]:
    risks = _objects(value, max_items=8)
    for risk in risks:
        _require_keys(
            risk,
            {
                "category",
                "description",
                "severity",
                "supporting_references",
            },
        )
        if (
            risk.get("category") not in _RISK_CATEGORIES
            or risk.get("severity") not in _RISK_SEVERITIES
        ):
            _invalid_response()
        _text(risk.get("description"), max_length=512)
        risk["supporting_references"] = _supporting_references(
            risk.get("supporting_references")
        )
    return risks


def _supporting_references(value: object) -> tuple[JsonObject, ...]:
    references = _objects(value, max_items=32)
    seen: set[tuple[str, str]] = set()
    for reference in references:
        _require_keys(reference, {"reference_id", "source_type", "reason"})
        reference_id = _identifier(reference.get("reference_id"))
        source_type = reference.get("source_type")
        if source_type not in _SOURCE_TYPES:
            _invalid_response()
        _text(reference.get("reason"), max_length=512)
        key = (reference_id.casefold(), str(source_type))
        if key in seen:
            _invalid_response()
        seen.add(key)
    return references


def _next_steps(value: object) -> tuple[JsonObject, ...]:
    steps = _objects(value, max_items=8)
    for step in steps:
        _require_keys(step, {"action", "reason"})
        _text(step.get("action"), max_length=256)
        _text(step.get("reason"), max_length=512)
    return steps


def _trace(
    value: object,
    *,
    context_id: str,
    has_risks: bool,
) -> JsonObject:
    trace = _object(value)
    _require_keys(
        trace,
        {
            "trace_id",
            "context_id",
            "snapshot_fingerprint",
            "capabilities_applied",
            "rules_applied",
            "generated_sections",
        },
    )
    _identifier(trace.get("trace_id"))
    if (
        trace.get("context_id") != context_id
        or not isinstance(context_id, str)
        or _CONTEXT_ID.fullmatch(context_id) is None
    ):
        _invalid_response()
    fingerprint = trace.get("snapshot_fingerprint")
    if not isinstance(fingerprint, str) or _FINGERPRINT.fullmatch(fingerprint) is None:
        _invalid_response()

    capabilities = _objects(trace.get("capabilities_applied"), max_items=3)
    names: list[str] = []
    for capability in capabilities:
        _require_keys(capability, {"name", "version"})
        if capability.get("version") != "1.0":
            _invalid_response()
        names.append(_text(capability.get("name"), max_length=64))
    if tuple(names) != _CAPABILITIES:
        _invalid_response()
    trace["capabilities_applied"] = capabilities

    rules = _objects(trace.get("rules_applied"), max_items=32)
    rule_keys: set[tuple[str, str]] = set()
    for rule in rules:
        _require_keys(
            rule,
            {
                "rule_id",
                "rule_version",
                "rule_source",
                "triggered",
                "references",
                "reason",
            },
        )
        rule_id = _identifier(rule.get("rule_id"))
        rule_version = rule.get("rule_version")
        if (
            rule_version != "1.0"
            or rule.get("rule_source") not in _RULE_SOURCES
            or not isinstance(rule.get("triggered"), bool)
        ):
            _invalid_response()
        references = _identifier_items(rule.get("references"), max_items=32)
        if rule.get("triggered") is False and references:
            _invalid_response()
        _text(rule.get("reason"), max_length=512)
        key = (rule_id, str(rule_version))
        if key in rule_keys:
            _invalid_response()
        rule_keys.add(key)
        rule["references"] = references
    trace["rules_applied"] = rules

    sections = _text_items(
        trace.get("generated_sections"),
        max_items=3,
        max_length=32,
    )
    expected_sections = (
        ("summary", "risk", "next_step") if has_risks else ("summary", "next_step")
    )
    if tuple(sections) != expected_sections or any(
        section not in _GENERATED_SECTIONS for section in sections
    ):
        _invalid_response()
    trace["generated_sections"] = sections
    return trace


def _show_analysis(summary: JsonObject) -> None:
    st.subheader("Analysis")
    st.markdown(str(summary["summary"]))
    st.caption(f"Confidence: {summary['confidence']}")
    assumptions = tuple(summary["assumptions"])
    for assumption in assumptions:
        st.caption(f"Assumption: {assumption}")
    presentation = summary.get("presentation_summary")
    if isinstance(presentation, str):
        st.subheader("Presentation Summary")
        st.markdown(presentation)


def _show_risks(risks: tuple[JsonObject, ...]) -> None:
    st.subheader("Risk Candidates")
    if not risks:
        st.info("No risk candidates generated.")
        return
    for risk in risks:
        st.markdown(
            f"**{risk['category']}** ({risk['severity']}): {risk['description']}"
        )


def _show_supporting_references(risks: tuple[JsonObject, ...]) -> None:
    st.subheader("Supporting References")
    references = tuple(
        reference
        for risk in risks
        for reference in tuple(risk["supporting_references"])
    )
    if not references:
        st.info("No supporting references available.")
        return
    for reference in references:
        st.markdown(
            f"**{reference['reference_id']}** ({reference['source_type']}): "
            f"{reference['reason']}"
        )


def _show_next_steps(next_steps: tuple[JsonObject, ...]) -> None:
    st.subheader("Suggested Next Steps")
    for step in next_steps:
        st.markdown(f"**{step['action']}**: {step['reason']}")


def _show_trace(trace: JsonObject) -> None:
    st.subheader("Reasoning Trace")
    st.caption(f"Trace ID: {trace['trace_id']}")
    st.caption(f"Context ID: {trace['context_id']}")
    st.caption(f"Snapshot: {trace['snapshot_fingerprint']}")
    for capability in tuple(trace["capabilities_applied"]):
        st.markdown(f"Capability: {capability['name']}@{capability['version']}")
    for rule in tuple(trace["rules_applied"]):
        status = "triggered" if rule["triggered"] else "not triggered"
        st.markdown(
            f"Rule: {rule['rule_id']}@{rule['rule_version']} "
            f"({rule['rule_source']}, {status})"
        )


def _objects(value: object, *, max_items: int) -> tuple[JsonObject, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        _invalid_response()
    items = tuple(_object(item) for item in value)
    if len(items) > max_items:
        _invalid_response()
    return items


def _object(value: object) -> JsonObject:
    if not isinstance(value, Mapping):
        _invalid_response()
    return {str(key): item for key, item in value.items()}


def _text_items(
    value: object,
    *,
    max_items: int,
    max_length: int,
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        _invalid_response()
    items = tuple(_text(item, max_length=max_length) for item in value)
    if len(items) > max_items or len(set(items)) != len(items):
        _invalid_response()
    return items


def _identifier_items(value: object, *, max_items: int) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        _invalid_response()
    items = tuple(_identifier(item) for item in value)
    if len(items) > max_items or len(set(items)) != len(items):
        _invalid_response()
    return items


def _identifier(value: object) -> str:
    candidate = _text(value, max_length=160)
    if _IDENTIFIER.fullmatch(candidate) is None:
        _invalid_response()
    return candidate


def _text(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        _invalid_response()
    candidate = " ".join(value.split())
    if not candidate or len(candidate) > max_length:
        _invalid_response()
    return candidate


def _require_keys(value: Mapping[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        _invalid_response()


def _invalid_response() -> None:
    raise ExperienceApiError("Copilot API returned an invalid response.")
