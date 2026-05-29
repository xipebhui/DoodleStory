# Backend Workflow Standard

## Purpose

Use this standard when adding background tasks, async jobs, workflow steps, long-running operations, generation tasks, retries, cancellation, queue workers, or graceful shutdown behavior.

The default for personal projects and small products is lightweight: use an in-process memory queue for scheduling work and use the database as the source of truth for task state. Do not introduce external queue infrastructure or a durable workflow engine unless the user asks for it or the task has crossed the medium/heavy thresholds below.

## Source Baseline

- [BullMQ: graceful shutdown](https://docs.bullmq.io/guide/workers/graceful-shutdown)
- [BullMQ: retrying failing jobs](https://docs.bullmq.io/guide/retrying-failing-jobs)
- [BullMQ: flows](https://docs.bullmq.io/guide/flows)
- [AWS SQS: visibility timeout](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)
- [AWS SQS: dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [Google Pub/Sub: handling failures](https://cloud.google.com/pubsub/docs/handling-failures)
- [Google Pub/Sub: lease management](https://docs.cloud.google.com/pubsub/docs/lease-management)
- [Temporal documentation](https://docs.temporal.io/)
- [Inngest: durable workflows](https://www.inngest.com/uses/durable-workflows)

## Default Decision Rule

Start small unless there is evidence not to.

For small tasks:

- Use an in-process memory queue to schedule work.
- Store task state, step state, progress, attempts, errors, and output references in the database.
- Run the worker loop inside the same application process by default.
- Recover pending or running tasks from database state on application startup.
- Keep the queue as a convenience, not the system of record.

Do not add Redis, RabbitMQ, Kafka, SQS, Pub/Sub, Temporal, Inngest, Step Functions, Celery, BullMQ, or a separate worker service by default.

## Does A Small Task Need An Independent Service?

Default answer: no.

For small projects, it is acceptable to start the background worker in the same deployable application process when all of these are true:

- Task volume is low.
- Tasks are not business-critical financial or compliance workflows.
- Tasks can be resumed from database state after a restart.
- Users can tolerate task pause or retry during deployments.
- The application has one or very few instances.
- Worker concurrency can be safely limited inside the process.

Move to an independent worker process or service when any of these become true:

- Web request latency is affected by background work.
- Multiple app instances would accidentally run duplicate in-memory workers.
- Tasks require different CPU, memory, timeout, or scaling behavior than web requests.
- Deployments need to drain workers separately from web traffic.
- Task processing must continue while the web application restarts.
- Operational monitoring needs separate worker health, queue depth, or lag.

## Workflow Levels

### Small Workflow

Use this for personal products, MVPs, admin tools, and early SaaS workflows.

Default architecture:

- API creates a task row in the database.
- API enqueues the task ID into an in-memory queue.
- A local worker pulls task IDs and processes bounded steps.
- Each step writes progress to the database.
- On startup, the app scans for resumable `queued`, `running`, or `retrying` tasks and re-enqueues them safely.

Appropriate examples:

- Generate a small number of images.
- Send a short email batch.
- Import a small CSV.
- Run a single provider call with retry.
- Produce a lightweight report.

Avoid:

- Custom distributed locks unless there are multiple active workers.
- External message brokers before there is real volume or reliability need.
- Full DAG/workflow engines.
- Queue-only state without database task records.

### Medium Workflow

Use this when the workflow is still product-level but needs stronger runtime guarantees.

Before implementing a medium workflow, explain to the user:

- Which small-workflow limit is being exceeded.
- What can go wrong if the workflow stays small.
- Which queue or worker approach is being proposed.
- What new operational cost or complexity it introduces.
- How task state remains visible in the database.

Medium indicators:

- Multiple app instances process tasks concurrently.
- Task volume or duration can block web traffic.
- Tasks need independent scaling from the web app.
- Tasks need delayed scheduling, rate limiting, or per-queue concurrency.
- Failed jobs need an operator-visible retry or dead-letter flow.
- Long-running tasks require heartbeat or lease extension.
- Users need cancellation, pause, retry, or partial retry.

Possible tools:

- Node: BullMQ or pg-boss.
- Python: RQ, Dramatiq, or Celery.
- Cloud queues: SQS or Pub/Sub.
- Managed durable functions when they reduce operational burden.

### Heavy Workflow

Use this only for business-critical or long-lived workflows.

Heavy indicators:

- Workflows run for hours, days, or longer.
- Workflows require human approval or wait for external events.
- Financial, billing, compliance, or irreversible side effects are involved.
- Cross-service orchestration must survive crashes and deployments.
- Exactly-once effects are impossible, so idempotency and durable replay are required.
- Operators need full workflow history and replay/reset tooling.

Possible tools:

- Temporal.
- Inngest.
- AWS Step Functions.
- Other durable execution systems approved for the project.

Do not select a heavy workflow engine just because the task has several steps.

## Required Task State

Every background workflow must expose a durable state model in the database.

Minimum task states:

- `pending`
- `queued`
- `running`
- `succeeded`
- `failed`
- `cancel_requested`
- `cancelled`
- `retrying`

Optional states when useful:

- `partial_succeeded`
- `paused`
- `waiting_for_input`

Minimum task fields:

- stable task ID
- task type
- status
- current step
- progress count or percent
- attempts
- max attempts
- next run time when retrying
- cancellation flag or cancel requested timestamp
- error code and user-safe error message
- internal error detail or log reference
- input summary
- output reference
- created, updated, started, and finished timestamps

For multi-step workflows, use a step table or structured step records when users or operators need per-step visibility.

## Queue Rules

1. Queue messages should contain a task ID, not the full business payload.
2. The worker must load current task state from the database before doing work.
3. The worker must check whether the task is already completed or cancelled before starting.
4. The worker must update state at step boundaries.
5. Retried work must use persisted task state to avoid duplicating completed side effects.
6. If the in-memory queue is lost, startup recovery must re-enqueue resumable tasks from the database.
7. Do not rely on process memory as the only record of progress.

## Graceful Shutdown

Workers must handle shutdown intentionally.

Small in-process workers:

1. Stop accepting or enqueueing new background work when shutdown begins.
2. Stop pulling new tasks from the memory queue.
3. Let the current step finish when it can finish inside the grace period.
4. Write a checkpoint or mark the task retryable before exit when the current step cannot finish.
5. Release any local locks or leases.
6. On next startup, recover tasks stuck in `running` beyond a safe timeout.

Medium and heavy workers:

- Use the selected queue or workflow engine's drain, close, ack, lease, heartbeat, or visibility-timeout mechanism.
- Document the shutdown signal and grace period.
- Document what happens to active jobs during deploys.

## Retries And Idempotency

Retry only work that is safe to repeat.

Rules:

1. Each retryable step must be idempotent or protected by an idempotency key.
2. External side effects such as payments, emails, generated assets, messages, and file writes need a request ID, step ID, or output receipt.
3. Use bounded retry counts.
4. Use backoff for transient failures.
5. Do not retry permanent failures such as invalid input, missing permission, or rejected content.
6. User-cancelled tasks must not retry automatically.
7. Store failure reason, attempt count, and next retry time.

## Cancellation

Cancellation is a state transition, not deletion.

Rules:

1. User cancellation should set `cancel_requested`.
2. Workers should check cancellation at step boundaries.
3. Already completed side effects should be preserved or explicitly cleaned according to product rules.
4. The UI should show whether cancellation is pending, completed, or impossible because the workflow already finished.
5. Cancelled tasks should not be automatically retried.

## Example: Story Image Generation

A lightweight story image generation workflow can stay small at first.

Suggested steps:

1. Create `image_generation_tasks` row with `queued` status.
2. Enqueue task ID in memory.
3. Parse story.
4. Extract characters.
5. Plan scenes.
6. Generate each image as its own step or child record.
7. Store generated asset references.
8. Mark task `succeeded`, `partial_succeeded`, or `failed`.

Suggested tables:

- `image_generation_tasks`
- `image_generation_steps` or structured step records
- `generated_images`
- `generated_characters` if character review is product-visible

Escalate to medium if image generation becomes high volume, needs separate GPU/provider rate limiting, must continue during web deploys, or needs operator retry tooling.

## Review Checklist

Before calling workflow implementation done, confirm:

- Task state is stored in the database.
- Queue messages contain task IDs, not full payloads.
- In-memory queue loss can be recovered from database state.
- Worker startup re-enqueues safe resumable tasks.
- Shutdown stops new work and handles active work safely.
- Each retryable step is idempotent or has an idempotency key.
- Retry limits and failure states are visible.
- Cancellation is a state transition.
- Medium or heavy infrastructure was explained and approved when selected.
