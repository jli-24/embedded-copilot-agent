"""Deterministic, evidence-bound Firmware Engineering projections."""

from __future__ import annotations

from embedded_copilot.engineering_firmware.integration.inputs import (
    _FirmwareEngineeringInput,
)
from embedded_copilot.engineering_firmware.models import (
    BuildArtifactStatus,
    BuildProposal,
    CodeGenerationIntent,
    CodeGenerationPlan,
    DebugStrategyProposal,
    DriverDesignProposal,
    FirmwareArchitectureModule,
    FirmwareArchitectureProposal,
    FirmwareBuildArtifactType,
    FirmwareDiagnosticCategory,
    FirmwareDiagnosticStrategy,
    FirmwareDriverRequirement,
    FirmwareDriverType,
    FirmwareEngineeringProposal,
    FirmwareEvidenceTrace,
    FirmwareExecutionContract,
    FirmwareExecutionPrerequisite,
    FirmwareFindingCode,
    FirmwareFindingSeverity,
    FirmwareInterfaceContract,
    FirmwareInterfaceContractProposal,
    FirmwareModuleLayer,
    FirmwarePlatformProfile,
    FirmwarePlatformStatus,
    FirmwarePriorityRecommendation,
    FirmwareProposalItemStatus,
    FirmwareReviewFinding,
    FirmwareReviewProjection,
    FirmwareTaskProposal,
    FirmwareTaskType,
    RTOSTaskArchitectureProposal,
    _projection_fingerprint,
    firmware_engineering_proposal_fingerprint,
)

_NETWORK_PROTOCOLS = frozenset({"BLE", "ETHERNET", "MQTT", "TCP_IP", "WIFI"})
_HARDWARE_CONFLICT_CODES = frozenset(
    {
        "CONSTRAINT_CONFLICT",
        "REQUIREMENT_EVIDENCE_CONFLICT",
        "VERIFIED_EVIDENCE_CONFLICT",
    }
)
_DEBUG_FACT_TYPES = {
    "FIRMWARE_COMPILE_ERROR": FirmwareDiagnosticCategory.COMPILE_ERROR,
    "FIRMWARE_RUNTIME_ERROR": FirmwareDiagnosticCategory.RUNTIME_ERROR,
    "FIRMWARE_MEMORY_ISSUE": FirmwareDiagnosticCategory.MEMORY_ISSUE,
}
_DEBUG_CHECKS = {
    FirmwareDiagnosticCategory.COMPILE_ERROR: (
        "REVIEW_DIAGNOSTIC_RECORDS",
        "VERIFY_BUILD_CONTRACT",
    ),
    FirmwareDiagnosticCategory.RUNTIME_ERROR: (
        "COLLECT_RUNTIME_OBSERVATIONS",
        "REVIEW_TASK_LIFECYCLE",
    ),
    FirmwareDiagnosticCategory.MEMORY_ISSUE: (
        "COLLECT_MEMORY_OBSERVATIONS",
        "REVIEW_MEMORY_BUDGET",
    ),
}


def build_firmware_proposal(
    source: _FirmwareEngineeringInput,
) -> FirmwareEngineeringProposal:
    architecture = _architecture(source)
    drivers = _drivers(source)
    tasks = _tasks(source, drivers)
    interfaces = _interfaces(source)
    code_generation = _code_generation(architecture, drivers)
    build = _build(source)
    debug = _debug_strategy(source)
    evidence_trace = _evidence_trace(source, drivers, debug)
    execution_contract = _execution_contract(source, build, debug)
    findings = _findings(source, drivers, tasks, interfaces, build, debug)
    review = _review(
        source,
        architecture,
        drivers,
        tasks,
        interfaces,
        evidence_trace,
        findings,
    )
    values = dict(
        proposal_id=source.proposal_id,
        project_id=source.project_id,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        requirement_fingerprint=source.requirement_fingerprint,
        plan_fingerprint=source.plan_fingerprint,
        context_fingerprint=source.context_fingerprint,
        platform=source.platform.projection,
        architecture=architecture,
        driver_design=drivers,
        task_architecture=tasks,
        interface_contracts=interfaces,
        code_generation=code_generation,
        build=build,
        debug_strategy=debug,
        execution_contract=execution_contract,
        evidence_trace=evidence_trace,
        review=review,
        proposed_at=source.proposed_at,
        candidate_semantics="unverified",
        review_required=True,
    )
    return FirmwareEngineeringProposal(
        **values,
        fingerprint=firmware_engineering_proposal_fingerprint(**values),
    )


