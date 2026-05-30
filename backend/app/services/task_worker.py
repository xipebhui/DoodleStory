import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models.entities import (
    FileAsset,
    GeneratedImage,
    GenerationStep,
    GenerationTask,
    Style,
    StyleReferenceImage,
    TaskPanel,
)
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageStatus,
    GenerationStepName,
    PromptStatus,
    StepStatus,
    TaskStatus,
)
from app.services.generation_profiles import get_generation_profile
from app.services.image_generation import ImageProviderConfigError, ImageProviderResponseError, generate_xg_image_edit
from app.services.llm import LLMProviderError, StorySegment, generate_panel_prompts, segment_story
from app.services.storage import resolve_storage_key

_queue: asyncio.Queue[str] | None = None
_worker_task: asyncio.Task[None] | None = None


def init_task_queue() -> None:
    global _queue, _worker_task
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(worker_loop())


async def shutdown_task_queue() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None


async def enqueue_task(task_id: str) -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    await _queue.put(task_id)


async def recover_queued_tasks() -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    with SessionLocal() as db:
        interrupted_tasks = db.scalars(
            select(GenerationTask)
            .where(GenerationTask.status.in_([TaskStatus.running, TaskStatus.cancel_requested]))
            .order_by(GenerationTask.created_at.asc())
        ).all()
        for task in interrupted_tasks:
            task.status = TaskStatus.failed
            task.error_code = "WorkerInterrupted"
            task.error_message = "服务重启导致任务中断，请重新创建任务"
            task.finished_at = datetime.utcnow()
        db.commit()

        task_ids = db.scalars(
            select(GenerationTask.id)
            .where(GenerationTask.status.in_([TaskStatus.queued, TaskStatus.retrying]))
            .order_by(GenerationTask.created_at.asc())
        ).all()
    for task_id in task_ids:
        await _queue.put(task_id)


async def worker_loop() -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    while True:
        task_id = await _queue.get()
        try:
            await asyncio.to_thread(process_task, task_id)
        finally:
            _queue.task_done()


def load_task(db: Session, task_id: str) -> GenerationTask | None:
    return db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(
            selectinload(GenerationTask.panels),
            selectinload(GenerationTask.steps),
            selectinload(GenerationTask.generated_images).selectinload(GeneratedImage.asset),
        )
    )


def set_step(db: Session, task: GenerationTask, step_name: GenerationStepName, status: StepStatus) -> GenerationStep:
    step = db.scalar(
        select(GenerationStep).where(
            GenerationStep.task_id == task.id,
            GenerationStep.step_name == step_name,
        )
    )
    if step is None:
        step = GenerationStep(
            task_id=task.id,
            step_name=step_name,
            idempotency_key=f"{task.id}:{step_name.value}",
        )
        db.add(step)
        db.flush()
    step.status = status
    if status == StepStatus.running:
        step.attempts += 1
        step.started_at = datetime.utcnow()
    if status in {StepStatus.succeeded, StepStatus.failed, StepStatus.cancelled}:
        step.finished_at = datetime.utcnow()
    task.current_step = step_name
    db.commit()
    return step


def fail_step_and_task(db: Session, task: GenerationTask, step_name: GenerationStepName, exc: Exception) -> None:
    step = set_step(db, task, step_name, StepStatus.failed)
    step.error_code = exc.__class__.__name__
    step.error_message = str(exc)
    task.status = TaskStatus.failed
    task.error_code = exc.__class__.__name__
    task.error_message = str(exc)
    task.finished_at = datetime.utcnow()
    db.commit()


def build_final_prompt(style_prompt: str, panel_prompt: str) -> str:
    return "\n\n".join(
        [
            style_prompt.strip(),
            f"画面内容：{panel_prompt.strip()}",
            "输出要求：9:16 竖图，无文字、无水印、无 Logo。",
        ]
    )


def should_stop_for_cancel(db: Session, task: GenerationTask) -> bool:
    db.refresh(task)
    if task.status != TaskStatus.cancel_requested:
        return False
    task.status = TaskStatus.cancelled
    task.finished_at = datetime.utcnow()
    db.commit()
    return True


