# Architecture Contracts

## Agent State

Define a typed state that can represent:

- request and conversation messages
- selected route and routing reason
- retrieved chunks and citation metadata
- normalized tool calls and tool results
- recoverable and terminal errors
- final answer and completion status

Use reducers only where concurrent graph branches genuinely merge data. Keep scalar routing and status fields single-writer.

## Supervisor

Route by capability, not agent personality:

- knowledge questions or source lookup -> Knowledge Agent
- firmware generation or review -> Firmware Agent
- failure analysis, logs, or diagnostic planning -> Debug Agent
- ambiguous requests -> ask for the minimum missing information or choose a documented safe default

Make routing output a constrained schema. Test every route and the unknown or invalid route.

## Agent Communication

Agents do not call each other directly. A node reads typed state and returns a partial typed update. The graph controls sequencing, retries, and termination.

Preserve retrieved citation identifiers across all nodes. A specialist may add claims, but it must not replace or detach the source records.

## Tool Calling

Each tool requires:

- a narrow Pydantic input schema
- a typed success result
- stable error categories
- timeout and cancellation behavior
- an adapter interface for offline tests
- explicit permission boundaries for device or filesystem access

Tool output is untrusted data. Validate it before updating state or including it in a response.

## LangGraph Shape

Prefer a small graph:

1. validate request
2. Supervisor route
3. specialist node
4. optional tool or retrieval node
5. synthesize cited response
6. terminal success or error

Add cycles only for a bounded, observable retry. Every cycle requires a counter and terminal condition.
