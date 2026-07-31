from __future__ import annotations

import copy

from embedded_copilot.datasheet_runtime import DatasheetIntelligencePort
from embedded_copilot.knowledge.intelligence.facade import (
    KnowledgeIntelligenceRuntime,
)
from embedded_copilot.knowledge.intelligence.models import SourceTrustCatalog
from embedded_copilot.knowledge.intelligence.ports import WebResearchSourcePort
from embedded_copilot.knowledge.intelligence.runtime import (
    _KnowledgeIntelligenceService,
)
from embedded_copilot.knowledge.intelligence.verification.service import (
    DeterministicKnowledgeVerifier,
)


def create_knowledge_intelligence_runtime(
    *,
    trust_catalog: SourceTrustCatalog,
    web_source: WebResearchSourcePort | None = None,
    datasheet_port: DatasheetIntelligencePort | None = None,
) -> KnowledgeIntelligenceRuntime:
    if not isinstance(trust_catalog, SourceTrustCatalog):
        raise TypeError("trust_catalog must be a SourceTrustCatalog")
    if web_source is not None and not isinstance(web_source, WebResearchSourcePort):
        raise TypeError("web_source must satisfy WebResearchSourcePort")
    if datasheet_port is not None and not isinstance(
        datasheet_port, DatasheetIntelligencePort
    ):
        raise TypeError("datasheet_port must satisfy DatasheetIntelligencePort")
    checked_catalog = SourceTrustCatalog.model_validate(copy.deepcopy(trust_catalog))
    verifier = DeterministicKnowledgeVerifier(checked_catalog)
    service = _KnowledgeIntelligenceService(
        web_source=web_source,
        datasheet_port=datasheet_port,
        verification_port=verifier,
    )
    return KnowledgeIntelligenceRuntime._compose(service)
