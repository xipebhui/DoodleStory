import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import func, select
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
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskPanelCharacterAppearance,
)
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageStatus,
    GeneratedImageSourceType,
    GeneratedImageWorkflowStep,
    GenerationStepName,
    PanelType,
    PromptStatus,
    StepStatus,
    StoryInputMode,
    TaskStatus,
)
from app.services.character_references import (
    build_panel_reference_pack,
    characters_to_plans,
    clear_panel_character_links,
    ensure_character_reference_images,
    load_task_characters,
    persist_character_plans,
    save_character_plan_panel_links,
    save_panel_character_links,
)
from app.services.image_generation import ImageProviderConfigError, ImageProviderResponseError, generate_xg_image
from app.services.llm import (
    LLMProviderError,
    LLMResponseError,
    StorySegment,
    extract_task_characters,
    generate_panel_prompts,
    generate_panel_prompts_with_characters,
    ImageTextPlan,
    plan_storyboard_from_brief,
    revise_panel_prompt,
    segment_story,
)
from app.services.prompt_templates import render_prompt_template
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


async def enqueue_panel_edit(generated_image_id: str) -> None:
    asyncio.create_task(asyncio.to_thread(process_panel_edit, generated_image_id))
    logger.info("panel edit enqueued generated_image_id=%s", generated_image_id)


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
            selectinload(GenerationTask.panels)
            .selectinload(TaskPanel.character_appearances)
            .selectinload(TaskPanelCharacterAppearance.appearance)
            .selectinload(TaskCharacterAppearance.character),
            selectinload(GenerationTask.panels)
            .selectinload(TaskPanel.character_appearances)
            .selectinload(TaskPanelCharacterAppearance.appearance)
            .selectinload(TaskCharacterAppearance.reference_image),
            selectinload(GenerationTask.steps),
            selectinload(GenerationTask.characters)
            .selectinload(TaskCharacter.appearances)
            .selectinload(TaskCharacterAppearance.reference_image),
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


def task_progress_total(task: GenerationTask) -> int:
    total = 3
    if task.story_input_mode == StoryInputMode.adapted:
        total += 1
    if task.use_character_references:
        total += 2
    return total


def panel_story_segments(task: GenerationTask) -> list[StorySegment]:
    return [
        StorySegment(
            panel_order=panel.panel_order,
            panel_type=panel.panel_type,
            text=panel.original_text_segment,
            narration_text=panel.narration_text,
            dialogue_text=panel.dialogue_text,
            visual_prompt=panel.generated_prompt,
            image_text=parse_image_text_json(panel.image_text_json),
            text_layout=panel.text_layout,
        )
        for panel in sorted(task.panels, key=lambda item: item.panel_order)
    ]


def story_text_for_generation(task: GenerationTask) -> str:
    if task.story_input_mode == StoryInputMode.adapted and task.adapted_story_text:
        return f"用户原始方案：\n{task.original_text}\n\n图文分镜概要：\n{task.adapted_story_text}"
    return task.original_text


def image_text_to_dict(image_text: ImageTextPlan | dict[str, str | None] | None) -> dict[str, str | None]:
    if image_text is None:
        return {"title": None, "narration": None, "dialogue": None, "emphasis": None}
    if isinstance(image_text, ImageTextPlan):
        return image_text.model_dump()
    return {
        "title": image_text.get("title"),
        "narration": image_text.get("narration"),
        "dialogue": image_text.get("dialogue"),
        "emphasis": image_text.get("emphasis"),
    }


def image_text_to_json(image_text: ImageTextPlan | dict[str, str | None] | None) -> str:
    return json.dumps(image_text_to_dict(image_text), ensure_ascii=False)


def parse_image_text_json(value: str | None) -> dict[str, str | None] | None:
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        return None
    return {
        "title": parsed.get("title"),
        "narration": parsed.get("narration"),
        "dialogue": parsed.get("dialogue"),
        "emphasis": parsed.get("emphasis"),
    }


