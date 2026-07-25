from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from web.copilot.app_pages.shared import api_client, show_api_error, show_viewer_state
from web.copilot.client import ExperienceApiError
from web.copilot.contracts import object_list, object_value, text_value
from web.copilot.state import active_session_id


def _quote(value: object) -> str:
    text = text_value(value, fallback="unknown")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def graphviz_source(projection: Mapping[str, object]) -> tuple[str | None, str]:
    nodes = object_list(projection.get("nodes"))
    edges = object_list(projection.get("edges"))
    if not edges:
        return None, "unresolved"
    lines = ["digraph blueprint {", "  rankdir=LR;"]
    for node in nodes:
        lines.append(
            f"  {_quote(node.get('node_id'))} [label={_quote(node.get('label'))}];"
        )
    for edge in edges:
        lines.append(
            "  "
            f"{_quote(edge.get('source_node_id'))} -> "
            f"{_quote(edge.get('target_node_id'))} "
            f"[label={_quote(edge.get('label'))}];"
        )
    lines.append("}")
    return "\n".join(lines), "ready"


def render() -> None:
    st.title("Blueprint")
    session_id = active_session_id()
    if not session_id:
        st.caption("No active session.")
        return
    try:
        with api_client() as client:
            payload = client.get_artifacts(session_id)
    except ExperienceApiError as error:
        show_api_error(error)
        return

    show_viewer_state(payload)
    for item in object_list(payload.get("artifacts")):
        st.subheader(text_value(item.get("project_summary")))
        projection = object_value(item.get("blueprint_summary"))
        source, state = graphviz_source(projection)
        if state == "unresolved":
            st.warning("Blueprint relationships are unresolved.")
            nodes = object_list(projection.get("nodes"))
            if nodes:
                st.dataframe(nodes, hide_index=True)
            continue
        if source is not None:
            st.graphviz_chart(source)
