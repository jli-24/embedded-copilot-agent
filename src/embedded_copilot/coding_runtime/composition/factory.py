from __future__ import annotations

from embedded_copilot.coding_runtime.analysis import (
    DeterministicBuildAnalyzer,
    DeterministicCodingPort,
    DeterministicDiffAnalyzer,
    DeterministicFusionAnalyzer,
    DeterministicProjectAnalyzer,
    TreeSitterCodeParser,
)
from embedded_copilot.coding_runtime.facade import CodingRuntime


def create_coding_runtime() -> CodingRuntime:
    port = DeterministicCodingPort(
        TreeSitterCodeParser(),
        DeterministicProjectAnalyzer(),
        DeterministicBuildAnalyzer(),
        DeterministicDiffAnalyzer(),
        DeterministicFusionAnalyzer(),
    )
    return CodingRuntime._compose(port)
