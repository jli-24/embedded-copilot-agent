from embedded_copilot.agents import supervisor as runtime_supervisor
from embedded_copilot.supervisor import SupervisorAgent as PublicSupervisor
from embedded_copilot.supervisor.agent import SupervisorAgent as FoundationSupervisor


def test_foundation_and_runtime_supervisor_imports_do_not_shadow_each_other() -> None:
    assert PublicSupervisor is FoundationSupervisor
    assert callable(runtime_supervisor.classify_intent)
    assert callable(runtime_supervisor.supervisor_node)
    assert not hasattr(runtime_supervisor, "SupervisorAgent")
