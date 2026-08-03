from .service import MemoryAutomationPort, MemoryAutomationService


def create_memory_automation() -> MemoryAutomationPort:
    return MemoryAutomationService()

