from .contracts import DebugAnalyzerPort
from .service import DebugAnalysisService


def create_debug_analysis_service(analyzer: DebugAnalyzerPort) -> DebugAnalysisService:
    return DebugAnalysisService(analyzer)


__all__ = ["create_debug_analysis_service"]
