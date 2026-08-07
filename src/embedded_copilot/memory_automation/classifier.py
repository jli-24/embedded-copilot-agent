from __future__ import annotations

import copy

from .contracts import MemorySourceKind, MemoryType, VersionMemoryInput


def classify_memory(value: VersionMemoryInput) -> MemoryType:
    if type(value) is not VersionMemoryInput:
        raise TypeError("version memory input must be a typed projection")
    checked = VersionMemoryInput.model_validate(copy.deepcopy(value))
    if checked.memory_type is not None:
        return checked.memory_type
    mapping = {
        MemorySourceKind.CONVERSATION_SUMMARY: MemoryType.CONVERSATION_SUMMARY,
        MemorySourceKind.USER_FEEDBACK: MemoryType.USER_FEEDBACK,
        MemorySourceKind.ENGINEERING_EVENT: MemoryType.ENGINEERING_EVENT,
        MemorySourceKind.BUILD_OBSERVATION: MemoryType.BUILD_OBSERVATION,
        MemorySourceKind.ENGINEERING_LOOP_RESULT: MemoryType.ENGINEERING_LOOP_RESULT,
        MemorySourceKind.DEBUG_ANALYSIS_RESULT: MemoryType.DEBUG_ANALYSIS_RESULT,
        MemorySourceKind.OPTIMIZATION_RESULT: MemoryType.OPTIMIZATION_RESULT,
        MemorySourceKind.FIRMWARE_ENGINEERING_RESULT: MemoryType.FIRMWARE_ENGINEERING_RESULT,
        MemorySourceKind.HIL_VALIDATION_RESULT: MemoryType.HIL_VALIDATION_RESULT,
        MemorySourceKind.OPTIMIZATION_ANALYSIS_RESULT: MemoryType.OPTIMIZATION_ANALYSIS_RESULT,
        MemorySourceKind.ENGINEERING_KNOWLEDGE_RESULT: MemoryType.ENGINEERING_KNOWLEDGE_RESULT,
    }
    return mapping.get(checked.source.source_type, MemoryType.CONVERSATION_SUMMARY)