def process_task(task_id: str) -> None:
    with SessionLocal() as db:
        task = load_task(db, task_id)
        if task is None or task.status in {TaskStatus.cancelled, TaskStatus.cancel_requested}:
            return

        task.status = TaskStatus.running
        task.started_at = task.started_at or datetime.utcnow()
        task.progress_current = 0
        task.progress_total = 3
        db.commit()

        try:
            profile = get_generation_profile(task.generation_profile_key_snapshot or "")
        except Exception as exc:
            fail_step_and_task(db, task, GenerationStepName.segment_story, exc)
            return

        try:
            set_step(db, task, GenerationStepName.segment_story, StepStatus.running)
            segmentation = segment_story(
                original_text=task.original_text,
                image_count_mode=task.image_count_mode,
                requested_image_count=task.requested_image_count,
                profile=profile,
            )
            for panel in segmentation.panels:
                db.add(
                    TaskPanel(
                        task_id=task.id,
                        panel_order=panel.panel_order,
                        original_text_segment=panel.text,
                    )
                )
            task.progress_current = 1
            set_step(db, task, GenerationStepName.segment_story, StepStatus.succeeded)
        except LLMProviderError as exc:
            fail_step_and_task(db, task, GenerationStepName.segment_story, exc)
            return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        try:
            set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.running)
            story_segments = [
                StorySegment(panel_order=panel.panel_order, text=panel.original_text_segment)
                for panel in sorted(task.panels, key=lambda item: item.panel_order)
            ]
            prompt_result = generate_panel_prompts(
                original_text=task.original_text,
                style_prompt=task.style_prompt_snapshot,
                panels=story_segments,
                profile=profile,
            )
            prompts_by_order = {item.panel_order: item.prompt for item in prompt_result.panels}
            for panel in task.panels:
                panel.generated_prompt = prompts_by_order[panel.panel_order]
                panel.prompt_status = PromptStatus.generated
                panel.prompt_model_snapshot = profile.llm_model
            task.progress_current = 2
            set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.succeeded)
        except LLMProviderError as exc:
            for panel in task.panels:
                panel.prompt_status = PromptStatus.failed
                panel.error_code = exc.__class__.__name__
                panel.error_message = str(exc)
            fail_step_and_task(db, task, GenerationStepName.generate_panel_prompts, exc)
            return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        set_step(db, task, GenerationStepName.generate_images, StepStatus.running)
        style = db.scalar(
            select(Style)
            .where(Style.id == task.style_id)
            .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
        )
        if style is None or not style.reference_images:
            fail_step_and_task(db, task, GenerationStepName.generate_images, ImageProviderConfigError("风格至少需要一张参考图"))
            return

        reference_paths = [resolve_storage_key(reference.asset.storage_key) for reference in style.reference_images]
        success_count = 0
        for panel in sorted(task.panels, key=lambda item: item.panel_order):
            if should_stop_for_cancel(db, task):
                return
            final_prompt = build_final_prompt(task.style_prompt_snapshot, panel.generated_prompt or "")
            image = GeneratedImage(
                task_id=task.id,
                panel_id=panel.id,
                status=GeneratedImageStatus.running,
                final_prompt=final_prompt,
                generation_profile_key_snapshot=task.generation_profile_key_snapshot,
                started_at=datetime.utcnow(),
            )
            db.add(image)
            db.commit()
            db.refresh(image)

            try:
                generated = generate_xg_image_edit(prompt=final_prompt, reference_paths=reference_paths, profile=profile)
                asset = FileAsset(
                    purpose=FileAssetPurpose.generated_image,
                    storage_key=generated.storage_key,
                    original_filename=generated.original_filename,
                    content_type=generated.content_type,
                    byte_size=generated.byte_size,
                    checksum_sha256=generated.checksum_sha256,
                )
                db.add(asset)
                db.flush()
                image.asset_id = asset.id
                image.provider_request_id = generated.provider_request_id
                image.status = GeneratedImageStatus.succeeded
                image.finished_at = datetime.utcnow()
                success_count += 1
            except (ImageProviderConfigError, ImageProviderResponseError) as exc:
                image.status = GeneratedImageStatus.failed
                image.error_code = exc.__class__.__name__
                image.error_message = str(exc)
                image.finished_at = datetime.utcnow()
            db.commit()

        task = load_task(db, task_id)
        if task is None:
            return
        set_step(db, task, GenerationStepName.generate_images, StepStatus.succeeded if success_count else StepStatus.failed)
        task.progress_current = 3
        task.finished_at = datetime.utcnow()
        if success_count == len(task.panels):
            task.status = TaskStatus.succeeded
        elif success_count > 0:
            task.status = TaskStatus.partial_succeeded
        else:
            task.status = TaskStatus.failed
            task.error_code = "ImageGenerationFailed"
            task.error_message = "所有分镜图片生成失败"
        db.commit()