def _architecture(
    source: _FirmwareEngineeringInput,
) -> FirmwareArchitectureProposal:
    components = tuple(item.component_reference for item in source.components)
    interfaces = tuple(item.interface_id for item in source.interfaces)
    has_platform = source.platform.profile is not FirmwarePlatformProfile.UNRESOLVED
    modules = (
        FirmwareArchitectureModule(
            layer=FirmwareModuleLayer.BSP,
            responsibility="PLATFORM_INITIALIZATION",
            component_references=tuple(
                item.component_reference
                for item in source.components
                if item.requirement_key == "MCU"
            ),
            status=(
                FirmwareProposalItemStatus.PROPOSED
                if has_platform
                else FirmwareProposalItemStatus.UNRESOLVED
            ),
        ),
        FirmwareArchitectureModule(
            layer=FirmwareModuleLayer.DRIVERS,
            responsibility="HARDWARE_ABSTRACTION",
            component_references=components,
            interface_references=interfaces,
            status=(
                FirmwareProposalItemStatus.PROPOSED
                if components or interfaces
                else FirmwareProposalItemStatus.UNRESOLVED
            ),
        ),
        FirmwareArchitectureModule(
            layer=FirmwareModuleLayer.MIDDLEWARE,
            responsibility="SERVICE_COORDINATION",
            interface_references=interfaces,
            status=(
                FirmwareProposalItemStatus.PROPOSED
                if has_platform or interfaces
                else FirmwareProposalItemStatus.UNRESOLVED
            ),
        ),
        FirmwareArchitectureModule(
            layer=FirmwareModuleLayer.APPLICATION,
            responsibility="FUNCTION_ORCHESTRATION",
            status=(
                FirmwareProposalItemStatus.PROPOSED
                if source.functional_requirements
                else FirmwareProposalItemStatus.UNRESOLVED
            ),
        ),
        FirmwareArchitectureModule(
            layer=FirmwareModuleLayer.TESTS,
            responsibility="VERIFICATION_PLANNING",
            status=FirmwareProposalItemStatus.PROPOSED,
        ),
    )
    return FirmwareArchitectureProposal(
        modules=modules,
        fingerprint=_projection_fingerprint(
            "FirmwareArchitectureProposal", modules=modules
        ),
    )


def _drivers(source: _FirmwareEngineeringInput) -> DriverDesignProposal:
    drivers: list[FirmwareDriverRequirement] = []
    for item in source.components:
        is_conflict = item.status == "CONFLICT"
        drivers.append(
            FirmwareDriverRequirement(
                driver_reference=f"driver-{item.component_reference}",
                driver_type=(
                    FirmwareDriverType.BSP_SUPPORT
                    if item.requirement_key == "MCU"
                    else FirmwareDriverType.COMPONENT_DRIVER
                ),
                responsibility=(
                    "RESOLVE_COMPONENT_CONTRACT"
                    if is_conflict
                    else "PROJECT_COMPONENT_INTEGRATION"
                ),
                component_reference=item.component_reference,
                dependency_references=(item.component_reference,),
                status=(
                    FirmwareProposalItemStatus.BLOCKED
                    if is_conflict
                    else FirmwareProposalItemStatus.PROPOSED
                ),
                evidence_ids=item.evidence_ids,
            )
        )
    for item in source.interfaces:
        drivers.append(
            FirmwareDriverRequirement(
                driver_reference=f"driver-{item.interface_id}",
                driver_type=FirmwareDriverType.INTERFACE_ADAPTER,
                responsibility="PROJECT_INTERFACE_ADAPTER",
                component_reference=item.component_reference,
                interface_references=(item.interface_id,),
                dependency_references=(
                    (item.component_reference,)
                    if item.component_reference is not None
                    else ()
                ),
                status=(
                    FirmwareProposalItemStatus.PROPOSED
                    if item.component_reference is not None
                    else FirmwareProposalItemStatus.UNRESOLVED
                ),
                evidence_ids=item.evidence_ids,
            )
        )
    result = tuple(sorted(drivers, key=lambda item: item.driver_reference))
    return DriverDesignProposal(
        drivers=result,
        fingerprint=_projection_fingerprint("DriverDesignProposal", drivers=result),
    )


