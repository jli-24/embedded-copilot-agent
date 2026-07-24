from embedded_copilot.pcb import (
    KiCadPCBParser,
    PCBComponent,
    PCBNet,
    PCBParseError,
    PCBParser,
    PCBSourceResolver,
    PCBStructureEvidence,
    PCBStructureRuleEngine,
    RootedPCBSourceResolver,
    UnifiedPCBModel,
    attach_pcb_model,
)


def test_pcb_intelligence_foundation_public_imports() -> None:
    assert UnifiedPCBModel.__name__ == "UnifiedPCBModel"
    assert PCBComponent.__name__ == "PCBComponent"
    assert PCBNet.__name__ == "PCBNet"
    assert PCBParseError.__name__ == "PCBParseError"
    assert PCBStructureEvidence.__name__ == "PCBStructureEvidence"
    assert PCBParser.__name__ == "PCBParser"
    assert PCBSourceResolver.__name__ == "PCBSourceResolver"
    assert RootedPCBSourceResolver.__name__ == "RootedPCBSourceResolver"
    assert KiCadPCBParser.__name__ == "KiCadPCBParser"
    assert PCBStructureRuleEngine.__name__ == "PCBStructureRuleEngine"
    assert attach_pcb_model.__name__ == "attach_pcb_model"
