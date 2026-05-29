# AGENTS.md

## Global Agent Rules

1. Git commit requirements
   - Whenever a major change is made, proactively create one `git commit`.
   - Commit messages must be written in Chinese and must describe the update, impact scope, key changes, and necessary background in detail.
   - Do not use vague commit messages such as "update", "fix", "adjust", "modify", or other context-free summaries.

2. No default fallback strategy
   - Unless the user explicitly states, authorizes, or requests it, do not introduce fallback strategies, degradation logic, compatibility fallbacks, placeholder implementations, mock results, or silent error swallowing.
   - When the primary approach cannot be executed or carries clear risk, first explain the blocker, impact scope, and available options, then wait for user confirmation before implementing an alternative.

## Purpose

This repository uses Codex as a delivery partner for DoodleStory. Codex should work incrementally, keep project state in files, and avoid treating the chat history as the only source of truth.

## Files To Read First

Before substantial work, read:

1. `README.md`
2. `docs/spec.md`
3. `docs/progress.md`
4. the active contract under `docs/contracts/`

When work touches a specific technology area, also read the relevant standard before planning or editing:

- Python: `docs/standards/python.md`
- Java: `docs/standards/java.md`
- Database schema, migrations, queries, or persistence: `docs/standards/database.md`
- Backend background tasks, queues, workflow steps, retries, cancellation, or graceful shutdown: `docs/standards/backend-workflows.md`
- Frontend UI, web apps, or browser behavior: `docs/standards/frontend.md`
- Product UI workflows, list/create/detail/edit flows, buttons, feedback, or user interaction behavior: `docs/standards/ui-interaction.md`
- Common modules such as authentication, user management, payments, subscriptions, admin panels, email, file uploads, or notifications: `docs/standards/reusable-modules.md`

## Operating Rules

1. Work only within the current sprint contract unless explicitly told to expand scope.
2. Prefer small, reviewable changes over broad rewrites.
3. Update `docs/progress.md` after each meaningful implementation step.
4. Do not call work done without running the relevant checks, or clearly documenting what was not checked.
5. If requirements, architecture, or API contracts change, update `docs/spec.md` and the active contract in the same change.
6. Do not add fallback behavior, compatibility layers, mocks, or silent error handling unless the user explicitly requests it.
7. Match database design complexity to the project's actual scale. Avoid sharding, CQRS, denormalized read models, or other large-system patterns without evidence and explicit approval.
8. For personal or small projects, prefer mature lightweight integrations for commodity modules. Email registration/login should be the default authentication path unless the user asks for another flow.
9. For UI work, follow common interaction habits for list, create, detail, edit, button, feedback, loading, and error states instead of inventing ad hoc flows.
10. For small backend workflows, default to an in-process memory queue with database-backed task state. If a medium or heavy workflow approach is needed, explain why and get user confirmation before adding external queue or workflow infrastructure.

## Standard Loop

Use this delivery loop for non-trivial tasks:

1. Read the current project state.
2. Select or create a sprint contract.
3. Implement only that slice.
4. Run verification.
5. Record QA findings if needed.
6. Update progress and next step.

## Done Criteria

A sprint is done only when:

- the agreed scope is implemented
- verification has been run or explicitly deferred
- known gaps are documented
- the repository is left in a coherent state for the next session

## Verification

Preferred entrypoint:

```bash
./scripts/check.sh
```

If project-specific commands exist, add them to `scripts/check.sh`.

## When To Pause

Pause and ask for confirmation when:

- the change affects security, billing, or production data
- the task requires a cross-cutting rewrite
- the current contract conflicts with the new request
- success criteria are too vague to verify
