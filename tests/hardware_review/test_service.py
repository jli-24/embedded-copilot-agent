from embedded_copilot.hardware_design.adapters.fake import FakeKiCadAdapter
from embedded_copilot.hardware_design.contracts import HardwareSourceReference
from embedded_copilot.hardware_design.models import DesignSourceType
from embedded_copilot.hardware_review.service import HardwareReviewService


def test_review_service_projects_missing_component_identity() -> None:
    source = HardwareSourceReference.create(
        project_id="demo",
        design_id="design-1",
        filename="demo.kicad_pcb",
        source_type=DesignSourceType.KICAD,
    )
    findings = HardwareReviewService.review(FakeKiCadAdapter().parse(source))
    assert findings[0].category.value == "COMPONENT"
    assert findings[0].status.value == "PROJECTED"
