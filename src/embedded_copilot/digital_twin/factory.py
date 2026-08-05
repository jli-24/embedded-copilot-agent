from .adapters.fake import FakeDigitalTwinAdapter


def create_digital_twin_port() -> None:
    return None


__all__ = ["FakeDigitalTwinAdapter", "create_digital_twin_port"]
