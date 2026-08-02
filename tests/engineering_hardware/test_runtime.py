from __future__ import annotations

from copy import deepcopy

import pytest

from embedded_copilot.engineering_hardware import (
    ComponentSelectionStatus,
    HardwareEngineeringRejected,
    HardwareEngineeringRequest,
    create_engineering_hardware_runtime,
)

from .conftest import NOW


def _request(snapshot) -> HardwareEngineeringRequest:
    return HardwareEngineeringRequest(
        proposal_id="proposal-1",
        requirement=snapshot.requirement,
        plan=snapshot.plan,
        context=snapshot.context,
        proposed_at=NOW,
    )


def test_complete_hardware_proposal_contains_eight_review_only_sections(
    intelligence_snapshot,
) -> None:
    port = create_engineering_hardware_runtime().hardware_engineering_port()
    proposal = port.prepare_proposal(_request(intelligence_snapshot))

    assert proposal.candidate_semantics == "unverified"
    assert proposal.review_required is True
    assert proposal.architecture.blocks
    assert proposal.component_selection.items
    assert proposal.interface_contracts.contracts
    assert proposal.power_design.requirements == ("LOW_POWER_OPERATION",)
    assert proposal.bom.items
    assert proposal.schematic_intent.component_references
    assert proposal.pcb_constraints.constraints
    assert proposal.review.review_required is True


def test_component_selection_and_bom_use_only_explicit_constraints(
    intelligence_snapshot,
) -> None:
    proposal = (
        create_engineering_hardware_runtime()
        .hardware_engineering_port()
        .prepare_proposal(_request(intelligence_snapshot))
    )
    selections = {
        (item.requirement_key, item.candidate): item
        for item in proposal.component_selection.items
    }

    assert set(selections) == {("CAMERA", "OV2640"), ("MCU", "ESP32-S3")}
    assert selections[("MCU", "ESP32-S3")].status is ComponentSelectionStatus.SUPPORTED
    assert selections[("MCU", "ESP32-S3")].evidence_ids == ("evidence-mcu",)
    assert (
        selections[("CAMERA", "OV2640")].status is ComponentSelectionStatus.UNVERIFIED
    )
    assert selections[("CAMERA", "OV2640")].evidence_ids == ()
    assert tuple(item.candidate for item in proposal.bom.items) == (
        "OV2640",
        "ESP32-S3",
    )
    assert all(item.quantity is None for item in proposal.bom.items)
    assert all(item.manufacturer is None for item in proposal.bom.items)
    assert all(item.unit_cost is None for item in proposal.bom.items)


def test_interface_power_schematic_and_pcb_do_not_invent_engineering_facts(
    intelligence_snapshot,
) -> None:
    proposal = (
        create_engineering_hardware_runtime()
        .hardware_engineering_port()
        .prepare_proposal(_request(intelligence_snapshot))
    )
    interface = proposal.interface_contracts.contracts[0]

    assert interface.protocol == "WIFI"
    assert interface.consumer_reference is None
    assert interface.electrical_standard is None
    assert interface.pin_bindings == ()
    assert proposal.power_design.input_voltage is None
    assert proposal.power_design.current_budget is None
    assert proposal.power_design.margin_percent is None
    assert proposal.schematic_intent.net_intents == ()
    serialized = proposal.model_dump_json().casefold()
    for forbidden in (
        "kicad",
        "altium",
        "easyeda",
        "footprint",
        "coordinate",
        "trace_width",
        "pin_mapping",
        "hardware-tested",
    ):
        assert forbidden not in serialized


def test_runtime_is_stateless_and_does_not_modify_inputs(intelligence_snapshot) -> None:
    runtime = create_engineering_hardware_runtime()
    port = runtime.hardware_engineering_port()
    request = _request(intelligence_snapshot)
    before = deepcopy(request.model_dump(mode="json"))

    first = port.prepare_proposal(request)
    second = port.prepare_proposal(request)

    assert first == second
    assert request.model_dump(mode="json") == before
    assert runtime.hardware_engineering_port() is port
    for forbidden in ("settings", "config", "catalog", "session", "agent"):
        assert not hasattr(runtime, forbidden)


def test_runtime_rejects_untyped_request_without_leaking_input(
    intelligence_snapshot,
) -> None:
    port = create_engineering_hardware_runtime().hardware_engineering_port()

    with pytest.raises(
        HardwareEngineeringRejected,
        match="^hardware engineering request rejected$",
    ):
        port.prepare_proposal(  # type: ignore[arg-type]
            _request(intelligence_snapshot).model_dump(mode="python")
        )


def test_proposal_is_identical_across_one_hundred_calls(
    intelligence_snapshot,
) -> None:
    port = create_engineering_hardware_runtime().hardware_engineering_port()
    request = _request(intelligence_snapshot)
    proposals = tuple(port.prepare_proposal(request) for _ in range(100))

    assert all(proposal == proposals[0] for proposal in proposals)
    assert {proposal.fingerprint for proposal in proposals} == {
        proposals[0].fingerprint
    }
