---
title: Architecture Stabilization Phase 4 - Knowledge Gateway Boundary Freeze
type: architecture
status: frozen
layer: knowledge
---

# Knowledge Gateway Boundary

Phase 4 freezes the Knowledge Gateway Source, Adapter, Projection, Retrieval,
and Runtime boundaries. It adds architecture documentation and boundary
tests only.

This phase does not modify production logic, RAG behavior, KnowledgeAgent
behavior, Runtime composition, Workflow, LangGraph graph, Memory schemas,
Multimodal contracts, or API contracts. It adds no Agent, Runtime, Workflow
node, Registry, Provider, Model, or execution capability.

## Canonical Runtime

The fixed Runtime composition is:

```text
Supervisor Router
KnowledgeAgent
FirmwareAgent
DebugAgent
```

`supervisor_node` remains the Supervisor Router. It is not replaced with a
new `SupervisorAgent` class. `KnowledgeAgent` is the only Runtime Knowledge
entry point.

The following are not Runtime Agents:

```text
Knowledge Gateway
Local RAG
Web Research Adapter
Datasheet Adapter
Engineering Memory Retrieval
Engineering Knowledge
Knowledge Evolution
Knowledge Writer
Multimodal Input
```

No SearchAgent, WebResearchAgent, DatasheetAgent, MemoryAgent, GraphAgent, or
VisionAgent is introduced.

## Gateway Flow

The Knowledge Gateway flow is one-way and structured:

```text
User Query
  -> KnowledgeAgent
  -> Knowledge Gateway
  -> Source / Adapter
  -> Evidence Projection
  -> Structured Knowledge Result
```

The Gateway is an application composition boundary, not an Agent. It has no
Agent loop, Workflow node, Runtime routing, or execution capability.

## Knowledge Source Layer

The current source and projection packages are classified as follows:

| Package | Identity | Allowed responsibility |
| --- | --- | --- |
| `rag/` | Local Retrieval Infrastructure | Document, Chunk, Embedding, Retriever, Evidence |
| `knowledge/` | Gateway Composition Root | Provider registry, adapter composition, evidence ranking |
| `engineering_knowledge/` | Knowledge Graph Projection | Entity, Relation, Evidence, Confidence |
| `knowledge_evolution/` | Knowledge Projection | Read-only knowledge evolution projection |
| `datasheet/` | Datasheet Source/Adapter | Datasheet parsing and evidence projection |
| `datasheet_agent/` | External Knowledge Adapter/Projection | Typed datasheet evidence |
| `web_research_agent/` | External Knowledge Adapter/Projection | Typed external evidence |
| `multimodal_input/` | Observation/Interpretation Projection | Safe input to observation/projection |
| `knowledge_writer/` | Approved Projection Writer | Approved projection to Markdown artifact |

`datasheet_agent/` and `web_research_agent/` retain their historical names,
but their frozen identity is Adapter/Projection, not Runtime Agent.

## Local RAG Boundary

Local RAG preserves this pipeline:

```text
Document
  -> Chunk
  -> Embedding
  -> Retriever
  -> Evidence
```

RAG may retrieve and rank evidence. It must not write Engineering Memory,
modify the Knowledge Graph, or trigger Runtime, Build, Flash, or Device
actions. RAG is not a RAG Agent, Retrieval Agent, or Decision Agent.

## External Knowledge Boundary

External knowledge uses the following boundary:

```text
Request
  -> External Adapter
  -> Provider result
  -> Evidence Projection
```

External adapters may retain their existing provider integration, but they
must not inherit `BaseAgent`, register in an Agent Registry, create a
Workflow node, or create execution capability. Phase 4 tests inspect these
boundaries without making network requests, invoking providers, or writing
files.

## KnowledgeAgent Boundary

KnowledgeAgent consumes Gateway output only:

```text
Query
  -> Knowledge Gateway
  -> Evidence
  -> Structured Result
```

KnowledgeAgent must not perform Web crawling, Datasheet parsing, Memory
writing, Graph modification, or independent Knowledge creation inside its
Agent behavior. Existing KnowledgeAgent behavior remains unchanged.

## Engineering Memory Boundary

Conversation Memory and Engineering Memory remain separate:

```text
Conversation
  -> Candidate
  -> Approval
  -> Promotion
  -> Engineering Memory
  -> Knowledge Retrieval
```

Conversation must not write directly to the Knowledge Base. RAG must not
write Memory. Engineering Memory retrieval is read-only for the Knowledge
Gateway and may expose only approved engineering facts.

## Knowledge Graph Boundary

`engineering_knowledge/` and `knowledge_evolution/` are read-only Knowledge
Projection layers. They may expose entities, relations, evidence, confidence,
and provenance. They must not create a Graph Agent, make Runtime decisions,
or perform automatic graph mutation.

## Knowledge Writer Boundary

Knowledge Writer has one direction:

```text
Approved Projection
  -> Markdown Artifact
```

Markdown is a generated projection artifact. It is not a reasoning source,
Memory source, automatic learning source, or Runtime input. Markdown and
Obsidian must not flow back into Memory, the Knowledge Graph, Knowledge
Gateway, or Runtime.

## Boundary Enforcement

Phase 4 tests inspect only the declared Knowledge Gateway packages and do not
scan unrelated repository code. They verify:

- no Runtime Agent imports or registration;
- no Workflow, LangGraph, Runtime, Build, Flash, or Device execution edge;
- External modules are Adapter/Provider/Projection only;
- Knowledge Writer has no reverse Markdown flow;
- KnowledgeAgent remains the only Runtime Knowledge entry;
- approved Memory retrieval remains separate from Memory mutation.

If an existing violation is found, the test remains failing and the violation
is recorded for a later migration plan. Production code is not changed to
make the Phase 4 tests pass.

## Known Architecture Violation

The current `knowledge_writer/contracts.py` retains the historical
`MemoryCandidate` import and `artifact_from_candidate` helper. The current
`FileKnowledgeWriter` approval paths do not use this helper, but the helper
still exposes a Candidate-to-Markdown compatibility surface that conflicts
with the frozen Writer boundary.

Phase 4 records this issue through the Writer boundary test and does not
remove or rewrite the compatibility helper. A later migration must separate
or retire this helper without changing approved Projection contracts.
