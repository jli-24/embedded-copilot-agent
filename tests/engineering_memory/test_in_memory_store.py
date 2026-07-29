import inspect

from embedded_copilot.engineering_memory import EngineeringMemoryStorePort
from embedded_copilot.engineering_memory.stores.in_memory import (
    InMemoryEngineeringMemoryStore,
)


def test_in_memory_store_satisfies_exact_domain_port() -> None:
    store = InMemoryEngineeringMemoryStore()
    assert isinstance(store, EngineeringMemoryStorePort)
    public = {
        name
        for name, member in type(store).__dict__.items()
        if callable(member) and not name.startswith("_")
    }
    assert public == {
        name
        for name, member in EngineeringMemoryStorePort.__dict__.items()
        if inspect.isfunction(member) and not name.startswith("_")
    }
    assert not any(
        hasattr(store, name)
        for name in ("save", "update", "delete", "clear", "truncate")
    )


def test_store_instances_and_returned_records_are_isolated() -> None:
    from .test_mutations import FP, _create, _read

    first = InMemoryEngineeringMemoryStore()
    second = InMemoryEngineeringMemoryStore()
    first.create_candidate(_create(), request_fingerprint=FP)
    snapshot = first.get_candidate_snapshot(_read())
    object.__setattr__(snapshot.records[0].payload, "board_name", "tampered")
    assert first.get_candidate_snapshot(_read()).records[0].payload.board_name == (
        "Board One"
    )
    assert second.get_candidate_snapshot(_read()).records == ()