def image_text_block(image_text: ImageTextPlan | dict[str, str | None] | None, panel_type: PanelType) -> str:
    values = image_text_to_dict(image_text)
    lines = []
    title = values.get("title")
    narration = values.get("narration")
    if title:
        label = "大标题" if panel_type == PanelType.cover else "标题"
        lines.append(f"{label}：“{title.strip()}”")
    if narration:
        lines.append(f"旁白：“{narration.strip()}”")
    return "\n".join(lines) if lines else "无图片内文字。"


def scene_block(story_beat: str, visual_prompt: str, image_text: ImageTextPlan | dict[str, str | None] | None) -> str:
    lines = [story_beat.strip(), visual_prompt.strip()]
    dialogue = dialogue_block(image_text)
    if dialogue:
        lines.append(dialogue)
    return "\n".join(line for line in lines if line)


def dialogue_block(image_text: ImageTextPlan | dict[str, str | None] | None) -> str | None:
    values = image_text_to_dict(image_text)
    dialogue = values.get("dialogue")
    if not dialogue:
        return None
    return "\n".join(dialogue_lines_for_prompt(dialogue))


def dialogue_lines_for_prompt(dialogue: str) -> list[str]:
    lines: list[str] = []
    for raw_line in dialogue.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        speaker, content = split_dialogue_speaker(line)
        if speaker and content:
            lines.append(f"{speaker}说：“{content}”")
        else:
            lines.append(f"对白：“{line}”")
    return lines


def split_dialogue_speaker(line: str) -> tuple[str | None, str | None]:
    for separator in ("：", ":"):
        if separator not in line:
            continue
        speaker, content = line.split(separator, 1)
        speaker = speaker.strip()
        content = content.strip()
        if 1 <= len(speaker) <= 12 and content:
            return speaker, content
    return None, None


def reference_notes_block(reference_notes: list[str] | None) -> str:
    if not reference_notes:
        return "不需要额外参考图说明。"
    return "\n".join(reference_notes)


def style_reference_notes(start_index: int, reference_count: int) -> list[str]:
    if reference_count <= 0:
        return []
    end_index = start_index + reference_count - 1
    if start_index == end_index:
        return [f"风格参考（参考图{start_index}）"]
    return [f"风格参考（参考图{start_index}-{end_index}）"]


def build_final_prompt(
    style_prompt: str,
    aspect_ratio: str,
    visual_prompt: str,
    story_beat: str,
    panel_type: PanelType = PanelType.scene,
    image_text: ImageTextPlan | dict[str, str | None] | None = None,
    text_layout: str | None = None,
    reference_notes: list[str] | None = None,
) -> str:
    return render_prompt_template(
        "final_image_prompt_v1.md",
        {
            "aspect_ratio": aspect_ratio,
            "panel_type": "封面图" if panel_type == PanelType.cover else "剧情分镜",
            "scene_block": scene_block(story_beat, visual_prompt, image_text),
            "image_text_block": image_text_block(image_text, panel_type),
            "reference_notes_block": reference_notes_block(reference_notes),
        },
    )


def current_succeeded_images_by_panel(task: GenerationTask) -> dict[str, GeneratedImage]:
    return {
        image.panel_id: image
        for image in task.generated_images
        if image.is_current and image.status == GeneratedImageStatus.succeeded and image.asset_id is not None
    }


def next_generation_number(db: Session, panel_id: str) -> int:
    current_max = db.scalar(select(func.max(GeneratedImage.generation_number)).where(GeneratedImage.panel_id == panel_id))
    return (current_max or 0) + 1


