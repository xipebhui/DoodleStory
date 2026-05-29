# Sprint 01 Contract: Product UI, API, And Database Design

## Goal

Design DoodleStory's first product shape across UI workflows, backend REST API contracts, and relational database schema so implementation can begin from a documented, harness-compliant plan.

## In Scope

- Define the primary UI screens and interaction states for styles, style testing, tasks, generation progress, image preview, and batch download.
- Define backend API resources, request/response shapes, pagination rules, and workflow endpoints.
- Define an initial relational database schema for styles, model bindings, assets, tasks, panels, generated prompts, generated images, and workflow state.
- Keep the workflow design small: in-process queue plus database-backed task state.
- Update project spec, progress, and QA notes.

## Out of Scope

- Implementing frontend or backend code.
- Selecting a concrete framework, ORM, or cloud provider.
- Integrating a real LLM or image model provider.
- Adding authentication, billing, teams, or permissions.
- Introducing Redis, RabbitMQ, Kafka, Temporal, Inngest, or another external workflow engine.

## Deliverables

- `docs/design/README.md`
- `docs/design/ui.md`
- `docs/design/api.md`
- `docs/design/database.md`
- `docs/qa/sprint-01-product-design-report.md`
- Updates to `docs/spec.md` and `docs/progress.md`

## Done Means

- Future implementation work can start from clear product screens, API contracts, and schema notes.
- The design preserves the original user text exactly.
- The task workflow stores progress, step state, errors, and generated asset references in the database.
- Dynamic lists use bounded server-side pagination.
- Verification has been run through `./scripts/check.sh`.

## Verification

```bash
./scripts/check.sh
```

Manual or QA checks:

- Confirm UI design includes list, create, detail, edit, loading, empty, error, destructive, and preview states.
- Confirm API list endpoints enforce `limit` and do not return full detail payloads.
- Confirm database design includes constraints, indexes, and persisted workflow state.
- Confirm no default fallback, mock, or silent error strategy has been introduced.

## Risks / Notes

- Provider-specific fields may need adjustment after the first LLM and image-generation providers are selected.
- Authentication is intentionally left out until the user requests it or a multi-user product requirement appears.

## Handoff

- Next likely step: choose a concrete stack and create an implementation sprint for the app skeleton.
