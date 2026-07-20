# Embedded Copilot Skills Configuration Design

## Objective

Configure the development workflow and domain constraints required for Embedded Copilot Agent v0.1.0 without creating application code.

## Placement

- Install reusable Superpowers workflow Skills globally under the Codex user Skills directory.
- Store project-specific Skills under .agents/skills so they are versioned with the repository and apply only to this project.
- Use AGENTS.md as the durable routing map between repository paths and Skills.

## Global Skills

Enable brainstorming, writing-plans, executing-plans, test-driven-development, systematic-debugging, requesting-code-review, and verification-before-completion.

## Project Skills

- agent-architecture governs Supervisor routing, typed Agent State, LangGraph, inter-agent communication, and Tool Calling.
- rag-development governs PDF parsing, chunking, embeddings, Chroma, retrieval, and citations.
- python-backend governs FastAPI, Pydantic, API contracts, error mapping, and structured logging.
- testing governs pytest coverage for agents, RAG, tools, API, and configuration.
- embedded-c-knowledge constrains C, ESP32, STM32, ESP-IDF, STM32 HAL, UART, SPI, I2C, and FreeRTOS claims.
- git-engineering governs allowed commit prefixes and v0.x.x versioning.

## Enablement

Every project Skill contains:

- SKILL.md with explicit trigger conditions and development guardrails
- agents/openai.yaml with implicit invocation enabled
- a default prompt that names the Skill
- references only where detailed contracts or domain constraints improve progressive disclosure

## Validation

Configuration is complete when:

- the two missing global workflow Skills are installed
- all six project Skill folders pass the official structural validator
- no generated placeholders remain
- every openai.yaml is UTF-8 and enables implicit invocation
- AGENTS.md maps the workflow and repository paths
- no application source package has been created

## Approval Boundary

This configuration and the v0.1.0 plan may be committed as documentation. Application development starts only after explicit user approval.
