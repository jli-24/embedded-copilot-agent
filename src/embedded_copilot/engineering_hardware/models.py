"""Immutable proposal-only contracts for Hardware Engineering."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_HTTPS_REFERENCE = re.compile(r"^https://[^\s/@:]+(?::[0-9]{1,5})?(?:/[^\s]*)?$")
_ABSOLUTE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])",
    re.IGNORECASE,
)


class _HardwareContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 256) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not candidate or len(candidate) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise ValueError(f"{field} is invalid")
    if _ABSOLUTE_PATH.search(candidate) or _SENSITIVE.search(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _reference(value: object) -> str:
    if type(value) is not str:
        raise ValueError("reference is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is not None:
        return candidate
    if (
        _HTTPS_REFERENCE.fullmatch(candidate) is not None
        and "?" not in candidate
        and "#" not in candidate
    ):
        return candidate
    raise ValueError("reference is invalid")


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _identifiers(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_identifier(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _tokens(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_token(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _references(value: object) -> tuple[str, ...]:
    values = _tuple(value, field="reference_ids")
    checked = tuple(_reference(item) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError("reference_ids must be sorted and unique")
    return checked


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        encoded = value.astimezone(UTC).isoformat()
        return f"{encoded[:-6]}Z"
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class ComponentSelectionStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"


class InterfaceContractStatus(StrEnum):
    UNRESOLVED = "UNRESOLVED"


class HardwareProposalItemStatus(StrEnum):
    PROPOSED = "PROPOSED"
    UNRESOLVED = "UNRESOLVED"


class PCBConstraintCategory(StrEnum):
    PLACEMENT = "PLACEMENT"
    POWER_DISTRIBUTION = "POWER_DISTRIBUTION"
    GROUND_RETURN = "GROUND_RETURN"
    INTERFACE_ROUTING = "INTERFACE_ROUTING"


class HardwareFindingSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    REVIEW = "REVIEW"


class HardwareFindingCode(StrEnum):
    CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
    VERIFIED_EVIDENCE_CONFLICT = "VERIFIED_EVIDENCE_CONFLICT"
    REQUIREMENT_EVIDENCE_CONFLICT = "REQUIREMENT_EVIDENCE_CONFLICT"
    COMPONENT_UNRESOLVED = "COMPONENT_UNRESOLVED"
    INTERFACE_BINDING_UNRESOLVED = "INTERFACE_BINDING_UNRESOLVED"
    POWER_BUDGET_UNKNOWN = "POWER_BUDGET_UNKNOWN"


class HardwareEvidenceTrace(_HardwareContract):
    evidence_id: str
    source_type: str
    reference_ids: tuple[str, ...]
    source_fingerprint: str

    _evidence_id = field_validator("evidence_id")(
        lambda value: _identifier(value, field="evidence_id")
    )
    _source_type = field_validator("source_type")(
        lambda value: _token(value, field="source_type")
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _source_fingerprint = field_validator("source_fingerprint")(_fingerprint_value)


class SystemArchitectureBlock(_HardwareContract):
    block_id: str
    block_type: str
    label: str
    component_reference: str | None = None
    evidence_ids: tuple[str, ...] = ()

    _block_id = field_validator("block_id")(
        lambda value: _identifier(value, field="block_id")
    )
    _block_type = field_validator("block_type")(
        lambda value: _token(value, field="block_type")
    )
    _label = field_validator("label")(
        lambda value: _safe_text(value, field="label", maximum=128)
    )

    @field_validator("component_reference")
    @classmethod
    def validate_component_reference(cls, value: object) -> str | None:
        if value is None:
            return None
        return _identifier(value, field="component_reference")

    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


class SystemArchitectureRelation(_HardwareContract):
    source_block_id: str
    target_block_id: str
    relation_type: Literal["SYSTEM_CONTAINS_COMPONENT"]

    @field_validator("source_block_id", "target_block_id")
    @classmethod
    def validate_block_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)


def system_architecture_fingerprint(
    *,
    product: str,
    capabilities: tuple[str, ...],
    blocks: tuple[SystemArchitectureBlock, ...],
    relations: tuple[SystemArchitectureRelation, ...],
) -> str:
    return _fingerprint(
        {
            "product": product,
            "capabilities": capabilities,
            "blocks": blocks,
            "relations": relations,
        }
    )


class SystemArchitectureProposal(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    product: str
    capabilities: tuple[str, ...]
    blocks: tuple[SystemArchitectureBlock, ...]
    relations: tuple[SystemArchitectureRelation, ...]
    fingerprint: str

    _product = field_validator("product")(lambda value: _token(value, field="product"))
    _capabilities = field_validator("capabilities", mode="before")(
        lambda value: _tokens(value, field="capabilities")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("blocks", "relations", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_projection(self) -> SystemArchitectureProposal:
        block_ids = tuple(item.block_id for item in self.blocks)
        if block_ids != tuple(sorted(block_ids)) or len(block_ids) != len(
            set(block_ids)
        ):
            raise ValueError("architecture blocks must be sorted and unique")
        relation_keys = tuple(
            (item.source_block_id, item.target_block_id, item.relation_type)
            for item in self.relations
        )
        if relation_keys != tuple(sorted(relation_keys)) or len(relation_keys) != len(
            set(relation_keys)
        ):
            raise ValueError("architecture relations must be sorted and unique")
        if any(
            item.source_block_id not in block_ids
            or item.target_block_id not in block_ids
            for item in self.relations
        ):
            raise ValueError("architecture relation binding is invalid")
        expected = system_architecture_fingerprint(
            product=self.product,
            capabilities=self.capabilities,
            blocks=self.blocks,
            relations=self.relations,
        )
        if self.fingerprint != expected:
            raise ValueError("architecture fingerprint mismatch")
        return self


class ComponentSelectionItem(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    component_reference: str
    requirement_key: str
    candidate: str
    status: ComponentSelectionStatus
    evidence_ids: tuple[str, ...]

    _component_reference = field_validator("component_reference")(
        lambda value: _identifier(value, field="component_reference")
    )
    _requirement_key = field_validator("requirement_key")(
        lambda value: _token(value, field="requirement_key")
    )
    _candidate = field_validator("candidate")(
        lambda value: _safe_text(value, field="candidate", maximum=128)
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


def component_selection_fingerprint(
    *, items: tuple[ComponentSelectionItem, ...]
) -> str:
    return _fingerprint({"items": items})


class ComponentSelectionProposal(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    items: tuple[ComponentSelectionItem, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("items", mode="before")
    @classmethod
    def validate_items_tuple(cls, value: object) -> object:
        return _tuple(value, field="items")

    @model_validator(mode="after")
    def validate_projection(self) -> ComponentSelectionProposal:
        keys = tuple((item.requirement_key, item.candidate) for item in self.items)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("component selections must be sorted and unique")
        if self.fingerprint != component_selection_fingerprint(items=self.items):
            raise ValueError("component selection fingerprint mismatch")
        return self


class InterfaceContract(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    interface_id: str
    protocol: str
    provider_component_reference: str | None = None
    consumer_reference: None = None
    electrical_standard: None = None
    pin_bindings: tuple[str, ...] = ()
    status: Literal[InterfaceContractStatus.UNRESOLVED] = (
        InterfaceContractStatus.UNRESOLVED
    )
    evidence_ids: tuple[str, ...] = ()

    _interface_id = field_validator("interface_id")(
        lambda value: _identifier(value, field="interface_id")
    )
    _protocol = field_validator("protocol")(
        lambda value: _token(value, field="protocol")
    )

    @field_validator("provider_component_reference")
    @classmethod
    def validate_provider_reference(cls, value: object) -> str | None:
        if value is None:
            return None
        return _identifier(value, field="provider_component_reference")

    @field_validator("pin_bindings", mode="before")
    @classmethod
    def validate_no_pin_bindings(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="pin_bindings")
        if values:
            raise ValueError("pin bindings remain unresolved")
        return ()

    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


def interface_contracts_fingerprint(*, contracts: tuple[InterfaceContract, ...]) -> str:
    return _fingerprint({"contracts": contracts})


class InterfaceContractProposal(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    contracts: tuple[InterfaceContract, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("contracts", mode="before")
    @classmethod
    def validate_contract_tuple(cls, value: object) -> object:
        return _tuple(value, field="contracts")

    @model_validator(mode="after")
    def validate_projection(self) -> InterfaceContractProposal:
        keys = tuple(item.interface_id for item in self.contracts)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("interface contracts must be sorted and unique")
        if self.fingerprint != interface_contracts_fingerprint(
            contracts=self.contracts
        ):
            raise ValueError("interface contract fingerprint mismatch")
        return self


def power_design_fingerprint(
    *,
    requirements: tuple[str, ...],
    consumer_references: tuple[str, ...],
    input_voltage: None,
    current_budget: None,
    margin_percent: None,
    evidence_ids: tuple[str, ...],
) -> str:
    return _fingerprint(
        {
            "requirements": requirements,
            "consumer_references": consumer_references,
            "input_voltage": input_voltage,
            "current_budget": current_budget,
            "margin_percent": margin_percent,
            "evidence_ids": evidence_ids,
        }
    )


class PowerDesignProposal(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    requirements: tuple[str, ...]
    consumer_references: tuple[str, ...]
    input_voltage: None = None
    current_budget: None = None
    margin_percent: None = None
    evidence_ids: tuple[str, ...] = ()
    fingerprint: str

    _requirements = field_validator("requirements", mode="before")(
        lambda value: _tokens(value, field="requirements")
    )
    _consumer_references = field_validator("consumer_references", mode="before")(
        lambda value: _identifiers(value, field="consumer_references")
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_projection(self) -> PowerDesignProposal:
        expected = power_design_fingerprint(
            requirements=self.requirements,
            consumer_references=self.consumer_references,
            input_voltage=self.input_voltage,
            current_budget=self.current_budget,
            margin_percent=self.margin_percent,
            evidence_ids=self.evidence_ids,
        )
        if self.fingerprint != expected:
            raise ValueError("power design fingerprint mismatch")
        return self


class BOMLineItem(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    line_id: str
    component_reference: str
    requirement_key: str
    candidate: str
    quantity: None = None
    manufacturer: None = None
    alternative: None = None
    unit_cost: None = None
    supply_risk: Literal["UNKNOWN"] = "UNKNOWN"
    evidence_ids: tuple[str, ...] = ()

    @field_validator("line_id", "component_reference")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_key = field_validator("requirement_key")(
        lambda value: _token(value, field="requirement_key")
    )
    _candidate = field_validator("candidate")(
        lambda value: _safe_text(value, field="candidate", maximum=128)
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


def bom_fingerprint(*, items: tuple[BOMLineItem, ...]) -> str:
    return _fingerprint({"items": items})


class BOMProposal(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    items: tuple[BOMLineItem, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("items", mode="before")
    @classmethod
    def validate_item_tuple(cls, value: object) -> object:
        return _tuple(value, field="items")

    @model_validator(mode="after")
    def validate_projection(self) -> BOMProposal:
        keys = tuple(item.line_id for item in self.items)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("BOM items must be sorted and unique")
        if self.fingerprint != bom_fingerprint(items=self.items):
            raise ValueError("BOM fingerprint mismatch")
        return self


def schematic_intent_fingerprint(
    *,
    component_references: tuple[str, ...],
    interface_references: tuple[str, ...],
    power_requirement_references: tuple[str, ...],
    net_intents: tuple[str, ...],
) -> str:
    return _fingerprint(
        {
            "component_references": component_references,
            "interface_references": interface_references,
            "power_requirement_references": power_requirement_references,
            "net_intents": net_intents,
        }
    )


class SchematicIntentModel(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    component_references: tuple[str, ...]
    interface_references: tuple[str, ...]
    power_requirement_references: tuple[str, ...]
    net_intents: tuple[str, ...] = ()
    fingerprint: str

    _component_references = field_validator("component_references", mode="before")(
        lambda value: _identifiers(value, field="component_references")
    )
    _interface_references = field_validator("interface_references", mode="before")(
        lambda value: _identifiers(value, field="interface_references")
    )
    _power_references = field_validator("power_requirement_references", mode="before")(
        lambda value: _tokens(value, field="power_requirement_references")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("net_intents", mode="before")
    @classmethod
    def validate_no_generated_nets(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="net_intents")
        if values:
            raise ValueError("net intents remain unresolved")
        return ()

    @model_validator(mode="after")
    def validate_projection(self) -> SchematicIntentModel:
        expected = schematic_intent_fingerprint(
            component_references=self.component_references,
            interface_references=self.interface_references,
            power_requirement_references=self.power_requirement_references,
            net_intents=self.net_intents,
        )
        if self.fingerprint != expected:
            raise ValueError("schematic intent fingerprint mismatch")
        return self


class PCBConstraint(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    constraint_id: str
    category: PCBConstraintCategory
    subject_reference: str
    rule_code: str
    status: Literal[HardwareProposalItemStatus.PROPOSED] = (
        HardwareProposalItemStatus.PROPOSED
    )
    evidence_ids: tuple[str, ...] = ()

    _constraint_id = field_validator("constraint_id")(
        lambda value: _identifier(value, field="constraint_id")
    )
    _subject_reference = field_validator("subject_reference")(
        lambda value: _identifier(value, field="subject_reference")
    )
    _rule_code = field_validator("rule_code")(
        lambda value: _token(value, field="rule_code")
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


def pcb_constraints_fingerprint(*, constraints: tuple[PCBConstraint, ...]) -> str:
    return _fingerprint({"constraints": constraints})


class PCBConstraintProposal(_HardwareContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    constraints: tuple[PCBConstraint, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("constraints", mode="before")
    @classmethod
    def validate_constraint_tuple(cls, value: object) -> object:
        return _tuple(value, field="constraints")

    @model_validator(mode="after")
    def validate_projection(self) -> PCBConstraintProposal:
        keys = tuple(item.constraint_id for item in self.constraints)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("PCB constraints must be sorted and unique")
        if self.fingerprint != pcb_constraints_fingerprint(
            constraints=self.constraints
        ):
            raise ValueError("PCB constraint fingerprint mismatch")
        return self


class HardwareReviewFinding(_HardwareContract):
    code: HardwareFindingCode
    severity: HardwareFindingSeverity
    subject_reference: str
    evidence_ids: tuple[str, ...] = ()

    _subject_reference = field_validator("subject_reference")(
        lambda value: _identifier(value, field="subject_reference")
    )
    _evidence_ids = field_validator("evidence_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_ids")
    )


def hardware_review_fingerprint(
    *,
    proposal_id: str,
    requirement_fingerprint: str,
    plan_fingerprint: str,
    context_fingerprint: str,
    component_count: int,
    interface_count: int,
    bom_item_count: int,
    evidence_count: int,
    findings: tuple[HardwareReviewFinding, ...],
    finding_codes: tuple[HardwareFindingCode, ...],
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "proposal_id": proposal_id,
            "requirement_fingerprint": requirement_fingerprint,
            "plan_fingerprint": plan_fingerprint,
            "context_fingerprint": context_fingerprint,
            "component_count": component_count,
            "interface_count": interface_count,
            "bom_item_count": bom_item_count,
            "evidence_count": evidence_count,
            "findings": findings,
            "finding_codes": finding_codes,
            "review_required": review_required,
        }
    )


class HardwareDesignReviewProjection(_HardwareContract):
    proposal_id: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    component_count: int = Field(ge=0)
    interface_count: int = Field(ge=0)
    bom_item_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    findings: tuple[HardwareReviewFinding, ...]
    finding_codes: tuple[HardwareFindingCode, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_fingerprint_value)
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator(
        "component_count", "interface_count", "bom_item_count", "evidence_count"
    )
    @classmethod
    def validate_counts(cls, value: int, info) -> int:
        if type(value) is not int or value < 0:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("findings", "finding_codes", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_projection(self) -> HardwareDesignReviewProjection:
        finding_keys = tuple(
            (item.code.value, item.subject_reference) for item in self.findings
        )
        if finding_keys != tuple(sorted(finding_keys)) or len(finding_keys) != len(
            set(finding_keys)
        ):
            raise ValueError("review findings must be sorted and unique")
        expected_codes = tuple(
            sorted({item.code for item in self.findings}, key=lambda item: item.value)
        )
        if self.finding_codes != expected_codes:
            raise ValueError("review finding codes are invalid")
        expected = hardware_review_fingerprint(
            proposal_id=self.proposal_id,
            requirement_fingerprint=self.requirement_fingerprint,
            plan_fingerprint=self.plan_fingerprint,
            context_fingerprint=self.context_fingerprint,
            component_count=self.component_count,
            interface_count=self.interface_count,
            bom_item_count=self.bom_item_count,
            evidence_count=self.evidence_count,
            findings=self.findings,
            finding_codes=self.finding_codes,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("review fingerprint mismatch")
        return self


def hardware_engineering_proposal_fingerprint(
    *,
    proposal_id: str,
    project_id: str,
    requirement_fingerprint: str,
    plan_fingerprint: str,
    context_fingerprint: str,
    architecture: SystemArchitectureProposal,
    component_selection: ComponentSelectionProposal,
    interface_contracts: InterfaceContractProposal,
    power_design: PowerDesignProposal,
    bom: BOMProposal,
    schematic_intent: SchematicIntentModel,
    pcb_constraints: PCBConstraintProposal,
    evidence_trace: tuple[HardwareEvidenceTrace, ...],
    review: HardwareDesignReviewProjection,
    proposed_at: datetime,
    candidate_semantics: str,
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "proposal_id": proposal_id,
            "project_id": project_id,
            "requirement_fingerprint": requirement_fingerprint,
            "plan_fingerprint": plan_fingerprint,
            "context_fingerprint": context_fingerprint,
            "architecture": architecture,
            "component_selection": component_selection,
            "interface_contracts": interface_contracts,
            "power_design": power_design,
            "bom": bom,
            "schematic_intent": schematic_intent,
            "pcb_constraints": pcb_constraints,
            "evidence_trace": evidence_trace,
            "review": review,
            "proposed_at": proposed_at,
            "candidate_semantics": candidate_semantics,
            "review_required": review_required,
        }
    )


class HardwareEngineeringProposal(_HardwareContract):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str
    project_id: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    architecture: SystemArchitectureProposal
    component_selection: ComponentSelectionProposal
    interface_contracts: InterfaceContractProposal
    power_design: PowerDesignProposal
    bom: BOMProposal
    schematic_intent: SchematicIntentModel
    pcb_constraints: PCBConstraintProposal
    evidence_trace: tuple[HardwareEvidenceTrace, ...]
    review: HardwareDesignReviewProjection
    proposed_at: datetime
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    @field_validator("proposal_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_fingerprint_value)
    _context_fingerprint = field_validator("context_fingerprint")(_fingerprint_value)
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("evidence_trace", mode="before")
    @classmethod
    def validate_evidence_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence_trace")

    @model_validator(mode="after")
    def validate_proposal(self) -> HardwareEngineeringProposal:
        evidence_ids = tuple(item.evidence_id for item in self.evidence_trace)
        if evidence_ids != tuple(sorted(evidence_ids)) or len(evidence_ids) != len(
            set(evidence_ids)
        ):
            raise ValueError("evidence trace must be sorted and unique")
        if (
            self.review.proposal_id != self.proposal_id
            or self.review.requirement_fingerprint != self.requirement_fingerprint
            or self.review.plan_fingerprint != self.plan_fingerprint
            or self.review.context_fingerprint != self.context_fingerprint
        ):
            raise ValueError("review binding mismatch")
        expected = hardware_engineering_proposal_fingerprint(
            proposal_id=self.proposal_id,
            project_id=self.project_id,
            requirement_fingerprint=self.requirement_fingerprint,
            plan_fingerprint=self.plan_fingerprint,
            context_fingerprint=self.context_fingerprint,
            architecture=self.architecture,
            component_selection=self.component_selection,
            interface_contracts=self.interface_contracts,
            power_design=self.power_design,
            bom=self.bom,
            schematic_intent=self.schematic_intent,
            pcb_constraints=self.pcb_constraints,
            evidence_trace=self.evidence_trace,
            review=self.review,
            proposed_at=self.proposed_at,
            candidate_semantics=self.candidate_semantics,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("hardware proposal fingerprint mismatch")
        return self
