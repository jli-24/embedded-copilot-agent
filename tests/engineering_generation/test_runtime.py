from __future__ import annotations

import pytest

from embedded_copilot.engineering_generation import (
    ArtifactLifecycleState,
    ArtifactType,
    GenerationFailureCode,
    GenerationProgressUnavailable,
    GenerationVerificationStatus,
    GeneratorType,
    create_engineering_generation_runtime,
)

from .conftest import (
    RecordingApprovalPolicy,
    RecordingGenerator,
    RecordingProgressSink,
    RecordingVerifier,
    StaticRegistry,
    binding_for,
    proposal_for,
    request_for,
)


def _generator_type(artifact_type: ArtifactType) -> GeneratorType:
    return GeneratorType(artifact_type.value)


def _runtime(
    request, *, generator=None, registry=None, verifier=None, policy=None, sink=None
):
    selected_generator = generator or RecordingGenerator(proposal_for(request))
    selected_registry = registry or StaticRegistry(
        binding_for(
            selected_generator,
            generator_type=_generator_type(request.artifact_type),
        )
    )
    selected_verifier = verifier or RecordingVerifier()
    selected_policy = policy or RecordingApprovalPolicy()
    selected_sink = sink or RecordingProgressSink()
    runtime = create_engineering_generation_runtime(
        generator_registry=selected_registry,
        verification_port=selected_verifier,
        approval_policy=selected_policy,
        progress_sink=selected_sink,
    )
    return (
        runtime,
        selected_generator,
        selected_registry,
        selected_verifier,
        selected_policy,
        selected_sink,
    )


@pytest.mark.parametrize("artifact_type", tuple(ArtifactType))
def test_all_generation_types_reach_waiting_approval(artifact_type) -> None:
    request = request_for(artifact_type=artifact_type)
    runtime, generator, registry, verifier, policy, sink = _runtime(request)

    snapshot = runtime.generation_port().generate_artifact(request)

    assert snapshot.state is ArtifactLifecycleState.WAITING_APPROVAL
    assert snapshot.proposal is not None
    assert snapshot.proposal.artifact_type is artifact_type
    assert [event.state for event in sink.events] == [
        ArtifactLifecycleState.CREATED,
        ArtifactLifecycleState.GENERATING,
        ArtifactLifecycleState.VERIFYING,
        ArtifactLifecycleState.WAITING_APPROVAL,
    ]
    assert len(generator.calls) == len(registry.calls) == len(verifier.calls) == 1
    assert policy.calls == []
    assert snapshot.request is not request


def test_unknown_generator_and_registry_failure_do_not_fallback(
    generation_request,
) -> None:
    for registry in (
        StaticRegistry(binding=None),
        StaticRegistry(error=RuntimeError("database unavailable")),
    ):
        runtime, generator, _, verifier, policy, _ = _runtime(
            generation_request,
            registry=registry,
        )

        snapshot = runtime.generation_port().generate_artifact(generation_request)

        assert snapshot.state is ArtifactLifecycleState.FAILED
        assert snapshot.failure_code is GenerationFailureCode.GENERATOR_UNAVAILABLE
        assert generator.calls == []
        assert verifier.calls == []
        assert policy.calls == []


@pytest.mark.parametrize(
    ("error", "failure"),
    (
        (RuntimeError("provider secret"), GenerationFailureCode.GENERATOR_UNAVAILABLE),
        (TimeoutError("transport path"), GenerationFailureCode.GENERATION_TIMEOUT),
    ),
)
def test_generator_failures_are_sanitized(generation_request, error, failure) -> None:
    generator = RecordingGenerator(error=error)
    runtime, *_ = _runtime(generation_request, generator=generator)

    snapshot = runtime.generation_port().generate_artifact(generation_request)

    assert snapshot.state is ArtifactLifecycleState.FAILED
    assert snapshot.failure_code is failure
    assert "secret" not in snapshot.model_dump_json()
    assert "path" not in snapshot.model_dump_json()


def test_untyped_generator_output_fails_closed(generation_request) -> None:
    generator = RecordingGenerator({"summary": "unsafe", "raw_output": "payload"})
    runtime, _, _, verifier, _, _ = _runtime(generation_request, generator=generator)

    snapshot = runtime.generation_port().generate_artifact(generation_request)

    assert snapshot.state is ArtifactLifecycleState.FAILED
    assert snapshot.failure_code is GenerationFailureCode.PROPOSAL_REJECTED
    assert verifier.calls == []


def test_invalid_verification_rejects_proposal(generation_request) -> None:
    verifier = RecordingVerifier(status=GenerationVerificationStatus.INVALID)
    runtime, *_ = _runtime(generation_request, verifier=verifier)

    snapshot = runtime.generation_port().generate_artifact(generation_request)

    assert snapshot.state is ArtifactLifecycleState.REJECTED
    assert snapshot.failure_code is GenerationFailureCode.VERIFICATION_INVALID
    assert snapshot.proposal is None


def test_progress_failure_stops_before_downstream_calls(generation_request) -> None:
    sink = RecordingProgressSink(fail_at=2)
    runtime, generator, registry, verifier, _, _ = _runtime(
        generation_request, sink=sink
    )

    with pytest.raises(GenerationProgressUnavailable):
        runtime.generation_port().generate_artifact(generation_request)

    assert len(registry.calls) == 1
    assert generator.calls == []
    assert verifier.calls == []
