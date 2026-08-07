from __future__ import annotations

from .models import MemoryType


_SIGNALS = (
    (MemoryType.REQUIREMENT, ("requirement", "需求", "must", "必须")),
    (MemoryType.ARCHITECTURE, ("architecture", "架构", "boundary", "边界")),
    (MemoryType.DEBUG_EXPERIENCE, ("debug", "error", "fault", "故障", "错误")),
    (MemoryType.OPTIMIZATION, ("optimiz", "performance", "性能", "优化")),
    (MemoryType.VALIDATION, ("validation", "verify", "验证", "测试通过")),
    (MemoryType.DECISION, ("decide", "decision", "选择", "决定", "采用")),
)


def classify(text: str) -> MemoryType | None:
    lowered = text.casefold()
    for memory_type, signals in _SIGNALS:
        if any(signal.casefold() in lowered for signal in signals):
            return memory_type
    return None


__all__ = ["classify"]
