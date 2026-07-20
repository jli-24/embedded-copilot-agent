---
name: testing
description: Test Embedded Copilot with pytest. Use for all work under tests/ and whenever changing agents, tools, RAG, or FastAPI behavior that requires unit, routing, retrieval, tool-contract, or API coverage.
---

# Embedded Copilot Testing

Use pytest to verify behavior at module boundaries without live models, devices, networks, or embedding services.

## Test Workflow

1. State the observable behavior and failure mode.
2. Write the smallest failing test before implementation.
3. Use fakes for models, embeddings, Chroma, serial ports, and external tools.
4. Run the focused test and confirm the expected failure.
5. Implement the minimal behavior.
6. Run focused, subsystem, then full test suites.
7. Keep regression tests for every fixed defect.

## Required Coverage

- Agent tests: state transitions, Supervisor routing, specialist output, and terminal errors.
- RAG tests: parsing metadata, chunking, idempotent indexing, ranking, empty retrieval, and citations.
- Tool tests: schema validation, success, timeout, malformed output, permission denial, and adapter errors.
- API tests: validation, health, success envelopes, citations, exception mapping, and trace identifiers.
- Configuration tests: defaults, environment overrides, and invalid values.

## Test Design Rules

- Assert outputs and state, not prompt wording or private implementation calls.
- Use deterministic fixtures and fixed clocks or identifiers where needed.
- Mark true integration tests separately; keep the default suite offline and fast.
- Prefer factories and small fixtures over a shared mutable test universe.
- Verify negative behavior, especially unsupported claims and swallowed exceptions.
- Keep one reason for failure per test.

## Commands

Use focused commands while developing, then run:

```text
pytest -q
```

Before completion, also run configured linting and type checks when present.
