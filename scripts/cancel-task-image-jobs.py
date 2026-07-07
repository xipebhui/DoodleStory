#!/usr/bin/env python3
"""Cancel active image jobs for a task and release unsettled reserved credits."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import GeneratedImage, GenerationTask  # noqa: E402
from app.models.enums import GeneratedImageStatus  # noqa: E402
from app.services.task_worker import image_job_has_terminal_credit, load_task, mark_task_cancelled  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cancel queued/running generated_images for one task. "
            "Dry-run by default; pass --apply to write changes."
        )
    )
    parser.add_argument("--task-id", required=True, help="GenerationTask id to clean up.")
    parser.add_argument("--apply", action="store_true", help="Write cancellation changes to the database.")
    return parser.parse_args()


def active_images(db, task_id: str) -> list[GeneratedImage]:
    return (
        db.query(GeneratedImage)
        .filter(
            GeneratedImage.task_id == task_id,
            GeneratedImage.status.in_([GeneratedImageStatus.queued, GeneratedImageStatus.running]),
        )
        .order_by(GeneratedImage.created_at.asc(), GeneratedImage.id.asc())
        .all()
    )


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        task = load_task(db, args.task_id)
        if task is None:
            raise SystemExit(f"task not found: {args.task_id}")

        images = active_images(db, task.id)
        unsettled_count = sum(0 if image_job_has_terminal_credit(db, image.id) else 1 for image in images)
        print(f"task_id={task.id}")
        print(f"task_status={task.status.value}")
        print(f"active_image_jobs={len(images)}")
        print(f"unsettled_reserved_credit_jobs={unsettled_count}")
        for image in images:
            credit_state = "settled" if image_job_has_terminal_credit(db, image.id) else "reserved"
            print(
                "image "
                f"id={image.id} status={image.status.value} job_kind={image.job_kind.value} "
                f"panel_id={image.panel_id or ''} attempts={image.attempts} credit={credit_state}"
            )

        if not args.apply:
            print("dry_run=true")
            return 0

        mark_task_cancelled(db, task)
        db.commit()
        db.refresh(task)
        remaining = active_images(db, task.id)
        print("dry_run=false")
        print(f"new_task_status={task.status.value}")
        print(f"remaining_active_image_jobs={len(remaining)}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
