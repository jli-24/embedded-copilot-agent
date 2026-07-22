import pytest
from pydantic import ValidationError

from embedded_copilot.core.models import AgentContext


def test_agent_context_is_strict_and_frozen() -> None:
    context = AgentContext(session_id=" session-1 ", metadata={"trace_id": "abc"})

    assert context.session_id == "session-1"
    assert context.user_id is None
    with pytest.raises(ValidationError):
        context.session_id = "changed"  # type: ignore[misc]


def test_agent_context_rejects_empty_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentContext(session_id=" ")
    with pytest.raises(ValidationError):
        AgentContext(session_id="s", unexpected=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        AgentContext(session_id="s", user_id=" ")
