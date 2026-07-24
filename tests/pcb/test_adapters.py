from __future__ import annotations

import pytest

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.pcb.adapters import attach_pcb_model
from embedded_copilot.pcb.exceptions import PCBAnalysisError
from embedded_copilot.pcb.models import UnifiedPCBModel


def _model() -> UnifiedPCBModel:
    return UnifiedPCBModel(
        board_name="adapter_demo",
        source_format="kicad_pcb",
        components=(),
        nets=({"name": "GND", "net_type": "ground", "nodes": ()},),
        layers=({"name": "F.Cu", "index": 0, "type": "signal"},),
    )


def test_attach_pcb_model_isolates_task_and_rejects_duplicate_context() -> None:
    original = AgentTask(
        task_id="pcb-adapter",
        task_type="pcb",
        requirement="Review parsed board",
        metadata={"caller": "test"},
    )

    attached = attach_pcb_model(original, _model())

    assert original.metadata == {"caller": "test"}
    assert attached.metadata["caller"] == "test"
    assert attached != original
    with pytest.raises(PCBAnalysisError, match="PCB model context already exists"):
        attach_pcb_model(attached, _model())


def test_attach_pcb_model_rejects_invalid_inputs() -> None:
    task = AgentTask(task_id="pcb-adapter", task_type="pcb", requirement="Review")

    with pytest.raises(PCBAnalysisError, match="PCB analysis adapter is invalid"):
        attach_pcb_model(task, object())
    with pytest.raises(PCBAnalysisError, match="PCB analysis adapter is invalid"):
        attach_pcb_model(object(), _model())
