---
title: Architecture Stabilization Phase 2 - Legacy Compatibility Boundary
type: architecture
status: frozen
layer: runtime
---

# Runtime Boundary

Phase 2 freezes the compatibility boundary established by Phase 1. It does
not migrate domain behavior, add agents, or change the workflow graph.

## Composition Roots

The application has exactly two runtime composition roots:

```text
/chat     -> build_canonical_runtime()
/analyze  -> build_legacy_runtime()
```

`services/runtime.py` is a compatibility facade only:

```text
build_runtime()          -> build_canonical_runtime()
build_analysis_service() -> build_legacy_runtime()
```

Neither alias contains an independent composition implementation.

## Canonical Runtime

The Canonical Runtime uses the `embedded_copilot.agents` implementation
modules and the existing workflow. Its active specialist whitelist is fixed
to Knowledge, Firmware, and Debug, with the existing Supervisor router as the
workflow entry. It must not import or construct Foundation, Hardware, or PCB
agents.

## Legacy Runtime

The Legacy Runtime preserves the existing AnalysisService composition for
historical APIs and compatibility tests. Its explicit type boundary is:

```text
SupervisorAgent
FoundationFirmwareAgent
FoundationDebugAgent
HardwareAgent
PCBAgent
```

These modules remain available for old callers. They are not active Canonical
Runtime agents and are not registered in the Canonical workflow.

## API Compatibility

Explicit `service` and `analysis_service` injection takes precedence over
default composition. This keeps tests and embedding applications from
silently constructing a second runtime. Public paths, request schemas,
response schemas, status codes, and execution lifecycle remain unchanged.

## Frozen Negative Rules

- Canonical Runtime must not import Legacy Runtime or Foundation agent modules.
- Legacy agents must not be added to the Canonical whitelist or workflow.
- Legacy Runtime must not fall back to Canonical Runtime.
- Canonical Runtime must not fall back to Legacy Runtime.
- Engineering Services are not Runtime Agents.
- No new workflow node, Agent behavior, Hardware/PCB migration, Memory change,
  or Multimodal implementation is part of this phase.
