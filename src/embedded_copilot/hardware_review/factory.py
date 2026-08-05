from __future__ import annotations

from .service import HardwareReviewService


def create_hardware_review_service(port) -> HardwareReviewService:
    return HardwareReviewService(port)


__all__ = ["create_hardware_review_service"]
