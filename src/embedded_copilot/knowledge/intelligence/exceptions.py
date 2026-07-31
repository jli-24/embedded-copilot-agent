class KnowledgeIntelligenceError(RuntimeError):
    """Base error for the read-only knowledge intelligence boundary."""


class KnowledgeSourceUnavailable(KnowledgeIntelligenceError):
    def __init__(self) -> None:
        super().__init__("knowledge source unavailable")


class KnowledgeObservationTimeout(KnowledgeIntelligenceError):
    def __init__(self) -> None:
        super().__init__("knowledge observation timed out")


class KnowledgeDataRejected(KnowledgeIntelligenceError):
    def __init__(self) -> None:
        super().__init__("knowledge data rejected")


class KnowledgeGraphRejected(KnowledgeIntelligenceError):
    def __init__(self) -> None:
        super().__init__("knowledge graph projection rejected")


class KnowledgeMemoryBridgeRejected(KnowledgeIntelligenceError):
    def __init__(self) -> None:
        super().__init__("knowledge memory projection rejected")
