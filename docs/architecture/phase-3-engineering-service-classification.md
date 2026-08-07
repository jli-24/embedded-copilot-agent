---
title: Architecture Stabilization Phase 3 - Engineering Service Classification Freeze
type: architecture
status: frozen
layer: architecture
---

# Classification Freeze

Phase 3 freezes the identity of existing Runtime Agents, Legacy Agents,
Engineering Services, Projections, and Adapters. It does not migrate domain
capability or change the LangGraph workflow.

## Execution Constraints

Phase 3 is an architecture classification freeze. The priorities are:

1. Preserve existing behavior.
2. Add boundary verification.
3. Add architecture documentation.
4. Prevent future architecture drift.

This phase must not modify production logic to satisfy a test. It must not
modify existing DTOs, Ports, Memory schemas, Multimodal contracts, Runtime
composition, Agent registries, Workflow, LangGraph, Tool Runtime, or Agent
behavior.

If an existing implementation violates a frozen classification boundary,
the test must expose the violation and the documentation must record it. The
implementation is not repaired in this phase; a later migration plan is
required unless the change is explicitly in the approved Phase 3 scope.

## Classification Baseline

| Module | Current identity | Runtime Agent | Future direction |
| --- | --- | --- | --- |
| `agents/supervisor` | Supervisor Router | No | Runtime orchestration |
| `agents/knowledge` | Canonical Agent | Yes | Preserve |
| `agents/firmware` | Canonical Agent | Yes | Preserve |
| `agents/debug` | Canonical Agent | Yes | Preserve |
| `hardware/agent.py` | Legacy Agent | No | Hardware Service |
| `pcb/agent.py` | Legacy Agent | No | PCB Service |
| `multimodal_input` | Service | No | Multimodal Service |
| `engineering_memory` | Service / Storage Boundary | No | Memory Platform |
| `knowledge_writer` | Projection Writer | No | Artifact Projection |
| `knowledge_evolution` | Projection Service | No | Knowledge Evolution |
| `conversation_memory` | Candidate Service | No | Conversation Memory |
| `memory_automation` | Approval / Promotion Service | No | Memory Automation |
| `engineering_knowledge` | Graph Projection Service | No | Engineering Knowledge |
| `engineering_context` | Context Projection Service | No | Engineering Context |

## Canonical Runtime

The Canonical Runtime keeps the existing composition:

```text
Supervisor Router
  -> KnowledgeAgent
  -> FirmwareAgent
  -> DebugAgent
```

The public Runtime boundary still exposes four names:

```text
supervisor, knowledge, firmware, debug
```

`supervisor` is the existing `supervisor_node` router. It is not converted
into a new `SupervisorAgent` class. The Canonical Agent type tuple remains
limited to the three existing specialist Agent classes.

Hardware, PCB, Foundation Agents, Memory, Multimodal, Validation,
Optimization, Knowledge Evolution, and Knowledge Writer are not Canonical
Runtime Agents.

## Legacy Compatibility

The Legacy Runtime preserves these existing types:

```text
SupervisorAgent
FoundationFirmwareAgent
FoundationDebugAgent
HardwareAgent
PCBAgent
```

Legacy modules and their historical adapters remain importable and directly
testable. They are not registered in the Canonical Runtime and are not added
to the Canonical Workflow.

## Engineering Service Layer

Engineering Services provide deterministic analysis, validation,
transformation, projection, context preparation, or knowledge processing.
They communicate through Ports, Protocols, typed DTOs, and immutable
Projections.

An Engineering Service is not a Runtime Agent. It must not create an Agent
loop, Workflow node, Runtime router, or implicit execution capability. It must
not hold a Supervisor, Agent, Workflow, Tool Executor, Device Handle, or
provider runtime object as an implicit dependency.

The frozen service/projection identities include:

- Hardware and PCB analysis/projection capability.
- Validation, review, and checking capability.
- Optimization analysis, recommendation, and proposal projection.
- Conversation Memory, Memory Automation, and Engineering Memory.
- Knowledge Evolution, Engineering Knowledge, and Knowledge Writer.
- Multimodal Input, Engineering Context, Completion, and Intelligence.

## Explicit Compatibility Exceptions

The following are intentionally preserved Legacy compatibility files and are
not subject to the ordinary Service import prohibition:

```text
hardware/agent.py
pcb/agent.py
supervisor/agent.py
firmware/agent.py
debug/agent.py
hardware_design/adapter.py
```

The first five are Legacy Agent implementations. The hardware design adapter
is a historical composition adapter. These exceptions remain outside both
Canonical and Engineering Service registries and are protected by separate
Legacy boundary tests.

The AST Service boundary test scans only packages matching the approved
Service naming patterns (`engineering_*`, `*_service`, `*_projection`,
`*_writer`, `*_memory`, `*_context`, `*_knowledge`) plus `multimodal_input`.
It does not scan the entire repository or reinterpret Legacy compatibility
modules as Services.

## Memory and Multimodal Boundaries

Conversation Memory produces Candidates only. Engineering Memory receives
data only through Approval and Promotion. Memory and Knowledge projections do
not become Runtime Agents.

Multimodal Input remains a Service + Port + Projection boundary:

```text
Safe Input
  -> VisionModelPort
  -> Observation
  -> optional EngineeringReasoningPort
  -> Interpretation/Projection
```

No Vision Agent, Datasheet Agent, or PCB Vision Agent is introduced.

Markdown, Memory, Graph, and Multimodal projections do not enter Canonical
Runtime and do not provide implicit execution authority.

## Phase Scope

This phase adds classification documentation and boundary tests only. It does
not modify Agents, Workflow, LangGraph graph, Runtime composition, API
contracts, Tool Runtime, Build, Flash, Device, Memory schemas, or Multimodal
production behavior.