def _tasks(
    source: _FirmwareEngineeringInput,
    drivers: DriverDesignProposal,
) -> RTOSTaskArchitectureProposal:
    driver_map = {item.driver_reference: item for item in drivers.drivers}
    tasks: list[FirmwareTaskProposal] = []

    camera_components = tuple(
        item.component_reference
        for item in source.components
        if item.requirement_key == "CAMERA"
    )
    if "VIDEO_CAPTURE" in source.functional_requirements or camera_components:
        tasks.append(
            _task(
                FirmwareTaskType.CAMERA,
                "COORDINATE_CAMERA_PIPELINE",
                tuple(f"driver-{item}" for item in camera_components),
                driver_map,
            )
        )

    network_interfaces = tuple(
        item.interface_id
        for item in source.interfaces
        if item.protocol in _NETWORK_PROTOCOLS
    )
    if "WIRELESS_TRANSMISSION" in source.functional_requirements or network_interfaces:
        tasks.append(
            _task(
                FirmwareTaskType.NETWORK,
                "COORDINATE_NETWORK_SERVICE",
                tuple(f"driver-{item}" for item in network_interfaces),
                driver_map,
            )
        )

    storage_components = tuple(
        item.component_reference
        for item in source.components
        if item.requirement_key == "STORAGE"
    )
    if storage_components:
        tasks.append(
            _task(
                FirmwareTaskType.STORAGE,
                "COORDINATE_STORAGE_SERVICE",
                tuple(f"driver-{item}" for item in storage_components),
                driver_map,
            )
        )

    order = {item: index for index, item in enumerate(FirmwareTaskType)}
    result = tuple(sorted(tasks, key=lambda item: order[item.task_type]))
    return RTOSTaskArchitectureProposal(
        platform_profile=source.platform.profile,
        tasks=result,
        fingerprint=_projection_fingerprint(
            "RTOSTaskArchitectureProposal",
            platform_profile=source.platform.profile,
            tasks=result,
        ),
    )


def _task(
    task_type: FirmwareTaskType,
    responsibility: str,
    driver_references: tuple[str, ...],
    driver_map: dict[str, FirmwareDriverRequirement],
) -> FirmwareTaskProposal:
    references = tuple(sorted(set(driver_references)))
    resolved = bool(references) and all(
        reference in driver_map
        and driver_map[reference].status is FirmwareProposalItemStatus.PROPOSED
        for reference in references
    )
    return FirmwareTaskProposal(
        task_type=task_type,
        responsibility=responsibility,
        driver_references=references,
        priority_recommendation=FirmwarePriorityRecommendation.UNRESOLVED,
        status=(
            FirmwareProposalItemStatus.PROPOSED
            if resolved
            else FirmwareProposalItemStatus.UNRESOLVED
        ),
    )


def _interfaces(
    source: _FirmwareEngineeringInput,
) -> FirmwareInterfaceContractProposal:
    contracts = tuple(
        FirmwareInterfaceContract(
            hardware_interface_id=item.interface_id,
            protocol=item.protocol,
            component_reference=item.component_reference,
            evidence_ids=item.evidence_ids,
            pin_bindings=(),
            register_bindings=(),
            clock_configuration=None,
            memory_layout=None,
        )
        for item in source.interfaces
    )
    return FirmwareInterfaceContractProposal(
        contracts=contracts,
        fingerprint=_projection_fingerprint(
            "FirmwareInterfaceContractProposal", contracts=contracts
        ),
    )