def mark_image_current(db: Session, image: GeneratedImage) -> None:
    for existing in db.scalars(select(GeneratedImage).where(GeneratedImage.panel_id == image.panel_id)).all():
        existing.is_current = existing.id == image.id


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
        task.progress_total = task_progress_total(task)
        db.commit()

        if task.story_input_mode == StoryInputMode.adapted:
            if task.adapted_story_text and task.panels and all(panel.generated_prompt for panel in task.panels):
                task.progress_current = max(task.progress_current, 1)
                set_step(db, task, GenerationStepName.adapt_story, StepStatus.succeeded)
                logger.info("task storyboard planning skipped task_id=%s", task.id)
            else:
                try:
                    set_step(db, task, GenerationStepName.adapt_story, StepStatus.running)
                    storyboard = plan_storyboard_from_brief(
                        brief_text=task.original_text,
                        style_prompt=task.style_prompt_snapshot,
                        image_count_mode=task.image_count_mode,
                        requested_image_count=task.requested_image_count,
                    )
                    task.adapted_story_title = storyboard.story_title
                    task.adapted_story_hook = storyboard.story_hook
                    task.adapted_story_text = storyboard.story_outline
                    task.display_title = storyboard.story_title[:120]
                    for existing_panel in list(task.panels):
                        db.delete(existing_panel)
                    db.flush()
                    for panel in storyboard.panels:
                        db.add(
                            TaskPanel(
                                task_id=task.id,
                                panel_order=panel.panel_order,
                                panel_type=panel.panel_type,
                                original_text_segment=panel.story_beat,
                                narration_text=panel.image_text.narration,
                                dialogue_text=panel.image_text.dialogue,
                                image_text_json=image_text_to_json(panel.image_text),
                                text_layout=panel.text_layout,
                                prompt_status=PromptStatus.generated,
                                generated_prompt=panel.visual_prompt,
                                prompt_model_snapshot=get_settings().siliconflow_model,
                            )
                        )
                    task.progress_current = 1
                    set_step(db, task, GenerationStepName.adapt_story, StepStatus.succeeded)
                    logger.info(
                        "task storyboard planning completed task_id=%s title=%s panel_count=%s",
                        task.id,
                        storyboard.story_title,
                        len(storyboard.panels),
                    )
                except LLMProviderError as exc:
                    fail_step_and_task(db, task, GenerationStepName.adapt_story, exc)
                    return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        existing_panels = sorted(task.panels, key=lambda item: item.panel_order)
        if existing_panels:
            task.progress_current = max(task.progress_current, 2 if task.story_input_mode == StoryInputMode.adapted else 1)
            set_step(db, task, GenerationStepName.segment_story, StepStatus.succeeded)
            logger.info("task segmentation skipped task_id=%s existing_panel_count=%s", task.id, len(existing_panels))
        else:
            try:
                set_step(db, task, GenerationStepName.segment_story, StepStatus.running)
                if task.story_input_mode == StoryInputMode.adapted:
                    raise LLMResponseError("故事方案模式应在方案规划步骤生成 panels")
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
                            panel_type=panel.panel_type,
                            original_text_segment=panel.text,
                            narration_text=panel.narration_text or panel.text,
                            dialogue_text=panel.dialogue_text,
                        )
                    )
                task.progress_current = 2 if task.story_input_mode == StoryInputMode.adapted else 1
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

        style = db.scalar(
            select(Style)
            .where(Style.id == task.style_id)
            .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
        )
        if style is None or not style.reference_images:
            fail_step_and_task(
                db,
                task,
                GenerationStepName.generate_character_references
                if task.use_character_references
                else GenerationStepName.generate_images,
                ImageProviderConfigError("风格至少需要一张参考图"),
            )
            return

        style_reference_paths = [resolve_storage_key(reference.asset.storage_key) for reference in style.reference_images]
        story_segments = panel_story_segments(task)

        if task.use_character_references:
            characters = load_task_characters(db, task.id)
            if characters:
                task.progress_current = max(task.progress_current, 3 if task.story_input_mode == StoryInputMode.adapted else 2)
                set_step(db, task, GenerationStepName.extract_characters, StepStatus.succeeded)
                logger.info("task character extraction skipped task_id=%s character_count=%s", task.id, len(characters))
            else:
                try:
                    set_step(db, task, GenerationStepName.extract_characters, StepStatus.running)
                    character_result = extract_task_characters(
                        original_text=story_text_for_generation(task),
                        style_prompt=task.style_prompt_snapshot,
                        panels=story_segments,
                    )
                    if not character_result.characters:
                        raise LLMResponseError("未识别到可用于参考图的主要人物")
                    persist_character_plans(db, task, character_result.characters)
                    if task.story_input_mode == StoryInputMode.adapted:
                        task = load_task(db, task_id)
                        if task is None:
                            return
                        save_character_plan_panel_links(
                            db=db,
                            task=task,
                            character_plans=character_result.characters,
                        )
                    task.progress_current = 3 if task.story_input_mode == StoryInputMode.adapted else 2
                    set_step(db, task, GenerationStepName.extract_characters, StepStatus.succeeded)
                    logger.info(
                        "task character extraction completed task_id=%s character_count=%s",
                        task.id,
                        len(character_result.characters),
                    )
                except LLMProviderError as exc:
                    fail_step_and_task(db, task, GenerationStepName.extract_characters, exc)
                    return

            task = load_task(db, task_id)
            if task is None:
                return
            if should_stop_for_cancel(db, task):
                return
            try:
                set_step(db, task, GenerationStepName.generate_character_references, StepStatus.running)
                ensure_character_reference_images(
                    db=db,
                    task=task,
                    style_reference_paths=style_reference_paths,
                )
                task.progress_current = 3
                if task.story_input_mode == StoryInputMode.adapted:
                    task.progress_current = 4
                set_step(db, task, GenerationStepName.generate_character_references, StepStatus.succeeded)
                logger.info("task character reference images completed task_id=%s", task.id)
            except (ImageProviderConfigError, ImageProviderResponseError) as exc:
                fail_step_and_task(db, task, GenerationStepName.generate_character_references, exc)
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
        prompts_progress = task.progress_total - 1
        if prompts_ready:
            task.progress_current = max(task.progress_current, prompts_progress)
            set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.succeeded)
            logger.info("task panel prompts skipped task_id=%s existing_panel_count=%s", task.id, len(task.panels))
        else:
            try:
                set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.running)
                if task.use_character_references:
                    character_plans = characters_to_plans(load_task_characters(db, task.id))
                    prompt_result = generate_panel_prompts_with_characters(
                        original_text=story_text_for_generation(task),
                        style_prompt=task.style_prompt_snapshot,
                        panels=story_segments,
                        characters=character_plans,
                    )
                    clear_panel_character_links(db, task)
                else:
                    prompt_result = generate_panel_prompts(
                        original_text=story_text_for_generation(task),
                        style_prompt=task.style_prompt_snapshot,
                        panels=story_segments,
                    )
                for panel in task.panels:
                    prompt_item = next(item for item in prompt_result.panels if item.panel_order == panel.panel_order)
                    panel.generated_prompt = prompt_item.visual_prompt
                    panel.narration_text = prompt_item.image_text.narration
                    panel.dialogue_text = prompt_item.image_text.dialogue
                    panel.image_text_json = image_text_to_json(prompt_item.image_text)
                    panel.text_layout = prompt_item.text_layout
                    panel.prompt_status = PromptStatus.generated
                    panel.prompt_model_snapshot = get_settings().siliconflow_model
                    panel.error_code = None
                    panel.error_message = None
                    if task.use_character_references:
                        save_panel_character_links(
                            db=db,
                            task=task,
                            panel=panel,
                            appearance_keys=getattr(prompt_item, "appearance_keys", []),
                            usage_notes=getattr(prompt_item, "usage_notes", {}),
                        )
                task.progress_current = prompts_progress
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
            existing_successes = current_succeeded_images_by_panel(task)
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
            try:
                if task.use_character_references:
                    reference_pack = build_panel_reference_pack(panel=panel, style_reference_paths=reference_paths)
                    panel_reference_paths = reference_pack.paths
                    reference_notes = reference_pack.notes
                    character_reference_count = reference_pack.character_count
                else:
                    panel_reference_paths = reference_paths
                    reference_notes = style_reference_notes(1, len(reference_paths))
                    character_reference_count = 0
                final_prompt = build_final_prompt(
                    task.style_prompt_snapshot,
                    task.style_aspect_ratio_snapshot,
                    panel.generated_prompt or "",
                    panel.original_text_segment,
                    panel_type=panel.panel_type,
                    image_text=parse_image_text_json(panel.image_text_json)
                    or {
                        "title": None,
                        "narration": panel.narration_text,
                        "dialogue": panel.dialogue_text,
                        "emphasis": None,
                    },
                    text_layout=panel.text_layout,
                    reference_notes=reference_notes,
                )
            except ImageProviderConfigError as exc:
                fail_step_and_task(db, task, GenerationStepName.generate_images, exc)
                return
            image = GeneratedImage(
                task_id=task.id,
                panel_id=panel.id,
                status=GeneratedImageStatus.running,
                generation_number=next_generation_number(db, panel.id),
                is_current=False,
                source_type=GeneratedImageSourceType.retry if task.attempts > 0 else GeneratedImageSourceType.initial,
                workflow_step=GeneratedImageWorkflowStep.generate_image,
                image_prompt=panel.generated_prompt,
                image_text_json=panel.image_text_json,
                text_layout=panel.text_layout,
                final_prompt=final_prompt,
                image_model_name_snapshot=task.image_model_name_snapshot,
                started_at=datetime.utcnow(),
            )
            db.add(image)
            db.commit()
            db.refresh(image)

            try:
                logger.info(
                    "task panel image request task_id=%s panel_id=%s panel_order=%s image_id=%s prompt_chars=%s reference_count=%s character_reference_count=%s",
                    task.id,
                    panel.id,
                    panel.panel_order,
                    image.id,
                    len(final_prompt),
                    len(panel_reference_paths),
                    character_reference_count,
                )
                generated = generate_xg_image(
                    prompt=final_prompt,
                    reference_paths=panel_reference_paths,
                    image_model_name=task.image_model_name_snapshot,
                    aspect_ratio=task.style_aspect_ratio_snapshot,
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
                mark_image_current(db, image)
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
        task.progress_current = task.progress_total
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


def load_generated_image(db: Session, generated_image_id: str) -> GeneratedImage | None:
    return db.scalar(
        select(GeneratedImage)
        .where(GeneratedImage.id == generated_image_id)
        .options(
            selectinload(GeneratedImage.task),
            selectinload(GeneratedImage.panel)
            .selectinload(TaskPanel.character_appearances)
            .selectinload(TaskPanelCharacterAppearance.appearance)
            .selectinload(TaskCharacterAppearance.character),
            selectinload(GeneratedImage.panel)
            .selectinload(TaskPanel.character_appearances)
            .selectinload(TaskPanelCharacterAppearance.appearance)
            .selectinload(TaskCharacterAppearance.reference_image),
            selectinload(GeneratedImage.asset),
        )
    )


def process_panel_edit(generated_image_id: str) -> None:
    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            logger.warning("panel edit skipped missing generated_image_id=%s", generated_image_id)
            return
        task = image.task
        panel = image.panel
        logger.info(
            "panel edit started generated_image_id=%s task_id=%s panel_id=%s generation_number=%s",
            image.id,
            task.id,
            panel.id,
            image.generation_number,
        )

        image.status = GeneratedImageStatus.running
        image.workflow_step = GeneratedImageWorkflowStep.rewrite_prompt
        image.started_at = image.started_at or datetime.utcnow()
        image.error_code = None
        image.error_message = None
        db.commit()

        try:
            revision = revise_panel_prompt(
                original_text=story_text_for_generation(task),
                style_prompt=task.style_prompt_snapshot,
                panel_text=panel.original_text_segment,
                current_prompt=image.previous_prompt or panel.generated_prompt or "",
                current_image_text=parse_image_text_json(image.image_text_json or panel.image_text_json),
                current_text_layout=image.text_layout or panel.text_layout,
                user_instruction=image.user_instruction or "",
            )
            image.image_prompt = revision.visual_prompt
            image.image_text_json = image_text_to_json(revision.image_text)
            image.text_layout = revision.text_layout
            image.prompt_change_summary = revision.change_summary
            image.llm_model_snapshot = get_settings().siliconflow_model
            image.final_prompt = build_final_prompt(
                task.style_prompt_snapshot,
                task.style_aspect_ratio_snapshot,
                revision.visual_prompt,
                panel.original_text_segment,
                panel_type=panel.panel_type,
                image_text=revision.image_text,
                text_layout=revision.text_layout,
            )
            image.workflow_step = GeneratedImageWorkflowStep.generate_image
            db.commit()
            logger.info(
                "panel edit prompt revised generated_image_id=%s prompt_chars=%s change_summary=%s",
                image.id,
                len(revision.visual_prompt),
                revision.change_summary,
            )
        except LLMProviderError as exc:
            logger.warning(
                "panel edit prompt revision failed generated_image_id=%s error_type=%s error=%s",
                image.id,
                exc.__class__.__name__,
                exc,
            )
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            db.commit()
            return

        style = db.scalar(
            select(Style)
            .where(Style.id == task.style_id)
            .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
        )
        if style is None or not style.reference_images:
            exc = ImageProviderConfigError("风格至少需要一张参考图")
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            db.commit()
            return

        style_reference_paths = [resolve_storage_key(reference.asset.storage_key) for reference in style.reference_images]
        if task.use_character_references:
            try:
                reference_pack = build_panel_reference_pack(panel=panel, style_reference_paths=style_reference_paths)
            except ImageProviderConfigError as exc:
                image.status = GeneratedImageStatus.failed
                image.error_code = exc.__class__.__name__
                image.error_message = str(exc)
                image.finished_at = datetime.utcnow()
                db.commit()
                return
            reference_paths = reference_pack.paths
            reference_notes = reference_pack.notes
            image.final_prompt = build_final_prompt(
                task.style_prompt_snapshot,
                task.style_aspect_ratio_snapshot,
                image.image_prompt or "",
                panel.original_text_segment,
                panel_type=panel.panel_type,
                image_text=parse_image_text_json(image.image_text_json)
                or {
                    "title": None,
                    "narration": panel.narration_text,
                    "dialogue": panel.dialogue_text,
                    "emphasis": None,
                },
                text_layout=image.text_layout or panel.text_layout,
                reference_notes=reference_notes,
            )
            db.commit()
        else:
            reference_paths = style_reference_paths
            reference_notes = style_reference_notes(1, len(style_reference_paths))
            image.final_prompt = build_final_prompt(
                task.style_prompt_snapshot,
                task.style_aspect_ratio_snapshot,
                image.image_prompt or "",
                panel.original_text_segment,
                panel_type=panel.panel_type,
                image_text=parse_image_text_json(image.image_text_json)
                or {
                    "title": None,
                    "narration": panel.narration_text,
                    "dialogue": panel.dialogue_text,
                    "emphasis": None,
                },
                text_layout=image.text_layout or panel.text_layout,
                reference_notes=reference_notes,
            )
            db.commit()
        try:
            logger.info(
                "panel edit image request generated_image_id=%s task_id=%s panel_id=%s prompt_chars=%s reference_count=%s",
                image.id,
                task.id,
                panel.id,
                len(image.final_prompt or ""),
                len(reference_paths),
            )
            generated = generate_xg_image(
                prompt=image.final_prompt or "",
                reference_paths=reference_paths,
                image_model_name=image.image_model_name_snapshot,
                aspect_ratio=task.style_aspect_ratio_snapshot,
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
            panel.generated_prompt = image.image_prompt
            panel.image_text_json = image.image_text_json
            panel.text_layout = image.text_layout
            parsed_image_text = parse_image_text_json(image.image_text_json)
            if parsed_image_text:
                panel.narration_text = parsed_image_text.get("narration")
                panel.dialogue_text = parsed_image_text.get("dialogue")
            panel.prompt_status = PromptStatus.generated
            panel.prompt_model_snapshot = image.llm_model_snapshot
            panel.error_code = None
            panel.error_message = None
            mark_image_current(db, image)
            logger.info(
                "panel edit image succeeded generated_image_id=%s task_id=%s panel_id=%s asset_storage_key=%s bytes=%s",
                image.id,
                task.id,
                panel.id,
                generated.storage_key,
                generated.byte_size,
            )
        except (ImageProviderConfigError, ImageProviderResponseError) as exc:
            logger.warning(
                "panel edit image failed generated_image_id=%s task_id=%s panel_id=%s error_type=%s error=%s",
                image.id,
                task.id,
                panel.id,
                exc.__class__.__name__,
                exc,
            )
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
        db.commit()
