from embedded_copilot.engineering_context import EngineeringContextProviderPort


def test_provider_is_read_only_and_standalone() -> None:
    assert hasattr(EngineeringContextProviderPort, "get_context")
    assert not hasattr(EngineeringContextProviderPort, "write")
    assert not hasattr(EngineeringContextProviderPort, "update")
    assert not hasattr(EngineeringContextProviderPort, "execute")
