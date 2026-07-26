from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import JsonObject, object_value, text_value
from web.copilot.state import active_session_id

_CONTEXT_ID = re.compile(r"^context:[a-f0-9]{24}$")
_DOCUMENT_TYPES = {"TEXT", "SOURCE_CODE", "PDF", "DATASHEET"}
_IMAGE_TYPES = {"schematic", "pcb", "datasheet", "debug", "unknown"}
_COMPONENT_FAMILIES = {"STM32", "ESP32", "nRF52", "RP2040"}
_INTERFACE_NAMES = {"UART", "SPI", "I2C", "USB", "CAN", "ADC", "PWM", "I2S"}
_SECTION_NAMES = {
    "Pin Description",
    "Electrical Characteristics",
    "Absolute Maximum Ratings",
    "Functional Description",
    "Peripheral",
}
_DISCLAIMER = (
    "This output is contextual information only.\nEngineer validation required."
)


def render() -> None:
    st.title("Engineering Context")
    session_id = active_session_id()
    if not session_id:
        st.info("Enter a session ID to compose referenced engineering context.")
        return

    with st.form("engineering_context_form"):
        task_intent = st.text_area(
            "Task intent",
            max_chars=512,
            placeholder="Review referenced embedded context.",
        )
        raw_reference_ids = st.text_area(
            "Reference IDs",
            max_chars=4096,
            placeholder="file:datasheet-1\nimage:1",
        )
        submitted = st.form_submit_button(
            "Compose context",
            icon=":material/hub:",
        )
    if not submitted:
        return

    reference_ids = tuple(
        line.strip() for line in raw_reference_ids.splitlines() if line.strip()
    )
    try:
        with api_client() as client:
            result = client.compose_engineering_context(
                session_id,
                task_intent=task_intent,
                reference_ids=reference_ids,
            )
        files, datasheets, vision = _context_summary(
            result,
            task_intent=task_intent,
        )
    except (ExperienceApiError, ValueError) as error:
        show_api_error(ExperienceApiError(str(error)))
        return

    st.subheader("Task Intent")
    st.markdown(task_intent)
    _show_files(files)
    _show_datasheets(datasheets)
    _show_vision(vision)
    st.warning(_DISCLAIMER)


def _context_summary(
    result: Mapping[str, object],
    *,
    task_intent: str,
) -> tuple[tuple[JsonObject, ...], tuple[JsonObject, ...], tuple[JsonObject, ...]]:
    summary = object_value(result.get("context_summary"))
    context_id = summary.get("context_id")
    if (
        result.get("output_type") != "context_summary"
        or result.get("review_required") is not True
        or not isinstance(context_id, str)
        or _CONTEXT_ID.fullmatch(context_id) is None
        or summary.get("task_intent") != task_intent
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")
    files = _items(summary.get("files"))
    datasheets = _items(summary.get("datasheets"))
    vision = _items(summary.get("vision"))
    _validate_files(files)
    _validate_datasheets(datasheets)
    _validate_vision(vision)
    return files, datasheets, vision


def _items(value: object) -> tuple[JsonObject, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")
    items: list[JsonObject] = []
    for raw_item in value:
        if not isinstance(raw_item, Mapping):
            raise ExperienceApiError("Copilot API returned an invalid response.")
        items.append(object_value(raw_item))
    return tuple(items)


def _validate_files(files: tuple[JsonObject, ...]) -> None:
    for item in files:
        file_id = text_value(item.get("file_id"), fallback="")
        document_type = item.get("document_type")
        page_count = item.get("page_count")
        line_count = item.get("line_count")
        character_count = item.get("character_count")
        pdf_counts = (
            isinstance(page_count, int)
            and not isinstance(page_count, bool)
            and page_count > 0
            and line_count is None
            and character_count is None
        )
        text_counts = (
            page_count is None
            and isinstance(line_count, int)
            and not isinstance(line_count, bool)
            and line_count >= 0
            and isinstance(character_count, int)
            and not isinstance(character_count, bool)
            and character_count >= 0
        )
        if (
            not file_id
            or document_type not in _DOCUMENT_TYPES
            or (document_type in {"PDF", "DATASHEET"} and not pdf_counts)
            or (document_type in {"TEXT", "SOURCE_CODE"} and not text_counts)
        ):
            raise ExperienceApiError("Copilot API returned an invalid response.")


def _validate_datasheets(datasheets: tuple[JsonObject, ...]) -> None:
    for item in datasheets:
        if item.get("candidate_semantics") != "unverified" or not text_value(
            item.get("file_id"), fallback=""
        ):
            raise ExperienceApiError("Copilot API returned an invalid response.")
        component_candidate = item.get("component_candidate")
        if component_candidate is not None:
            component_value = object_value(component_candidate)
            if (
                component_value.get("semantics") != "candidate"
                or component_value.get("family") not in _COMPONENT_FAMILIES
            ):
                raise ExperienceApiError("Copilot API returned an invalid response.")
        _validate_candidates(item.get("interfaces"), allowed=_INTERFACE_NAMES)
        _validate_candidates(item.get("sections"), allowed=_SECTION_NAMES)


def _validate_candidates(value: object, *, allowed: set[str]) -> None:
    items = _items(value)
    names = tuple(text_value(item.get("name"), fallback="") for item in items)
    if (
        any(item.get("semantics") != "candidate" for item in items)
        or any(name not in allowed for name in names)
        or len(set(names)) != len(names)
    ):
        raise ExperienceApiError("Copilot API returned an invalid response.")


def _validate_vision(vision: tuple[JsonObject, ...]) -> None:
    for item in vision:
        if (
            not text_value(item.get("reference_id"), fallback="")
            or item.get("image_type") not in _IMAGE_TYPES
        ):
            raise ExperienceApiError("Copilot API returned an invalid response.")


def _show_files(files: tuple[JsonObject, ...]) -> None:
    st.subheader("File Summary")
    if not files:
        st.info("No file context available.")
        return
    for item in files:
        document_type = text_value(item.get("document_type"), fallback="")
        statistics = (
            f"{item['page_count']} pages"
            if item.get("page_count") is not None
            else f"{item['line_count']} lines, {item['character_count']} characters"
        )
        st.markdown(f"{item['file_id']}: {document_type}, {statistics}")


def _show_datasheets(datasheets: tuple[JsonObject, ...]) -> None:
    st.subheader("Datasheet Candidates")
    if not datasheets:
        st.info("No datasheet candidates available.")
        return
    for item in datasheets:
        st.markdown(f"**{item['file_id']}**")
        component_candidate = item.get("component_candidate")
        if component_candidate is None:
            st.markdown("No component candidate detected.")
        else:
            component_value = object_value(component_candidate)
            family = text_value(component_value.get("family"), fallback="")
            model = text_value(component_value.get("model"), fallback="")
            label = f"{family} / {model}" if model else family
            st.markdown(f"{label} (candidate)")
        for candidate in _items(item.get("interfaces")):
            st.markdown(f"{candidate['name']} (candidate)")
        for candidate in _items(item.get("sections")):
            st.markdown(f"{candidate['name']} (candidate)")


def _show_vision(vision: tuple[JsonObject, ...]) -> None:
    st.subheader("Vision References")
    if not vision:
        st.info("No vision references available.")
        return
    for item in vision:
        st.markdown(f"{item['reference_id']}: {item['image_type']}")
