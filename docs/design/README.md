# DoodleStory Product Design

This directory contains the first implementation-ready product design for DoodleStory.

## Documents

- [UI Design](ui.md): product navigation, screens, interaction states, and generation workflow UX.
- [Backend API Design](api.md): REST resources, request and response shapes, pagination, errors, and workflow actions.
- [Database Design](database.md): initial relational schema, constraints, indexes, and workflow state model.

## Design Principles

- Preserve the user's submitted story text exactly.
- Make style tuning inspectable through reference images, style prompts, tests, and model bindings.
- Keep AI-generated intermediate outputs visible: panels and generated prompts are product state, not invisible internals.
- Use database-backed workflow state as the source of truth.
- Keep the first workflow small. Do not introduce external queue or durable workflow infrastructure without a later explicit decision.
