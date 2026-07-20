---
name: git-engineering
description: Apply Embedded Copilot Git conventions. Use when preparing branches, commits, tags, changelogs, releases, or reviewing repository history and version changes.
---

# Git Engineering

Keep history small, reviewable, and aligned with Embedded Copilot semantic versioning.

## Commit Format

Use one of these subjects:

- feat: add a user-visible capability
- fix: correct faulty behavior
- docs: update documentation or project Skills
- test: add or change tests

Use the imperative mood. Keep one logical change per commit. Explain motivation and important trade-offs in the body when the subject is insufficient.

## Versioning

- Use v0.x.x tags before the 1.0 stability commitment.
- Increment the minor version for new first-stage capabilities.
- Increment the patch version for compatible fixes and documentation or test-only releases when a release is needed.
- The first target is v0.1.0.
- Keep the package version, release notes, and Git tag consistent.

## Workflow

1. Inspect status and diff before staging.
2. Preserve unrelated user changes.
3. Run focused verification for the changed scope.
4. Stage only intended files.
5. Review the staged diff.
6. Commit with an allowed prefix.
7. Create an annotated v0.x.x tag only for a verified release.

## Guardrails

- Do not rewrite shared history without explicit approval.
- Do not commit secrets, local vector stores, generated indexes, device dumps, or environment files.
- Do not mix formatting churn with functional changes.
- Do not tag a release until the full verification suite passes.