def _code_generation(
    architecture: FirmwareArchitectureProposal,
    drivers: DriverDesignProposal,
) -> CodeGenerationPlan:
    dependency_map = {
        FirmwareModuleLayer.BSP: tuple(
            item.driver_reference
            for item in drivers.drivers
            if item.driver_type is FirmwareDriverType.BSP_SUPPORT
        ),
        FirmwareModuleLayer.DRIVERS: tuple(
            item.driver_reference for item in drivers.drivers
        ),
        FirmwareModuleLayer.MIDDLEWARE: (),
        FirmwareModuleLayer.APPLICATION: (),
        FirmwareModuleLayer.TESTS: (),
    }
    intent_codes = {
        FirmwareModuleLayer.BSP: "DEFINE_BSP_MODULE_INTENT",
        FirmwareModuleLayer.DRIVERS: "DEFINE_DRIVER_MODULE_INTENT",
        FirmwareModuleLayer.MIDDLEWARE: "DEFINE_MIDDLEWARE_MODULE_INTENT",
        FirmwareModuleLayer.APPLICATION: "DEFINE_APPLICATION_MODULE_INTENT",
        FirmwareModuleLayer.TESTS: "DEFINE_TEST_MODULE_INTENT",
    }
    intents = tuple(
        CodeGenerationIntent(
            module_group=item.layer,
            intent_code=intent_codes[item.layer],
            responsibility=item.responsibility,
            dependency_references=tuple(sorted(dependency_map[item.layer])),
        )
        for item in architecture.modules
    )
    return CodeGenerationPlan(
        intents=intents,
        fingerprint=_projection_fingerprint("CodeGenerationPlan", intents=intents),
    )


def _build(source: _FirmwareEngineeringInput) -> BuildProposal:
    expected_artifact = (
        FirmwareBuildArtifactType.FIRMWARE_IMAGE
        if source.platform.profile is not FirmwarePlatformProfile.UNRESOLVED
        else FirmwareBuildArtifactType.UNRESOLVED
    )
    values = dict(
        platform_profile=source.platform.profile,
        build_system=source.platform.build_system,
        toolchain_requirement=source.platform.toolchain_requirement,
        expected_artifact_type=expected_artifact,
        artifact_status=BuildArtifactStatus.UNAVAILABLE,
        command_available=False,
    )
    return BuildProposal(
        **values,
        fingerprint=_projection_fingerprint("BuildProposal", **values),
    )


def _debug_strategy(source: _FirmwareEngineeringInput) -> DebugStrategyProposal:
    grouped: dict[FirmwareDiagnosticCategory, list[str]] = {}
    for item in source.verified_evidence:
        category = _DEBUG_FACT_TYPES.get(item.fact_type)
        if category is not None:
            grouped.setdefault(category, []).append(item.evidence_id)
    strategies = tuple(
        FirmwareDiagnosticStrategy(
            category=category,
            check_codes=tuple(sorted(_DEBUG_CHECKS[category])),
            evidence_ids=tuple(sorted(grouped[category])),
        )
        for category in FirmwareDiagnosticCategory
        if category in grouped
    )
    return DebugStrategyProposal(
        strategies=strategies,
        fingerprint=_projection_fingerprint(
            "DebugStrategyProposal", strategies=strategies
        ),
    )


def _evidence_trace(
    source: _FirmwareEngineeringInput,
    drivers: DriverDesignProposal,
    debug: DebugStrategyProposal,
) -> tuple[FirmwareEvidenceTrace, ...]:
    used = set(source.platform.evidence_ids)
    used.update(
        evidence_id for item in drivers.drivers for evidence_id in item.evidence_ids
    )
    used.update(
        evidence_id for item in debug.strategies for evidence_id in item.evidence_ids
    )
    evidence = {item.evidence_id: item for item in source.verified_evidence}
    return tuple(
        FirmwareEvidenceTrace(
            evidence_id=evidence_id,
            source_type=evidence[evidence_id].source_type,
            reference_ids=evidence[evidence_id].reference_ids,
            source_fingerprint=evidence[evidence_id].fingerprint,
        )
        for evidence_id in sorted(used)
    )


def _execution_contract(
    source: _FirmwareEngineeringInput,
    build: BuildProposal,
    debug: DebugStrategyProposal,
) -> FirmwareExecutionContract:
    values = dict(
        proposal_id=source.proposal_id,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        requirement_fingerprint=source.requirement_fingerprint,
        context_fingerprint=source.context_fingerprint,
        build_proposal_fingerprint=build.fingerprint,
        debug_strategy_fingerprint=debug.fingerprint,
        prerequisites=tuple(FirmwareExecutionPrerequisite),
        execution_state="PROPOSAL_ONLY",
        execution_available=False,
        artifact_status=BuildArtifactStatus.UNAVAILABLE,
        review_required=True,
    )
    return FirmwareExecutionContract(
        **values,
        fingerprint=_projection_fingerprint("FirmwareExecutionContract", **values),
    )


