# Database Design Standard

## Purpose

Use this standard when designing schemas, migrations, indexes, constraints, or data-access patterns. The default posture is: model the business truth clearly, enforce integrity where it matters, and scale the design only when the project scale justifies it.

## Source Baseline

- [Microsoft: Database design basics](https://support.microsoft.com/en-us/office/database-design-basics-eb2159cf-1e30-401a-8084-bd4f9c9ca1f5)
- [Microsoft Learn: database normalization basics](https://learn.microsoft.com/en-us/office/troubleshoot/access/database-normalization-description)
- [PostgreSQL documentation: constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [PostgreSQL documentation: indexes](https://www.postgresql.org/docs/current/indexes.html)
- [PostgreSQL documentation: performance tips](https://www.postgresql.org/docs/current/performance-tips.html)
- [OWASP: SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)

## Universal Rules

1. Start from the product workflow and data ownership, not from a fashionable architecture.
2. Define entities, relationships, primary keys, required fields, and business constraints before optimizing.
3. Prefer normalized OLTP schemas for transactional systems. Denormalize only with a documented read or performance reason.
4. Use foreign keys, unique constraints, not-null constraints, and check constraints when they protect business correctness.
5. Add indexes for known query patterns, uniqueness, joins, and ordering needs. Do not add speculative indexes.
6. Every non-obvious index must have a short reason: the query, join, filter, or ordering it supports.
7. Keep migrations reviewable and reversible when feasible. If rollback is unsafe, document the recovery plan.
8. Never build SQL through string concatenation with untrusted input. Use parameterized queries or the selected framework's safe query API.
9. Do not introduce sharding, read replicas, CQRS, event sourcing, data warehouses, or cache-as-source-of-truth without explicit project need and user approval.

## Scale-Based Design

### Small Project or MVP

Use this level for prototypes, internal tools, early SaaS products, or projects without proven load.

- Model only the current core workflow.
- Use a small number of clear tables.
- Add primary keys, required fields, unique constraints, and foreign keys for core relationships.
- Add indexes only for actual lookup paths, unique constraints, and obvious foreign-key joins.
- Prefer simple migrations and clear naming over advanced database features.

Avoid:

- Premature table partitioning.
- Generic metadata tables for unknown future features.
- Read/write splitting.
- Event sourcing.
- Multiple databases for one bounded workflow.

### Medium Project

Use this level when the project has multiple user roles, recurring reporting needs, background jobs, or measurable growth.

- Maintain an ERD or schema relationship note for core tables.
- Document ownership for shared tables and important write paths.
- Add constraints for cross-field business invariants where the database can enforce them safely.
- Review indexes against actual queries.
- Use `EXPLAIN` or equivalent planner output before adding complex indexes for performance.
- Separate transactional tables from reporting projections when reporting starts to distort OLTP design.

Avoid:

- Adding indexes without a query.
- Reusing one overloaded table for unrelated entity types.
- Introducing asynchronous projections without documenting freshness expectations.

## Workflow State Design

Use this section when a backend feature has background tasks, async generation, queues, retries, cancellation, or long-running workflow steps.

### Default Rule

The database is the source of truth for workflow state. Queues schedule work; they do not replace persisted task state.

For small projects, use a small set of workflow tables plus an in-process memory queue by default. Do not add external queue tables, event stores, or workflow engine schemas unless the user asks for them or the task has been explained as medium/heavy workflow work.

### Small Workflow Tables

Start with one task table when the workflow is simple.

Common columns:

- `id`
- `type` or domain-specific task kind
- `status`
- `current_step`
- `progress_current`
- `progress_total`
- `attempts`
- `max_attempts`
- `next_run_at`
- `cancel_requested_at`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`
- `input_summary` or a reference to input data
- `output_ref`
- `error_code`
- `error_message`
- `internal_error_ref`

Add a step table only when step-level visibility, retry, cancellation, or partial success is visible to users or operators.

Common step columns:

- `id`
- `task_id`
- `step_name`
- `status`
- `attempts`
- `started_at`
- `finished_at`
- `idempotency_key`
- `output_ref`
- `error_code`
- `error_message`

### State Constraints

- Use explicit allowed statuses, through enum, check constraint, or application-level validation plus tests.
- Keep timestamps for state transitions that affect recovery.
- Store user-safe error messages separately from internal error details.
- Store large payloads, generated assets, logs, and provider responses outside the task row when they can grow.
- Link task output to domain tables rather than embedding large result arrays in one row.

### Recovery Queries

Design indexes for recovery and worker polling:

- status plus `next_run_at`
- status plus `updated_at` for stuck running task detection
- user or owner plus creation time for task lists
- task ID for step and output lookups

Do not add speculative workflow indexes. Add indexes that support actual recovery, list, or detail queries.

### Escalation

If the workflow needs external queue infrastructure, separate worker services, durable replay, or dead-letter operations, document why the small workflow design is insufficient before changing the schema.

### Large Project

Use this level when the project has high traffic, large tables, strict uptime needs, multiple teams, or regulated data.

- Record capacity assumptions: row counts, write rate, read patterns, retention, and recovery expectations.
- Use `EXPLAIN ANALYZE`, slow query logs, or production-like benchmarks before structural performance changes.
- Consider partitioning, archival, materialized views, read models, or denormalization only with evidence.
- Document operational impact for migrations that rewrite large tables, lock hot paths, or backfill data.
- Define retention, backup, restore, and privacy requirements explicitly.

Avoid:

- Treating large-system patterns as defaults.
- Denormalizing before identifying the exact query and consistency trade-off.
- Creating irreversible migrations without a tested recovery path.

## Naming

- Use stable, descriptive table names based on domain concepts.
- Use consistent primary key naming within a project.
- Name foreign keys and indexes clearly enough to diagnose errors.
- Avoid abbreviations unless they are standard in the domain.

## List Queries And Pagination

Use this section when designing queries or endpoints that back list pages, tables, search results, feeds, admin indexes, dashboards, or exports.

### Default Rule

Dynamic list queries must be bounded. Do not expose an API or data-access function that returns every row from a table unless the dataset has a documented small upper bound.

The backend must enforce pagination. Frontend-only pagination over an unbounded result set is not acceptable.

### Query Shape

List queries should:

- select only the columns needed for the list view
- use stable ordering
- apply server-side filters and search conditions
- apply a limit or page size
- enforce a maximum limit
- return pagination metadata needed by the client

Detail queries should be separate from list queries. Load large fields, child collections, logs, histories, audit trails, file contents, and deeply nested related objects only for the selected item or a clearly bounded subset.

### Pagination Strategy

- Offset pagination is acceptable for small and medium admin lists when limits are enforced and ordering is stable.
- Cursor pagination is preferred for high-change datasets, infinite scroll, feeds, large tables, or user-facing lists where records may be inserted while users browse.
- Keyset pagination is preferred when performance matters and the sort key supports it.
- Total counts can be useful, but avoid expensive exact counts on large filtered datasets unless the user experience requires them.

### Indexing For Lists

Add indexes for real list query patterns:

- filter columns used frequently
- sort columns used with pagination
- search columns when search is part of the workflow
- foreign keys used in list joins

Do not add speculative indexes. If a list query is slow, inspect the query plan before introducing complex indexes or denormalized read models.

### Prohibited Patterns

- `SELECT *` for list endpoints.
- Unbounded `findMany`, `all`, or equivalent ORM calls for dynamic lists.
- Loading full child collections for every row in a list.
- Loading large text/blob fields for every row in a list.
- Running one detail query per row during initial list rendering.
- Sorting or filtering large dynamic datasets only after returning them to the frontend.

### Exceptions

Loading all records is allowed only when all of the following are true:

- The dataset has a documented small upper bound.
- The data is needed as a complete set, such as a short static select list.
- The response excludes unnecessary detail payloads.
- The reason is recorded near the implementation or in the relevant contract.

## Verification

Database changes should be checked through the selected migration tool and, where relevant, query planner evidence. At minimum, record:

- Migration command and result.
- Affected tables.
- New constraints and indexes.
- Manual or automated checks for the main workflow.
