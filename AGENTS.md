# Embedded Copilot Agent

## Project Goal

Build Embedded Copilot Agent v0.1.0 as a Multi-Agent, RAG, and Tool Calling assistant for embedded development.

## Required Development Workflow

Use the global workflow Skills in this order when applicable:

1. brainstorming for requirements and architecture approval
2. writing-plans for an implementation plan
3. executing-plans for approved plan execution
4. test-driven-development before feature or defect implementation
5. systematic-debugging for test failures and engineering problems
6. requesting-code-review after a coherent change is complete
7. verification-before-completion before claiming completion

Do not begin v0.1.0 implementation until the user approves the development plan.

## Project Skill Routing

- Use agent-architecture for files under agents/.
- Use rag-development for files under rag/.
- Use python-backend for files under api/.
- Use python-backend, agent-architecture, and testing for production clients under adapters/.
- Use agent-architecture and testing for files under tools/.
- Use agent-architecture, python-backend, and testing for shared contracts under models/.
- Use python-backend and testing for configuration and logging under core/.
- Use testing for files under tests/ and for all behavior changes.
- Use embedded-c-knowledge for firmware, MCU, peripheral, RTOS, and embedded debugging claims.
- Use git-engineering for commits, tags, versions, and releases.

When a change spans multiple areas, use every relevant project Skill.

## Scope

The first phase includes Supervisor, Knowledge, Firmware, and Debug Agents; RAG; Tool Calling; FastAPI; and unit tests. Keep v0.1.0 offline-testable by injecting model, embedding, workflow, and device adapters and by using temporary Chroma collections in tests.

## Git Conventions

Allowed commit prefixes:

- feat:
- fix:
- docs:
- test:

Use v0.x.x versions. The first target is v0.1.0.

## Verification

Run focused tests during development and the full offline suite before completion. Do not claim hardware validation unless actual hardware evidence is available.
