from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.hardware_design.adapters.fake import FakeKiCadAdapter
from embedded_copilot.hardware_design.contracts import HardwareSourceReference
from embedded_copilot.hardware_design.models import DesignSourceType
from embedded_copilot.hardware_review.adapters.fake import FakeHardwareReviewPort
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _DesignPort:
    def __init__(self):
        self.calls = 0

    def get_snapshot(self, project_id):
        self.calls += 1
        source = HardwareSourceReference.create(
            project_id=project_id,
            design_id="design-1",
            filename="demo.kicad_pcb",
            source_type=DesignSourceType.KICAD,
        )
        return FakeKiCadAdapter().parse(source)


def test_v22_routes_return_verified_projections_once() -> None:
    design = _DesignPort()
    review = FakeHardwareReviewPort()
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        hardware_design_port=design,
        hardware_review_port=review,
    )
    with TestClient(app) as client:
        design_response = client.get("/api/hardware/v22/design/demo")
        review_response = client.get("/api/hardware/v22/review/demo")
    assert design_response.status_code == 200
    assert design_response.json()["design_source_type"] == "KICAD"
    assert review_response.status_code == 200
    assert review_response.json()[0]["category"] == "COMPONENT"
    assert design.calls == 1


def test_v22_routes_are_safe_without_ports() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/hardware/v22/design/demo").json() == {
            "error": "HARDWARE_UNAVAILABLE"
        }
        assert client.get("/api/hardware/v22/review/demo").json() == {
            "error": "REVIEW_UNAVAILABLE"
        }
