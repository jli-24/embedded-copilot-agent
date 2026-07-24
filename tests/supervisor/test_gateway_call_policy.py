from __future__ import annotations

import inspect

from embedded_copilot.debug import agent as debug_agent
from embedded_copilot.firmware import agent as firmware_agent
from embedded_copilot.hardware import agent as hardware_agent
from embedded_copilot.pcb import agent as pcb_agent
from embedded_copilot.supervisor import dispatcher, knowledge_adapters, planner
from embedded_copilot.supervisor.agent import SupervisorAgent


def test_gateway_search_call_site_belongs_exclusively_to_supervisor_run() -> None:
    run_source = inspect.getsource(SupervisorAgent.run)
    class_source = inspect.getsource(SupervisorAgent)

    assert "self._knowledge_gateway.search(" in run_source
    assert class_source.count("self._knowledge_gateway.search(") == 1


def test_downstream_modules_do_not_import_or_reference_gateway() -> None:
    for module in (
        planner,
        dispatcher,
        knowledge_adapters,
        firmware_agent,
        hardware_agent,
        pcb_agent,
        debug_agent,
    ):
        source = inspect.getsource(module)
        assert "KnowledgeGateway" not in source
        assert "knowledge.gateway" not in source