def _findings(
    source: _FirmwareEngineeringInput,
    drivers: DriverDesignProposal,
    tasks: RTOSTaskArchitectureProposal,
    interfaces: FirmwareInterfaceContractProposal,
    build: BuildProposal,
    debug: DebugStrategyProposal,
) -> tuple[FirmwareReviewFinding, ...]:
    findings: list[FirmwareReviewFinding] = []
    if source.platform.status is FirmwarePlatformStatus.UNRESOLVED:
        findings.append(_finding(FirmwareFindingCode.PLATFORM_UNRESOLVED, "platform"))
    if _HARDWARE_CONFLICT_CODES.intersection(source.hardware_finding_codes):
        findings.append(
            _finding(
                FirmwareFindingCode.HARDWARE_CONFLICT_REQUIRES_REVIEW,
                "hardware-proposal",
                severity=FirmwareFindingSeverity.BLOCKING,
            )
        )
    if any(
        item.status is not FirmwareProposalItemStatus.PROPOSED
        for item in drivers.drivers
    ):
        findings.append(
            _finding(
                FirmwareFindingCode.DRIVER_BINDING_UNRESOLVED,
                "driver-design",
            )
        )
    if interfaces.contracts:
        findings.append(
            _finding(
                FirmwareFindingCode.INTERFACE_DETAIL_UNRESOLVED,
                "interface-contracts",
            )
        )
    if tasks.tasks:
        findings.append(
            _finding(
                FirmwareFindingCode.TASK_PRIORITY_UNRESOLVED,
                "task-architecture",
            )
        )
    if build.expected_artifact_type is FirmwareBuildArtifactType.UNRESOLVED:
        findings.append(
            _finding(
                FirmwareFindingCode.BUILD_CONFIGURATION_UNRESOLVED,
                "build-proposal",
            )
        )
    if not debug.strategies:
        findings.append(
            _finding(
                FirmwareFindingCode.DEBUG_EVIDENCE_REQUIRED,
                "debug-strategy",
            )
        )
    findings.append(
        _finding(
            FirmwareFindingCode.EXECUTION_NOT_AVAILABLE,
            "execution-contract",
        )
    )
    unique = {(item.code.value, item.subject_reference): item for item in findings}
    return tuple(unique[key] for key in sorted(unique))


def _finding(
    code: FirmwareFindingCode,
    subject: str,
    *,
    severity: FirmwareFindingSeverity = FirmwareFindingSeverity.REVIEW,
) -> FirmwareReviewFinding:
    return FirmwareReviewFinding(
        code=code,
        severity=severity,
        subject_reference=subject,
    )


def _review(
    source: _FirmwareEngineeringInput,
    architecture: FirmwareArchitectureProposal,
    drivers: DriverDesignProposal,
    tasks: RTOSTaskArchitectureProposal,
    interfaces: FirmwareInterfaceContractProposal,
    evidence_trace: tuple[FirmwareEvidenceTrace, ...],
    findings: tuple[FirmwareReviewFinding, ...],
) -> FirmwareReviewProjection:
    unresolved_count = sum(
        item.status is not FirmwareProposalItemStatus.PROPOSED
        for item in architecture.modules
    ) + sum(
        item.status is not FirmwareProposalItemStatus.PROPOSED
        for item in drivers.drivers
    )
    unresolved_count += sum(
        item.status is not FirmwareProposalItemStatus.PROPOSED for item in tasks.tasks
    )
    unresolved_count += len(interfaces.contracts)
    finding_codes = tuple(
        sorted({item.code for item in findings}, key=lambda item: item.value)
    )
    values = dict(
        proposal_id=source.proposal_id,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        requirement_fingerprint=source.requirement_fingerprint,
        context_fingerprint=source.context_fingerprint,
        module_count=len(architecture.modules),
        driver_count=len(drivers.drivers),
        task_count=len(tasks.tasks),
        interface_count=len(interfaces.contracts),
        unresolved_count=unresolved_count,
        evidence_count=len(evidence_trace),
        findings=findings,
        finding_codes=finding_codes,
        review_required=True,
    )
    return FirmwareReviewProjection(
        **values,
        fingerprint=_projection_fingerprint("FirmwareReviewProjection", **values),
    )
