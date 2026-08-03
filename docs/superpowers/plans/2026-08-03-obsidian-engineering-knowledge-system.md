# Obsidian Engineering Knowledge System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an Obsidian-compatible engineering knowledge system and final-vision architecture documentation without changing runtime code, tests, or existing documentation.

**Architecture:** New documentation is isolated under `docs/knowledge/` and the new `docs/architecture/system-architecture.md`. YAML front matter supplies Dataview fields, wiki links create navigable relationships, and every capability has an explicit implementation-status boundary.

**Tech Stack:** Markdown, Obsidian wiki links, YAML front matter, Mermaid, Dataview.

## Global Constraints

- Do not modify source code or tests.
- Do not overwrite existing documentation.
- v0.39 is the latest released version in the repository history.
- v0.49 and v0.50 are implemented development milestones, not released or tagged.
- v0.51 is a design/implementation milestone, not released or tagged.
- v1.0, v1.1, and v1.2 are roadmap/current-development milestones, not releases.
- Future execution, HIL, PCB, and optimization capabilities must be labelled roadmap only.

---

### Task 1: Establish the vault and metadata convention

**Files:**
- Create: `docs/knowledge/OBSIDIAN_VAULT.md`
- Create: `docs/knowledge/00_Project_Overview/project-overview.md`
- Create: `docs/knowledge/99_Memory/daily-template.md`
- Create: `docs/knowledge/99_Memory/weekly-template.md`
- Create: `docs/knowledge/99_Memory/engineering-memory.md`

- [ ] Define the folder responsibilities, stable YAML fields, tag vocabulary, and wiki-link conventions.
- [ ] Create project overview and memory templates using the shared metadata.
- [ ] Verify every created Markdown file starts with parseable YAML front matter.

### Task 2: Document architecture, agents, knowledge, and engineering layers

**Files:**
- Create: `docs/knowledge/01_System_Architecture/*.md`
- Create: `docs/knowledge/02_Agent_Design/*.md`
- Create: `docs/knowledge/03_Knowledge_System/*.md`
- Create: `docs/knowledge/04_Engineering_Layers/*.md`

- [ ] Document implemented runtime foundations separately from target multi-agent architecture.
- [ ] Add Mermaid flows only where they clarify architecture, workflow, or trust boundaries.
- [ ] Mark non-current Hardware, PCB, Test, and Optimization agents as roadmap concepts.
- [ ] Verify links reference meaningful page names and do not claim future features are implemented.

### Task 3: Record versions, decisions, and Dataview dashboards

**Files:**
- Create: `docs/knowledge/05_Version_History/*.md`
- Create: `docs/knowledge/06_Decision_Log/architecture-decisions.md`
- Create: `docs/knowledge/dashboard/*.md`

- [ ] Create version notes with exact release and milestone status.
- [ ] Capture architecture decisions as status-aware ADR-style entries.
- [ ] Create dashboards with valid Dataview queries against `docs/knowledge`.
- [ ] Verify dashboard fields match the YAML fields used by the source pages.

### Task 4: Add the final-vision system architecture document

**Files:**
- Create: `docs/architecture/system-architecture.md`

- [ ] Describe product positioning and the requested lifecycle from requirements to engineering memory.
- [ ] Use Mermaid for the overall system, knowledge gateway, feedback loop, and HIL target loop.
- [ ] Map v0.49–v0.51 and distinguish implemented development milestones from roadmap layers.
- [ ] Verify the document does not overwrite `docs/architecture.md` or present roadmap execution as current capability.

### Task 5: Documentation-quality review

**Files:**
- Review: all files created in Tasks 1–4

- [ ] Check the expected file tree exists and contains only Markdown documentation.
- [ ] Scan status claims for v0.39, v0.49, v0.50, and v0.51 consistency.
- [ ] Scan Mermaid fences, YAML delimiters, and Dataview fences for balanced delimiters.
- [ ] Run `git diff --check` and report the files created and validation evidence.
