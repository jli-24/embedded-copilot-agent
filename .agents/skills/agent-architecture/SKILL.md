---
name: agent-architecture
description: Design and implement Embedded Copilot multi-agent orchestration with LangGraph. Use for work under agents/, including Supervisor Agent routing, shared Agent State, inter-agent communication, workflow edges, specialist handoffs, and Tool Calling contracts.
---

# Agent Architecture

Design the smallest explicit LangGraph workflow that satisfies the requested behavior.

## Workflow

1. Define typed shared state before graph nodes.
2. Give each agent one responsibility and a typed input/output boundary.
3. Make Supervisor routing decisions explicit and testable.
4. Keep tool schemas separate from agent prompts and validate every tool result.
5. Model retry, timeout, empty-result, and terminal-error paths as graph behavior.
6. Add focused tests for nodes, routing, state transitions, and tool failures.

## Required v0.1.0 Architecture

- Supervisor Agent classifies requests and routes to Knowledge, Firmware, or Debug.
- Knowledge Agent retrieves grounded context and always preserves citations.
- Firmware Agent reasons about embedded C and produces reviewable firmware guidance.
- Debug Agent analyzes symptoms, logs, and tool observations without claiming unobserved facts.
- Agent State carries request, route, messages, retrieved sources, tool results, errors, and final answer.
- Inter-agent communication occurs only through typed state updates or typed tool results.
- Tool Calling uses narrow Pydantic schemas, deterministic error mapping, and injectable adapters.

Read [references/architecture-contracts.md](references/architecture-contracts.md) before defining state, graph nodes, or tool interfaces.

## Guardrails

- Do not hide routing in free-form prompt text.
- Do not let agents mutate global state or call infrastructure directly.
- Do not add an agent when a pure function or tool is sufficient.
- Preserve source provenance from retrieval through the final response.
- Use dependency injection so tests never require a live model, device, or vector database.
