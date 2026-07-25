from __future__ import annotations

from pathlib import Path

from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.firmware.review.models import FirmwareReviewResult


_REDACTED_CONTENT = "Source content redacted."


class FirmwareReviewProjectAdapter:
    def to_project(self, review: FirmwareReviewResult) -> FirmwareProject:
        if not isinstance(review, FirmwareReviewResult):
            raise TypeError("firmware review result is invalid")
        files = [
            ProjectFile(
                path=filename,
                content=_REDACTED_CONTENT,
                language=_language(filename),
            )
            for filename in review.files
        ]
        structure = [
            *(f"Entrypoint: {entry}" for entry in review.entrypoints),
            *(f"Architecture: {flow}" for flow in review.initialization_flow),
            *(
                f"[{item.severity.upper()}] {item.rule_id}: {item.description} "
                f"Recommendation: {item.recommendation} "
                f"[source_id: {item.source_ids[0]}]"
                for item in review.findings
            ),
            *(f"Limitation: {item}" for item in review.limitations),
        ]
        return FirmwareProject(
            name="firmware_review",
            platform=review.platform or "Unknown",
            framework=review.framework,
            files=files,
            structure=structure,
            metadata={
                "analysis_mode": "deterministic_static_review",
                "file_count": len(review.files),
                "finding_count": len(review.findings),
                "peripherals": list(review.peripherals),
                "source_ids": list(review.source_ids),
            },
        )


def _language(filename: str) -> str:
    suffix = Path(filename).suffix.casefold()
    return {
        ".c": "C",
        ".h": "C Header",
        ".cc": "C++",
        ".cpp": "C++",
        ".cxx": "C++",
        ".hpp": "C++ Header",
    }.get(suffix, "Text")
