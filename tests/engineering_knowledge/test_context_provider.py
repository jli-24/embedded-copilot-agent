from embedded_copilot.engineering_knowledge import EngineeringContextProviderPort


def test_context_provider_is_only_a_port() -> None:
    assert hasattr(EngineeringContextProviderPort, "get_context")
    assert not hasattr(EngineeringContextProviderPort, "write")
    assert not hasattr(EngineeringContextProviderPort, "update")
