import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
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
from app.services.image_generation import ImageProviderConfigError, ImageProviderResponseError, generate_xg_image
from app.services.llm import LLMProviderError, StorySegment, generate_panel_prompts, segment_story
from app.services.storage import resolve_storage_key

_queue: asyncio.Queue[str] | None = None
_worker_task: asyncio.Task[None] | None = None
logger = logging.getLogger(__name__)


def init_task_queue() -> None:
    global _queue, _worker_task
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(worker_loop())
    logger.info("task queue initialized")


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
    logger.info("task queue shutdown complete")


async def enqueue_task(task_id: str) -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    await _queue.put(task_id)
    logger.info("task enqueued task_id=%s queue_size=%s", task_id, _queue.qsize())


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
        if interrupted_tasks:
            logger.warning("marked interrupted tasks as failed count=%s", len(interrupted_tasks))

        task_ids = db.scalars(
            select(GenerationTask.id)
            .where(GenerationTask.status.in_([TaskStatus.queued, TaskStatus.retrying]))
            .order_by(GenerationTask.created_at.asc())
        ).all()
    for task_id in task_ids:
        await _queue.put(task_id)
    logger.info("recovered queued tasks count=%s", len(task_ids))


async def worker_loop() -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    logger.info("task worker loop started")
    while True:
        task_id = await _queue.get()
        try:
            logger.info("task worker picked task_id=%s queue_size=%s", task_id, _queue.qsize())
            await asyncio.to_thread(process_task, task_id)
        except Exception as exc:
            logger.exception("task worker unexpected error task_id=%s", task_id)
            mark_task_failed_by_unhandled_error(task_id, exc)
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
    logger.warning(
        "task step failed task_id=%s step=%s error_type=%s error=%s",
        task.id,
        step_name.value,
        exc.__class__.__name__,
        exc,
    )
    step = set_step(db, task, step_name, StepStatus.failed)
    step.error_code = exc.__class__.__name__
    step.error_message = str(exc)
    task.status = TaskStatus.failed
    task.error_code = exc.__class__.__name__
    task.error_message = str(exc)
    task.finished_at = datetime.utcnow()
    db.commit()


def mark_task_failed_by_unhandled_error(task_id: str, exc: Exception) -> None:
    with SessionLocal() as db:
        task = load_task(db, task_id)
        if task is None:
            return
        task.status = TaskStatus.failed
        task.error_code = exc.__class__.__name__
        task.error_message = str(exc) or "任务执行出现未处理异常"
        task.finished_at = datetime.utcnow()
        db.commit()


def build_final_prompt(style_prompt: str, panel_prompt: str, panel_text: str) -> str:
    return "\n\n".join(
        [
            f"风格模板：{style_prompt.strip()}",
            "统一文字要求：图片内文字必须使用中文。请把 panel 原文作为图片内可读文字完整呈现，不要删改、翻译、总结或补充文案内容。可以通过字体大小、字重、颜色、位置、换行和留白做视觉强调，但不要把强调理解成 Markdown 或排版符号。",
            "文字禁止项：不要在图片文字里加入 #、##、**、*、-、项目符号、引号包裹、代码块符号、标题标记或任何 panel 原文之外的格式字符。",
            f"画面内容：{panel_prompt.strip()}",
            f"panel 原文：{panel_text.strip()}",
            "输出要求：图片比例、画布方向和分格构图以风格模板中的描述为准。无水印、无 Logo，不添加 panel 原文之外的无关文字。",
        ]
    )


def succeeded_images_by_panel(task: GenerationTask) -> dict[str, GeneratedImage]:
    return {
        image.panel_id: image
        for image in task.generated_images
        if image.status == GeneratedImageStatus.succeeded and image.asset_id is not None
    }


def delete_non_succeeded_images_for_panel(db: Session, task: GenerationTask, panel: TaskPanel) -> None:
    for image in list(task.generated_images):
        if image.panel_id == panel.id and (image.status != GeneratedImageStatus.succeeded or image.asset_id is None):
            db.delete(image)


def should_stop_for_cancel(db: Session, task: GenerationTask) -> bool:
    db.refresh(task)
    if task.status != TaskStatus.cancel_requested:
        return False
    task.status = TaskStatus.cancelled
    task.finished_at = datetime.utcnow()
    db.commit()
    logger.info("task cancelled task_id=%s", task.id)
    return True


