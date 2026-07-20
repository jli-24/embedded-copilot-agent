---
name: python-backend
description: Design and implement the Embedded Copilot Python service under api/. Use for FastAPI routes, Pydantic request and response models, dependency injection, exception mapping, structured logging, lifecycle management, and API tests.
---

# Python Backend

Build a thin FastAPI boundary around independently testable application services.

## Workflow

1. Define Pydantic request and response contracts before routes.
2. Keep routes limited to validation, dependency resolution, service invocation, and response mapping.
3. Place orchestration and domain logic outside FastAPI modules.
4. Inject agents, retrievers, tools, and configuration through explicit dependencies.
5. Map domain exceptions to stable error codes and safe HTTP responses.
6. Emit structured logs with request and trace identifiers; never log secrets or full private documents.
7. Test routes with FastAPI TestClient or HTTPX using fakes for external dependencies.

## v0.1.0 API Rules

- Provide health and query endpoints.
- Version public endpoints under /api/v1.
- Use Pydantic settings for environment configuration.
- Return a stable envelope containing result, citations, trace identifier, and errors where applicable.
- Define explicit timeout, validation, retrieval, tool, and internal-error behavior.
- Keep OpenAPI schemas meaningful with descriptions and constrained fields.
- Avoid global mutable clients; construct long-lived resources in application lifespan.

## Error and Logging Contract

Use domain-specific exceptions below the route layer. Convert them once at the API boundary. Log internal diagnostic context, while responses expose stable codes and safe messages. Include exception traces only in server logs and only when they do not reveal secrets.

## Guardrails

- Do not import FastAPI from agents/, rag/, or tools/.
- Do not catch Exception in business modules merely to return HTTP responses.
- Do not perform blocking device or vector-store operations on the event loop.
- Do not create an abstraction unless at least one production boundary or test seam needs it.
