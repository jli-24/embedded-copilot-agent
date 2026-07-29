from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from embedded_copilot.engineering_memory import MemoryRevisionConflict
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)
from embedded_copilot.verification_agent import VerificationStatus

from .test_mutations import _create
from .test_state_transitions import _verification


def _race(*operations):
    barrier = Barrier(len(operations))

    def run(operation):
        barrier.wait()
        try:
            return operation()
        except Exception as error:  # noqa: BLE001
            return error

    with ThreadPoolExecutor(max_workers=len(operations)) as executor:
        return tuple(executor.map(run, operations))


def test_two_writes_at_same_revision_have_exactly_one_success() -> None:
    store = InMemoryEngineeringMemoryStore()
    outcomes = _race(
        lambda: store.create_candidate(
            _create(), request_fingerprint="sha256:" + "a" * 64
        ),
        lambda: store.create_candidate(
            _create(
                request_id="req-2",
                operation_id="op-2",
                record_id="record-2",
            ),
            request_fingerprint="sha256:" + "b" * 64,
        ),
    )
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert sum(isinstance(item, MemoryRevisionConflict) for item in outcomes) == 1


def test_concurrent_activation_has_one_winner_and_no_partial_state() -> None:
    store = InMemoryEngineeringMemoryStore()
    from .test_state_transitions import _create as create_decision

    store.create_candidate(create_decision(), request_fingerprint="sha256:" + "a" * 64)
    outcomes = _race(
        lambda: store.apply_verification(
            _verification(VerificationStatus.PASS, operation_id="verify-op-a"),
            request_fingerprint="sha256:" + "b" * 64,
        ),
        lambda: store.apply_verification(
            _verification(VerificationStatus.PASS, operation_id="verify-op-b"),
            request_fingerprint="sha256:" + "c" * 64,
        ),
    )
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert sum(isinstance(item, MemoryRevisionConflict) for item in outcomes) == 1


def test_concurrent_replacement_activation_has_one_atomic_winner() -> None:
    from embedded_copilot.engineering_memory import (
        CreateReplacementCandidateRequest,
        EngineeringDecisionMemory,
        MemoryStatus,
    )

    from .test_state_transitions import NOW, _history, _provenance
    from .test_state_transitions import _create as create_decision

    store = InMemoryEngineeringMemoryStore()
    store.create_candidate(create_decision(), request_fingerprint="sha256:" + "a" * 64)
    store.apply_verification(
        _verification(VerificationStatus.PASS),
        request_fingerprint="sha256:" + "b" * 64,
    )
    store.create_replacement_candidate(
        CreateReplacementCandidateRequest(
            request_id="replace-1",
            operation_id="replace-op-1",
            project_id="project-1",
            memory_id="memory-1",
            caller="caller-1",
            requested_at=NOW,
            expected_revision=2,
            record_id="record-2",
            payload=EngineeringDecisionMemory(
                decision_topic="rtos-choice",
                decision="Use Zephyr",
                rationale_summary="Updated portability requirement",
            ),
            provenance=_provenance(),
            supersedes_record_id="record-1",
        ),
        request_fingerprint="sha256:" + "c" * 64,
    )
    outcomes = _race(
        lambda: store.apply_verification(
            _verification(
                VerificationStatus.PASS,
                record_id="record-2",
                expected_revision=3,
                operation_id="activate-a",
            ),
            request_fingerprint="sha256:" + "d" * 64,
        ),
        lambda: store.apply_verification(
            _verification(
                VerificationStatus.PASS,
                record_id="record-2",
                expected_revision=3,
                operation_id="activate-b",
            ),
            request_fingerprint="sha256:" + "e" * 64,
        ),
    )
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert sum(isinstance(item, MemoryRevisionConflict) for item in outcomes) == 1
    records = {record.record_id: record for record in _history(store).records}
    assert records["record-1"].status is MemoryStatus.SUPERSEDED
    assert records["record-2"].status is MemoryStatus.VERIFIED
