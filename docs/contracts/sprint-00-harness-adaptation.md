# Sprint 00 Contract: DoodleStory Harness Adaptation

## Goal

Import the Codex project harness and adapt the persistent project documents so future Codex sessions understand DoodleStory's text-to-image business context before implementation starts.

## In Scope

- Import the harness structure from `codex-project-template`.
- Preserve reusable development standards and QA templates.
- Adapt README, product spec, progress log, and active contract to DoodleStory.
- Record the style library and task generation workflow described by the user.

## Out of Scope

- Selecting a frontend or backend stack.
- Implementing application code.
- Integrating LLM or image-generation providers.
- Designing final database migrations or API contracts.

## Deliverables

- `AGENTS.md`
- `README.md`, `README.zh-CN.md`, `README.en.md`
- `docs/spec.md`
- `docs/progress.md`
- `docs/contracts/sprint-00-harness-adaptation.md`
- Imported standards, QA templates, and harness reference documents

## Done Means

- Future Codex sessions can read the repository files and recover the current product context.
- DoodleStory's core concepts and generation workflow are documented.
- The project harness verification entrypoint runs successfully.

## Verification

```bash
./scripts/check.sh
```

Manual or QA checks:

- Confirm README links point to DoodleStory documents.
- Confirm product spec preserves the rule that task text is not rewritten.
- Confirm current progress points to this active contract.

## Risks / Notes

- This sprint is documentation and harness setup only.
- The project still needs a separate implementation sprint before code is added.

## Handoff

- Next likely step: choose the first implementation stack and create a sprint contract for the application skeleton.