def process_task(task_id: str) -> None:
    with SessionLocal() as db:
        task = load_task(db, task_id)
        if task is None or task.status in {TaskStatus.cancelled, TaskStatus.cancel_requested}:
            logger.info("task skipped task_id=%s reason=missing_or_cancelled", task_id)
            return

        logger.info(
            "task started task_id=%s owner_user_id=%s style_id=%s image_count_mode=%s requested_image_count=%s",
            task.id,
            task.owner_user_id,
            task.style_id,
            task.image_count_mode.value,
            task.requested_image_count,
        )
        task.status = TaskStatus.running
        task.started_at = task.started_at or datetime.utcnow()
        task.progress_current = 0
        task.progress_total = 3
        db.commit()

        existing_panels = sorted(task.panels, key=lambda item: item.panel_order)
        if existing_panels:
            task.progress_current = max(task.progress_current, 1)
            set_step(db, task, GenerationStepName.segment_story, StepStatus.succeeded)
            logger.info("task segmentation skipped task_id=%s existing_panel_count=%s", task.id, len(existing_panels))
        else:
            try:
                set_step(db, task, GenerationStepName.segment_story, StepStatus.running)
                segmentation = segment_story(
                    original_text=task.original_text,
                    image_count_mode=task.image_count_mode,
                    requested_image_count=task.requested_image_count,
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
                logger.info("task segmentation completed task_id=%s panel_count=%s", task.id, len(segmentation.panels))
            except LLMProviderError as exc:
                fail_step_and_task(db, task, GenerationStepName.segment_story, exc)
                return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        prompts_ready = bool(task.panels) and all(
            panel.prompt_status == PromptStatus.generated and bool(panel.generated_prompt)
            for panel in task.panels
        )
        if prompts_ready:
            task.progress_current = max(task.progress_current, 2)
            set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.succeeded)
            logger.info("task panel prompts skipped task_id=%s existing_panel_count=%s", task.id, len(task.panels))
        else:
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
                )
                prompts_by_order = {item.panel_order: item.prompt for item in prompt_result.panels}
                for panel in task.panels:
                    panel.generated_prompt = prompts_by_order[panel.panel_order]
                    panel.prompt_status = PromptStatus.generated
                    panel.prompt_model_snapshot = get_settings().siliconflow_model
                    panel.error_code = None
                    panel.error_message = None
                task.progress_current = 2
                set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.succeeded)
                logger.info("task panel prompts completed task_id=%s panel_count=%s", task.id, len(story_segments))
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
        logger.info(
            "task image generation started task_id=%s panel_count=%s reference_count=%s image_model=%s",
            task.id,
            len(task.panels),
            len(reference_paths),
            task.image_model_name_snapshot,
        )
        success_count = 0
        skipped_count = 0
        for panel in sorted(task.panels, key=lambda item: item.panel_order):
            if should_stop_for_cancel(db, task):
                return
            existing_successes = succeeded_images_by_panel(task)
            if panel.id in existing_successes:
                success_count += 1
                skipped_count += 1
                logger.info(
                    "task panel image skipped existing success task_id=%s panel_id=%s panel_order=%s image_id=%s",
                    task.id,
                    panel.id,
                    panel.panel_order,
                    existing_successes[panel.id].id,
                )
                continue
            delete_non_succeeded_images_for_panel(db, task, panel)
            db.flush()
            final_prompt = build_final_prompt(
                task.style_prompt_snapshot,
                panel.generated_prompt or "",
                panel.original_text_segment,
            )
            image = GeneratedImage(
                task_id=task.id,
                panel_id=panel.id,
                status=GeneratedImageStatus.running,
                final_prompt=final_prompt,
                image_model_name_snapshot=task.image_model_name_snapshot,
                started_at=datetime.utcnow(),
            )
            db.add(image)
            db.commit()
            db.refresh(image)

            try:
                logger.info(
                    "task panel image request task_id=%s panel_id=%s panel_order=%s image_id=%s prompt_chars=%s",
                    task.id,
                    panel.id,
                    panel.panel_order,
                    image.id,
                    len(final_prompt),
                )
                generated = generate_xg_image(
                    prompt=final_prompt,
                    reference_paths=reference_paths,
                    image_model_name=task.image_model_name_snapshot,
                )
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
                logger.info(
                    "task panel image succeeded task_id=%s panel_id=%s image_id=%s asset_storage_key=%s bytes=%s",
                    task.id,
                    panel.id,
                    image.id,
                    generated.storage_key,
                    generated.byte_size,
                )
            except (ImageProviderConfigError, ImageProviderResponseError) as exc:
                logger.warning(
                    "task panel image failed task_id=%s panel_id=%s image_id=%s error_type=%s error=%s",
                    task.id,
                    panel.id,
                    image.id,
                    exc.__class__.__name__,
                    exc,
                )
                image.status = GeneratedImageStatus.failed
                image.error_code = exc.__class__.__name__
                image.error_message = str(exc)
                image.finished_at = datetime.utcnow()
            db.commit()

        task = load_task(db, task_id)
        if task is None:
            return
        panel_count = len(task.panels)
        set_step(
            db,
            task,
            GenerationStepName.generate_images,
            StepStatus.succeeded if success_count == panel_count else StepStatus.failed,
        )
        task.progress_current = 3
        task.finished_at = datetime.utcnow()
        if success_count == panel_count:
            task.status = TaskStatus.succeeded
        elif success_count > 0:
            task.status = TaskStatus.partial_succeeded
        else:
            task.status = TaskStatus.failed
            task.error_code = "ImageGenerationFailed"
            task.error_message = "所有分镜图片生成失败"
        db.commit()
        logger.info(
            "task finished task_id=%s status=%s success_count=%s skipped_existing_success_count=%s panel_count=%s",
            task.id,
            task.status.value,
            success_count,
            skipped_count,
            panel_count,
        )
