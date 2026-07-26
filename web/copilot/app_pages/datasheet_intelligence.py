from __future__ import annotations

from collections.abc import Mapping, Sequence

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import JsonObject, object_value, text_value
from web.copilot.state import active_session_id

COMPONENT_FAMILIES = {"STM32", "ESP32", "nRF52", "RP2040"}
INTERFACE_NAMES = {"UART", "SPI", "I2C", "USB", "CAN", "ADC", "PWM", "I2S"}
SECTION_NAMES = {
    "Pin Description",
    "Electrical Characteristics",
    "Absolute Maximum Ratings",
    "Functional Description",
    "Peripheral",
}
DISCLAIMER = "This output is not Engineering Evidence. Engineer validation required."


def render() -> None:
    st.title("Datasheet Intelligence")
    session_id = active_session_id()
    if not session_id:
        st.info("Enter a session ID to analyze a registered datasheet reference.")
        return

    with st.form("datasheet_intelligence_form"):
        file_id = st.text_input(
            "Datasheet reference ID",
            placeholder="file:datasheet-1",
        )
        instruction_summary = st.text_area(
            "Analysis request",
            max_chars=512,
            placeholder="Extract unverified datasheet candidates.",
        )
        submitted = st.form_submit_button(
            "Analyze datasheet",
            icon=":material/find_in_page:",
        )
    if not submitted:
        return

    try:
        with api_client() as client:
            result = client.analyze_datasheet(
                session_id,
                file_id=file_id,
                instruction_summary=instruction_summary,
            )
        component_candidate, interfaces, sections = _candidate_summary(
            result,
            file_id=file_id,
        )
    except (ExperienceApiError, ValueError) as error:
        show_api_error(ExperienceApiError(str(error)))
        return

    st.caption("Candidate semantics: unverified")
    _show_component(component_candidate)
    _show_named_candidates(
        "Interface Candidates",
        interfaces,
        empty_message="No interface candidates detected.",
    )
    _show_named_candidates(
        "Section Summary",
        sections,
        empty_message="No section candidates detected.",
    )
    st.warning(DISCLAIMER)


def _candidate_summary(
    result: Mapping[str, object],
    *,
    file_id: str,
) -> tuple[JsonObject | None, tuple[str, ...], tuple[str, ...]]:
    summary = object_value(result.get("summary"))
    if (
        result.get("type") != "reasoning_suggestion"
        or result.get("review_required") is not True
        or summary.get("candidate_semantics") != "unverified"
        or summary.get("file_id") != file_id
        or not {
            "component_candidate",
            "interface_candidates",
            "electrical_candidates",
            "section_candidates",
        }.issubset(summary)
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")

    component_candidate = _component_candidate(summary.get("component_candidate"))
    interfaces = _named_candidates(
        summary.get("interface_candidates"),
        allowed=INTERFACE_NAMES,
    )
    _candidate_items(summary.get("electrical_candidates"))
    sections = _named_candidates(
        summary.get("section_candidates"),
        allowed=SECTION_NAMES,
    )
    return component_candidate, interfaces, sections


def _component_candidate(value: object) -> JsonObject | None:
    if value is None:
        return None
    component_candidate = object_value(value)
    family = component_candidate.get("family")
    model = component_candidate.get("model")
    if (
        component_candidate.get("semantics") != "candidate"
        or family not in COMPONENT_FAMILIES
        or (model is not None and not text_value(model, fallback=""))
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")
    return component_candidate


def _candidate_items(value: object) -> tuple[JsonObject, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")
    items: list[JsonObject] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ExperienceApiError("Copilot API returned an invalid response.")
        item = object_value(raw)
        if item.get("semantics") != "candidate":
            raise ExperienceApiError("Copilot API returned an invalid response.")
        items.append(item)
    return tuple(items)


def _named_candidates(
    value: object,
    *,
    allowed: set[str],
) -> tuple[str, ...]:
    names = tuple(
        text_value(item.get("name"), fallback="") for item in _candidate_items(value)
    )
    if any(not name or name not in allowed for name in names) or len(names) != len(
        set(names)
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")
    return names


def _show_component(component_candidate: JsonObject | None) -> None:
    st.subheader("Component Candidate")
    if component_candidate is None:
        st.info("No component candidate detected.")
        return
    family = text_value(component_candidate.get("family"), fallback="")
    model = text_value(component_candidate.get("model"), fallback="")
    label = f"{family} / {model}" if model else family
    st.write(f"{label} (candidate)")


def _show_named_candidates(
    title: str,
    candidates: tuple[str, ...],
    *,
    empty_message: str,
) -> None:
    st.subheader(title)
    if not candidates:
        st.info(empty_message)
        return
    for candidate in candidates:
        st.write(f"{candidate} (candidate)")
