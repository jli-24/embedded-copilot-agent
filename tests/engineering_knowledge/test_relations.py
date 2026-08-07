from embedded_copilot.engineering_knowledge import DeterministicRelationProjector


def test_relation_projector_has_no_implicit_relation_generation() -> None:
    assert DeterministicRelationProjector().project((), ()) == ()
