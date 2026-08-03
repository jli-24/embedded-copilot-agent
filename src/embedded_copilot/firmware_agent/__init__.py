"""Public Firmware Agent API."""

from embedded_copilot.firmware_agent.contracts import FirmwareAgentPort
from embedded_copilot.firmware_agent.exceptions import (
    FirmwareAgentError,
    FirmwareGenerationRejected,
)
from embedded_copilot.firmware_agent.facade import FirmwareAgent
from embedded_copilot.firmware_agent.factory import create_firmware_agent
from embedded_copilot.firmware_agent.models import (
    FirmwareArtifactProjection,
    FirmwareArtifactType,
    FirmwareGenerationRequest,
    FirmwarePlatform,
    FirmwareProposal,
    FirmwareSourceFile,
    canonical_firmware_json,
    firmware_artifact_fingerprint,
    firmware_generation_request_fingerprint,
    firmware_proposal_fingerprint,
    firmware_source_file_fingerprint,
)

__all__ = (
    "FirmwareAgent",
    "FirmwareAgentError",
    "FirmwareAgentPort",
    "FirmwareArtifactProjection",
    "FirmwareArtifactType",
    "FirmwareGenerationRejected",
    "FirmwareGenerationRequest",
    "FirmwarePlatform",
    "FirmwareProposal",
    "FirmwareSourceFile",
    "canonical_firmware_json",
    "create_firmware_agent",
    "firmware_artifact_fingerprint",
    "firmware_generation_request_fingerprint",
    "firmware_proposal_fingerprint",
    "firmware_source_file_fingerprint",
)
