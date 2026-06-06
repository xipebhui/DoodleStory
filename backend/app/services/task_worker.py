import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic

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
from app.services.image_generation import (
    GeneratedImageFile,
    ImageProviderConfigError,
    ImageProviderResponseError,
    generate_xg_image,
)
from app.services.llm import (
    LLMProviderError,
    LLMResponseError,
    StorySegment,
    extract_task_characters,
    generate_panel_prompts,
    generate_panel_prompts_with_characters,
    ImageTextPlan,
    parse_extracted_storyboard,
    plan_storyboard_from_brief,
    revise_panel_prompt,
    segment_story,
)
from app.services.prompt_logging import log_prompt_trace

_queue: asyncio.Queue[str] | None = None
_worker_tasks: list[asyncio.Task[None]] = []
_running_task_ids: set[str] = set()
_running_task_ids_lock: asyncio.Lock | None = None
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedPanelImageRequest:
    panel_id: str
    panel_order: int
    image_id: str
    final_prompt: str
    reference_paths: list[Path]
    reference_count: int
    character_reference_count: int


@dataclass(frozen=True)
class PanelImageGenerationResult:
    request: PreparedPanelImageRequest
    generated: GeneratedImageFile | None = None
    error: Exception | None = None


def generate_panel_image_request(
    *,
    task_id: str,
    image_model_name: str,
    aspect_ratio: str,
    request: PreparedPanelImageRequest,
) -> PanelImageGenerationResult:
    started = monotonic()
    try:
        logger.info(
            "story_drawing_debug provider_request_start task_id=%s panel_id=%s panel_order=%s image_id=%s image_model=%s aspect_ratio=%s prompt_chars=%s reference_count=%s character_reference_count=%s",
            task_id,
            request.panel_id,
            request.panel_order,
            request.image_id,
            image_model_name,
            aspect_ratio,
            len(request.final_prompt),
            request.reference_count,
            request.character_reference_count,
        )
        generated = generate_xg_image(
            prompt=request.final_prompt,
            reference_paths=request.reference_paths,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
        logger.info(
            "story_drawing_debug provider_request_done task_id=%s panel_id=%s panel_order=%s image_id=%s provider_request_id=%s storage_backend=%s storage_key=%s byte_size=%s elapsed_ms=%s",
            task_id,
            request.panel_id,
            request.panel_order,
            request.image_id,
            generated.provider_request_id,
            generated.storage_backend.value,
            generated.storage_key,
            generated.byte_size,
            round((monotonic() - started) * 1000),
        )
        return PanelImageGenerationResult(request=request, generated=generated)
    except (ImageProviderConfigError, ImageProviderResponseError) as exc:
        logger.warning(
            "story_drawing_debug provider_request_failed task_id=%s panel_id=%s panel_order=%s image_id=%s error_type=%s error=%s elapsed_ms=%s",
            task_id,
            request.panel_id,
            request.panel_order,
            request.image_id,
            exc.__class__.__name__,
            exc,
            round((monotonic() - started) * 1000),
        )
        return PanelImageGenerationResult(request=request, error=exc)
    except Exception as exc:
        logger.exception(
            "story_drawing_debug provider_request_unexpected_failed task_id=%s panel_id=%s image_id=%s elapsed_ms=%s",
            task_id,
            request.panel_id,
            request.image_id,
            round((monotonic() - started) * 1000),
        )
        return PanelImageGenerationResult(request=request, error=exc)


def task_trace_context(task: GenerationTask, step: str, **extra: object) -> dict[str, object]:
    return {
        "task_id": task.id,
        "owner_user_id": task.owner_user_id,
        "style_id": task.style_id,
        "story_input_mode": task.story_input_mode.value,
        "image_count_mode": task.image_count_mode.value,
        "requested_image_count": task.requested_image_count,
        "use_character_references": task.use_character_references,
        "step": step,
        **extra,
    }


def init_task_queue() -> None:
    global _queue, _worker_tasks, _running_task_ids_lock
    settings = get_settings()
    _queue = asyncio.Queue()
    _running_task_ids.clear()
    _running_task_ids_lock = asyncio.Lock()
    _worker_tasks = [
        asyncio.create_task(worker_loop(worker_index=worker_index))
        for worker_index in range(settings.task_worker_concurrency)
    ]
    logger.info("task queue initialized worker_count=%s", len(_worker_tasks))


async def shutdown_task_queue() -> None:
    global _worker_tasks, _running_task_ids_lock
    if not _worker_tasks:
        return
    for worker_task in _worker_tasks:
        worker_task.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks = []
    _running_task_ids.clear()
    _running_task_ids_lock = None
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


async def worker_loop(*, worker_index: int) -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    if _running_task_ids_lock is None:
        raise RuntimeError("任务运行锁尚未初始化")
    logger.info("task worker loop started worker_index=%s", worker_index)
    while True:
        task_id = await _queue.get()
        should_process = False
        try:
            async with _running_task_ids_lock:
                if task_id in _running_task_ids:
                    logger.warning(
                        "task worker skipped duplicate running task_id=%s worker_index=%s queue_size=%s",
                        task_id,
                        worker_index,
                        _queue.qsize(),
                    )
                    continue
                _running_task_ids.add(task_id)
                should_process = True
            logger.info(
                "task worker picked task_id=%s worker_index=%s queue_size=%s",
                task_id,
                worker_index,
                _queue.qsize(),
            )
            await asyncio.to_thread(process_task, task_id)
        except Exception as exc:
            logger.exception("task worker unexpected error task_id=%s worker_index=%s", task_id, worker_index)
            mark_task_failed_by_unhandled_error(task_id, exc)
        finally:
            if should_process:
                async with _running_task_ids_lock:
                    _running_task_ids.discard(task_id)
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
    total = 1
    if task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
        total += 1
    else:
        total += 2
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
    if task.story_input_mode == StoryInputMode.extracted_storyboard and task.adapted_story_text:
        return f"内容提取原文：\n{task.original_text}\n\n提取分镜概要：\n{task.adapted_story_text}"
    return task.original_text


def image_text_to_dict(image_text: ImageTextPlan | dict[str, str | None] | None) -> dict[str, str | None]:
    if image_text is None:
        return {"title": None, "narration": None, "dialogue": None, "inner_os": None, "emphasis": None}
    if isinstance(image_text, ImageTextPlan):
        return image_text.model_dump()
    return {
        "title": image_text.get("title"),
        "narration": image_text.get("narration"),
        "dialogue": image_text.get("dialogue"),
        "inner_os": image_text.get("inner_os"),
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
        "inner_os": parsed.get("inner_os"),
        "emphasis": parsed.get("emphasis"),
    }


def image_text_block(image_text: ImageTextPlan | dict[str, str | None] | None, panel_type: PanelType) -> str:
    values = image_text_to_dict(image_text)
    lines = []
    title = values.get("title")
    narration = values.get("narration")
    inner_os = values.get("inner_os")
    emphasis = values.get("emphasis")
    if title:
        lines.append(f"标题：「{title.strip()}」")
    if narration:
        lines.append(f"旁白：「{narration.strip()}」")
    dialogue = values.get("dialogue")
    if dialogue:
        lines.append(f"对白：「{dialogue.strip()}」")
    if inner_os:
        lines.append(f"内心OS：「{inner_os.strip()}」")
    if emphasis:
        lines.append(f"强调：「{emphasis.strip()}」")
    return "\n".join(lines)


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


def visual_prompt_has_dialogue(visual_prompt: str) -> bool:
    return bool(
        re.search(
            r"(说|问|回答|喊|叫|吼|劝|骂|质问|反问|嘀咕|喃喃|怒吼|低声|开口|对白|台词)[：:：]?[“\"']",
            visual_prompt,
        )
    )


def text_rules_block(visual_prompt: str, image_text: ImageTextPlan | dict[str, str | None] | None) -> str:
    common_rule = "不要添加指定文字之外的任何文字、Logo 或水印。"
    values = image_text_to_dict(image_text)
    rules = ["所有图片内文字必须字号偏大、清晰可读，不能挤压变形，优先保证文字可读性。"]
    if values.get("narration"):
        rules.append("旁白必须用漫画旁白框或字幕框呈现，放在画面上方、下方或格子边缘，不要画成对白气泡。")
    if dialogue_block(image_text) or visual_prompt_has_dialogue(visual_prompt):
        rules.append("对白必须出现在对应人物附近的对白气泡中，气泡尾巴指向说话人物；气泡里只写人物说出的句子，不写说话人名字和冒号。")
    if values.get("inner_os"):
        rules.append("内心OS必须用思想气泡、虚线气泡或半透明心理独白框呈现，明显区别于对白，不能画成说出口的台词。")
    rules.append(common_rule)
    return "".join(rules)


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


def build_original_story_final_prompt(
    aspect_ratio: str,
    visual_prompt: str,
    reference_notes: list[str] | None = None,
    exact_text: str = "",
) -> str:
    return "\n".join(
        [
            "参考：",
            reference_notes_block(reference_notes),
            "",
            f"画面比例：{aspect_ratio}",
            "",
            "画面：",
            visual_prompt.strip(),
            "",
            "必须把下面这段原文完整写入图片中，逐字一致，不能增加、删除、替换或改写任何一个字，不能添加“旁白”“字幕”“标题”等标签：",
            f"「{exact_text}」",
            "",
            "不要添加这段原文之外的任何文字、Logo 或水印。",
        ]
    ).strip()


def build_adapted_story_final_prompt(
    aspect_ratio: str,
    visual_prompt: str,
    story_beat: str,
    panel_type: PanelType = PanelType.scene,
    image_text: ImageTextPlan | dict[str, str | None] | None = None,
    reference_notes: list[str] | None = None,
    text_layout: str | None = None,
) -> str:
    lines = [
        "参考：",
        reference_notes_block(reference_notes),
        "",
        f"画面比例：{aspect_ratio}",
        "",
        "剧情意图：",
        story_beat.strip(),
        "",
        "画面：",
        visual_prompt.strip(),
    ]
    if text_layout:
        lines.extend(
            [
                "",
                "分格/多栏布局：",
                text_layout.strip(),
            ]
        )
    image_text_lines = image_text_block(image_text, panel_type)
    if image_text_lines:
        lines.extend(
            [
                "",
                "需要写入图片的文字和表现形式如下；只把引号内文字画进图片，冒号前的类型说明不要画进图片：",
                image_text_lines,
            ]
        )
    rules = text_rules_block(visual_prompt, image_text)
    if rules:
        lines.extend(["", rules])
    return "\n".join(line for line in lines if line is not None).strip()


def build_panel_final_prompt(
    task: GenerationTask,
    panel: TaskPanel,
    visual_prompt: str,
    image_text: ImageTextPlan | dict[str, str | None] | None,
    reference_notes: list[str] | None = None,
) -> str:
    if task.story_input_mode == StoryInputMode.original:
        return build_original_story_final_prompt(
            aspect_ratio=task.style_aspect_ratio_snapshot,
            visual_prompt=visual_prompt,
            reference_notes=reference_notes,
            exact_text=panel.original_text_segment,
        )
    return build_adapted_story_final_prompt(
        aspect_ratio=task.style_aspect_ratio_snapshot,
        visual_prompt=visual_prompt,
        story_beat=panel.original_text_segment,
        panel_type=panel.panel_type,
        image_text=image_text,
        reference_notes=reference_notes,
        text_layout=panel.text_layout,
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
    task_started = monotonic()
    with SessionLocal() as db:
        task = load_task(db, task_id)
        if task is None or task.status in {TaskStatus.cancelled, TaskStatus.cancel_requested}:
            logger.info("task skipped task_id=%s reason=missing_or_cancelled", task_id)
            return

        logger.info(
            "story_drawing_debug task_start task_id=%s owner_user_id=%s style_id=%s story_input_mode=%s image_count_mode=%s requested_image_count=%s use_character_references=%s image_model=%s style_prompt_chars=%s original_text_chars=%s",
            task.id,
            task.owner_user_id,
            task.style_id,
            task.story_input_mode.value,
            task.image_count_mode.value,
            task.requested_image_count,
            task.use_character_references,
            task.image_model_name_snapshot,
            len(task.style_prompt_snapshot or ""),
            len(task.original_text or ""),
        )
        task.status = TaskStatus.running
        task.started_at = task.started_at or datetime.utcnow()
        task.progress_current = 0
        task.progress_total = task_progress_total(task)
        db.commit()

        if task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
            if task.adapted_story_text and task.panels and all(panel.generated_prompt for panel in task.panels):
                task.progress_current = max(task.progress_current, 1)
                set_step(db, task, GenerationStepName.adapt_story, StepStatus.succeeded)
                logger.info("story_drawing_debug storyboard_skipped task_id=%s existing_panel_count=%s", task.id, len(task.panels))
            else:
                try:
                    set_step(db, task, GenerationStepName.adapt_story, StepStatus.running)
                    step_started = monotonic()
                    logger.info(
                        "story_drawing_debug storyboard_start task_id=%s story_input_mode=%s requested_image_count=%s image_count_mode=%s brief_chars=%s",
                        task.id,
                        task.story_input_mode.value,
                        task.requested_image_count,
                        task.image_count_mode.value,
                        len(task.original_text or ""),
                    )
                    if task.story_input_mode == StoryInputMode.extracted_storyboard:
                        storyboard = parse_extracted_storyboard(
                            extracted_text=task.original_text,
                            style_prompt=task.style_prompt_snapshot,
                            image_count_mode=task.image_count_mode,
                            requested_image_count=task.requested_image_count,
                            trace_context=task_trace_context(task, "adapt_story"),
                        )
                    else:
                        storyboard = plan_storyboard_from_brief(
                            brief_text=task.original_text,
                            style_prompt=task.style_prompt_snapshot,
                            image_count_mode=task.image_count_mode,
                            requested_image_count=task.requested_image_count,
                            trace_context=task_trace_context(task, "adapt_story"),
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
                        "story_drawing_debug storyboard_done task_id=%s title=%s panel_count=%s outline_chars=%s elapsed_ms=%s",
                        task.id,
                        storyboard.story_title,
                        len(storyboard.panels),
                        len(storyboard.story_outline),
                        round((monotonic() - step_started) * 1000),
                    )
                except LLMProviderError as exc:
                    fail_step_and_task(db, task, GenerationStepName.adapt_story, exc)
                    return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        planning_mode = task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}
        existing_panels = sorted(task.panels, key=lambda item: item.panel_order)
        if planning_mode:
            if not existing_panels:
                fail_step_and_task(db, task, GenerationStepName.adapt_story, LLMResponseError("分镜规划完成后没有生成 panels"))
                return
            logger.info(
                "story_drawing_debug segmentation_not_applicable task_id=%s story_input_mode=%s existing_panel_count=%s",
                task.id,
                task.story_input_mode.value,
                len(existing_panels),
            )
        elif existing_panels:
            task.progress_current = max(task.progress_current, 1)
            set_step(db, task, GenerationStepName.segment_story, StepStatus.succeeded)
            logger.info("story_drawing_debug segmentation_skipped task_id=%s existing_panel_count=%s", task.id, len(existing_panels))
        else:
            try:
                set_step(db, task, GenerationStepName.segment_story, StepStatus.running)
                step_started = monotonic()
                logger.info(
                    "story_drawing_debug segmentation_start task_id=%s original_text_chars=%s image_count_mode=%s requested_image_count=%s",
                    task.id,
                    len(task.original_text or ""),
                    task.image_count_mode.value,
                    task.requested_image_count,
                )
                segmentation = segment_story(
                    original_text=task.original_text,
                    image_count_mode=task.image_count_mode,
                    requested_image_count=task.requested_image_count,
                    trace_context=task_trace_context(task, "segment_story"),
                )
                for panel in segmentation.panels:
                    db.add(
                        TaskPanel(
                            task_id=task.id,
                            panel_order=panel.panel_order,
                            panel_type=panel.panel_type,
                            original_text_segment=panel.text,
                            narration_text=None,
                            dialogue_text=None,
                            image_text_json=image_text_to_json(
                                {
                                    "title": None,
                                    "narration": panel.text,
                                    "dialogue": None,
                                    "inner_os": None,
                                    "emphasis": None,
                                }
                            ),
                        )
                    )
                task.progress_current = 1
                set_step(db, task, GenerationStepName.segment_story, StepStatus.succeeded)
                logger.info(
                    "story_drawing_debug segmentation_done task_id=%s panel_count=%s elapsed_ms=%s",
                    task.id,
                    len(segmentation.panels),
                    round((monotonic() - step_started) * 1000),
                )
            except LLMProviderError as exc:
                fail_step_and_task(db, task, GenerationStepName.segment_story, exc)
                return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        style = db.scalar(select(Style).where(Style.id == task.style_id))
        if style is None:
            fail_step_and_task(
                db,
                task,
                GenerationStepName.generate_character_references
                if task.use_character_references
                else GenerationStepName.generate_images,
                ImageProviderConfigError("风格不存在"),
            )
            return

        story_segments = panel_story_segments(task)
        logger.info(
            "story_drawing_debug prompt_style_ready task_id=%s provider_style_reference_count=%s story_segment_count=%s",
            task.id,
            0,
            len(story_segments),
        )

        if task.use_character_references:
            characters = load_task_characters(db, task.id)
            if characters:
                task.progress_current = max(task.progress_current, 2)
                set_step(db, task, GenerationStepName.extract_characters, StepStatus.succeeded)
                logger.info("story_drawing_debug character_extraction_skipped task_id=%s character_count=%s", task.id, len(characters))
            else:
                try:
                    set_step(db, task, GenerationStepName.extract_characters, StepStatus.running)
                    step_started = monotonic()
                    logger.info(
                        "story_drawing_debug character_extraction_start task_id=%s story_chars=%s panel_count=%s",
                        task.id,
                        len(story_text_for_generation(task)),
                        len(story_segments),
                    )
                    character_result = extract_task_characters(
                        original_text=story_text_for_generation(task),
                        style_prompt=task.style_prompt_snapshot,
                        panels=story_segments,
                        trace_context=task_trace_context(task, "extract_characters"),
                    )
                    if not character_result.characters:
                        raise LLMResponseError("未识别到可用于参考图的主要人物")
                    persist_character_plans(db, task, character_result.characters)
                    if task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
                        task = load_task(db, task_id)
                        if task is None:
                            return
                        save_character_plan_panel_links(
                            db=db,
                            task=task,
                            character_plans=character_result.characters,
                        )
                    task.progress_current = 2
                    set_step(db, task, GenerationStepName.extract_characters, StepStatus.succeeded)
                    logger.info(
                        "story_drawing_debug character_extraction_done task_id=%s character_count=%s appearance_count=%s elapsed_ms=%s",
                        task.id,
                        len(character_result.characters),
                        sum(len(character.appearances) for character in character_result.characters),
                        round((monotonic() - step_started) * 1000),
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
                step_started = monotonic()
                logger.info(
                    "story_drawing_debug character_reference_start task_id=%s provider_style_reference_count=%s",
                    task.id,
                    0,
                )
                ensure_character_reference_images(
                    db=db,
                    task=task,
                )
                task.progress_current = 3
                set_step(db, task, GenerationStepName.generate_character_references, StepStatus.succeeded)
                logger.info(
                    "story_drawing_debug character_reference_done task_id=%s elapsed_ms=%s",
                    task.id,
                    round((monotonic() - step_started) * 1000),
                )
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
        if task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
            if not prompts_ready:
                fail_step_and_task(db, task, GenerationStepName.adapt_story, LLMResponseError("分镜规划缺少可用于生图的画面提示词"))
                return
            task.progress_current = max(task.progress_current, prompts_progress)
            db.commit()
            logger.info(
                "story_drawing_debug panel_prompts_not_applicable task_id=%s story_input_mode=%s existing_panel_count=%s",
                task.id,
                task.story_input_mode.value,
                len(task.panels),
            )
        elif prompts_ready:
            task.progress_current = max(task.progress_current, prompts_progress)
            set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.succeeded)
            logger.info("story_drawing_debug panel_prompts_skipped task_id=%s existing_panel_count=%s", task.id, len(task.panels))
        else:
            try:
                set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.running)
                step_started = monotonic()
                logger.info(
                    "story_drawing_debug panel_prompts_start task_id=%s panel_count=%s use_character_references=%s story_chars=%s",
                    task.id,
                    len(story_segments),
                    task.use_character_references,
                    len(story_text_for_generation(task)),
                )
                if task.use_character_references:
                    character_plans = characters_to_plans(load_task_characters(db, task.id))
                    prompt_result = generate_panel_prompts_with_characters(
                        original_text=story_text_for_generation(task),
                        style_prompt=task.style_prompt_snapshot,
                        panels=story_segments,
                        characters=character_plans,
                        trace_context=task_trace_context(task, "generate_panel_prompts"),
                    )
                    clear_panel_character_links(db, task)
                else:
                    prompt_result = generate_panel_prompts(
                        original_text=story_text_for_generation(task),
                        style_prompt=task.style_prompt_snapshot,
                        panels=story_segments,
                        trace_context=task_trace_context(task, "generate_panel_prompts"),
                    )
                for panel in task.panels:
                    prompt_item = next(item for item in prompt_result.panels if item.panel_order == panel.panel_order)
                    panel.generated_prompt = prompt_item.visual_prompt
                    if task.story_input_mode == StoryInputMode.original:
                        panel.narration_text = None
                        panel.dialogue_text = None
                        panel.image_text_json = image_text_to_json(
                            {
                                "title": None,
                                "narration": panel.original_text_segment,
                                "dialogue": None,
                                "inner_os": None,
                                "emphasis": None,
                            }
                        )
                        panel.text_layout = None
                    else:
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
                    log_prompt_trace(
                        logger,
                        "panel_prompt_adopted",
                        context=task_trace_context(
                            task,
                            "generate_panel_prompts",
                            panel_id=panel.id,
                            panel_order=panel.panel_order,
                        ),
                        visual_prompt=panel.generated_prompt,
                        image_text_json=panel.image_text_json,
                        text_layout=panel.text_layout,
                        prompt_model_snapshot=panel.prompt_model_snapshot,
                        appearance_keys=getattr(prompt_item, "appearance_keys", []),
                        usage_notes=getattr(prompt_item, "usage_notes", {}),
                    )
                    logger.info(
                        "story_drawing_debug panel_prompt_adopted task_id=%s panel_id=%s panel_order=%s visual_prompt_chars=%s image_text_chars=%s",
                        task.id,
                        panel.id,
                        panel.panel_order,
                        len(panel.generated_prompt or ""),
                        len(panel.image_text_json or ""),
                    )
                task.progress_current = prompts_progress
                set_step(db, task, GenerationStepName.generate_panel_prompts, StepStatus.succeeded)
                logger.info(
                    "story_drawing_debug panel_prompts_done task_id=%s panel_count=%s elapsed_ms=%s",
                    task.id,
                    len(story_segments),
                    round((monotonic() - step_started) * 1000),
                )
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
        style = db.scalar(select(Style).where(Style.id == task.style_id))
        if style is None:
            fail_step_and_task(db, task, GenerationStepName.generate_images, ImageProviderConfigError("风格不存在"))
            return

        image_step_started = monotonic()
        logger.info(
            "story_drawing_debug image_generation_start task_id=%s panel_count=%s provider_style_reference_count=%s image_model=%s aspect_ratio=%s",
            task.id,
            len(task.panels),
            0,
            task.image_model_name_snapshot,
            task.style_aspect_ratio_snapshot,
        )
        success_count = 0
        skipped_count = 0
        prepared_requests: list[PreparedPanelImageRequest] = []
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
                    reference_pack = build_panel_reference_pack(panel=panel)
                    panel_reference_paths = reference_pack.paths
                    reference_notes = reference_pack.notes
                    character_reference_count = reference_pack.character_count
                else:
                    panel_reference_paths = []
                    reference_notes = []
                    character_reference_count = 0
                final_prompt = build_panel_final_prompt(
                    task=task,
                    panel=panel,
                    visual_prompt=panel.generated_prompt or "",
                    image_text=parse_image_text_json(panel.image_text_json)
                    or {
                        "title": None,
                        "narration": panel.narration_text,
                        "dialogue": panel.dialogue_text,
                        "inner_os": None,
                        "emphasis": None,
                    },
                    reference_notes=reference_notes,
                )
                log_prompt_trace(
                    logger,
                    "final_image_prompt_composed",
                    context=task_trace_context(
                        task,
                        "generate_images",
                        panel_id=panel.id,
                        panel_order=panel.panel_order,
                    ),
                    reference_notes=reference_notes,
                    reference_count=len(panel_reference_paths),
                    character_reference_count=character_reference_count,
                    visual_prompt=panel.generated_prompt,
                    image_text_json=panel.image_text_json,
                    final_prompt_chars=len(final_prompt),
                    final_prompt=final_prompt,
                )
                logger.info(
                    "story_drawing_debug final_prompt_ready task_id=%s panel_id=%s panel_order=%s reference_count=%s character_reference_count=%s visual_prompt_chars=%s final_prompt_chars=%s",
                    task.id,
                    panel.id,
                    panel.panel_order,
                    len(panel_reference_paths),
                    character_reference_count,
                    len(panel.generated_prompt or ""),
                    len(final_prompt),
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
            logger.info(
                "story_drawing_debug generated_image_record_created task_id=%s panel_id=%s panel_order=%s image_id=%s generation_number=%s source_type=%s",
                task.id,
                panel.id,
                panel.panel_order,
                image.id,
                image.generation_number,
                image.source_type.value,
            )
            prepared_requests.append(
                PreparedPanelImageRequest(
                    panel_id=panel.id,
                    panel_order=panel.panel_order,
                    image_id=image.id,
                    final_prompt=final_prompt,
                    reference_paths=panel_reference_paths,
                    reference_count=len(panel_reference_paths),
                    character_reference_count=character_reference_count,
                )
            )

        image_generation_concurrency = get_settings().image_generation_concurrency
        image_generation_concurrency = min(image_generation_concurrency, len(prepared_requests) or 1)
        logger.info(
            "story_drawing_debug provider_batch_ready task_id=%s request_count=%s concurrency=%s skipped_existing_success_count=%s",
            task.id,
            len(prepared_requests),
            image_generation_concurrency,
            skipped_count,
        )
        if prepared_requests:
            with ThreadPoolExecutor(max_workers=image_generation_concurrency) as executor:
                futures = [
                    executor.submit(
                        generate_panel_image_request,
                        task_id=task.id,
                        image_model_name=task.image_model_name_snapshot,
                        aspect_ratio=task.style_aspect_ratio_snapshot,
                        request=request,
                    )
                    for request in prepared_requests
                ]
                for future in as_completed(futures):
                    result = future.result()
                    image = db.scalar(select(GeneratedImage).where(GeneratedImage.id == result.request.image_id))
                    if image is None:
                        logger.warning(
                            "task panel image result skipped missing image task_id=%s panel_id=%s image_id=%s",
                            task.id,
                            result.request.panel_id,
                            result.request.image_id,
                        )
                        continue
                    if result.error is not None:
                        logger.warning(
                            "story_drawing_debug panel_image_failed task_id=%s panel_id=%s panel_order=%s image_id=%s error_type=%s error=%s",
                            task.id,
                            result.request.panel_id,
                            result.request.panel_order,
                            result.request.image_id,
                            result.error.__class__.__name__,
                            result.error,
                        )
                        image.status = GeneratedImageStatus.failed
                        image.error_code = result.error.__class__.__name__
                        image.error_message = str(result.error)
                        image.finished_at = datetime.utcnow()
                        db.commit()
                        continue
                    generated = result.generated
                    if generated is None:
                        logger.warning(
                            "story_drawing_debug panel_image_empty_result task_id=%s panel_id=%s panel_order=%s image_id=%s",
                            task.id,
                            result.request.panel_id,
                            result.request.panel_order,
                            result.request.image_id,
                        )
                        image.status = GeneratedImageStatus.failed
                        image.error_code = "ImageGenerationFailed"
                        image.error_message = "图片 Provider 未返回生成结果"
                        image.finished_at = datetime.utcnow()
                        db.commit()
                        continue
                    asset = FileAsset(
                        purpose=FileAssetPurpose.generated_image,
                        storage_backend=generated.storage_backend,
                        storage_key=generated.storage_key,
                        public_url=generated.public_url,
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
                        "story_drawing_debug panel_image_succeeded task_id=%s panel_id=%s panel_order=%s image_id=%s asset_id=%s asset_storage_key=%s bytes=%s provider_request_id=%s",
                        task.id,
                        result.request.panel_id,
                        result.request.panel_order,
                        result.request.image_id,
                        asset.id,
                        generated.storage_key,
                        generated.byte_size,
                        generated.provider_request_id,
                    )
                    db.commit()
                    if should_stop_for_cancel(db, task):
                        logger.info("task image generation cancellation observed after result task_id=%s", task.id)
                        return

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
        task.finished_at = datetime.utcnow()
        if success_count == panel_count:
            task.progress_current = task.progress_total
            task.status = TaskStatus.succeeded
        elif success_count > 0:
            task.progress_current = max(task.progress_total - 1, 0)
            task.status = TaskStatus.partial_succeeded
            task.error_code = "ImageGenerationPartialFailed"
            task.error_message = f"部分分镜图片生成失败：成功 {success_count} / 共 {panel_count} 张"
        else:
            task.progress_current = max(task.progress_total - 1, 0)
            task.status = TaskStatus.failed
            task.error_code = "ImageGenerationFailed"
            task.error_message = "所有分镜图片生成失败"
        db.commit()
        logger.info(
            "story_drawing_debug task_done task_id=%s status=%s success_count=%s skipped_existing_success_count=%s panel_count=%s elapsed_ms=%s image_step_elapsed_ms=%s",
            task.id,
            task.status.value,
            success_count,
            skipped_count,
            panel_count,
            round((monotonic() - task_started) * 1000),
            round((monotonic() - image_step_started) * 1000),
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
                trace_context=task_trace_context(
                    task,
                    "panel_edit_rewrite_prompt",
                    panel_id=panel.id,
                    panel_order=panel.panel_order,
                    generated_image_id=image.id,
                    generation_number=image.generation_number,
                ),
            )
            image.image_prompt = revision.visual_prompt
            if task.story_input_mode == StoryInputMode.original:
                image.image_text_json = image_text_to_json(
                    {
                        "title": None,
                        "narration": panel.original_text_segment,
                        "dialogue": None,
                        "inner_os": None,
                        "emphasis": None,
                    }
                )
                image.text_layout = None
            else:
                image.image_text_json = image_text_to_json(revision.image_text)
                image.text_layout = revision.text_layout
            image.prompt_change_summary = revision.change_summary
            image.llm_model_snapshot = get_settings().siliconflow_model
            image.final_prompt = build_panel_final_prompt(
                task=task,
                panel=panel,
                visual_prompt=revision.visual_prompt,
                image_text=parse_image_text_json(image.image_text_json),
            )
            log_prompt_trace(
                logger,
                "panel_edit_prompt_adopted",
                context=task_trace_context(
                    task,
                    "panel_edit_rewrite_prompt",
                    panel_id=panel.id,
                    panel_order=panel.panel_order,
                    generated_image_id=image.id,
                    generation_number=image.generation_number,
                ),
                user_instruction=image.user_instruction,
                previous_prompt=image.previous_prompt,
                revised_visual_prompt=image.image_prompt,
                image_text_json=image.image_text_json,
                text_layout=image.text_layout,
                change_summary=image.prompt_change_summary,
                final_prompt=image.final_prompt,
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

        style = db.scalar(select(Style).where(Style.id == task.style_id))
        if style is None:
            exc = ImageProviderConfigError("风格不存在")
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            db.commit()
            return

        if task.use_character_references:
            try:
                reference_pack = build_panel_reference_pack(panel=panel)
            except ImageProviderConfigError as exc:
                image.status = GeneratedImageStatus.failed
                image.error_code = exc.__class__.__name__
                image.error_message = str(exc)
                image.finished_at = datetime.utcnow()
                db.commit()
                return
            reference_paths = reference_pack.paths
            reference_notes = reference_pack.notes
            image.final_prompt = build_panel_final_prompt(
                task=task,
                panel=panel,
                visual_prompt=image.image_prompt or "",
                image_text=parse_image_text_json(image.image_text_json)
                or {
                    "title": None,
                    "narration": panel.narration_text,
                    "dialogue": panel.dialogue_text,
                    "inner_os": None,
                    "emphasis": None,
                },
                reference_notes=reference_notes,
            )
            log_prompt_trace(
                logger,
                "panel_edit_final_image_prompt_composed",
                context=task_trace_context(
                    task,
                    "panel_edit_generate_image",
                    panel_id=panel.id,
                    panel_order=panel.panel_order,
                    generated_image_id=image.id,
                    generation_number=image.generation_number,
                ),
                reference_notes=reference_notes,
                reference_count=len(reference_paths),
                visual_prompt=image.image_prompt,
                image_text_json=image.image_text_json,
                final_prompt_chars=len(image.final_prompt or ""),
                final_prompt=image.final_prompt,
            )
            db.commit()
        else:
            reference_paths = []
            reference_notes = []
            image.final_prompt = build_panel_final_prompt(
                task=task,
                panel=panel,
                visual_prompt=image.image_prompt or "",
                image_text=parse_image_text_json(image.image_text_json)
                or {
                    "title": None,
                    "narration": panel.narration_text,
                    "dialogue": panel.dialogue_text,
                    "inner_os": None,
                    "emphasis": None,
                },
                reference_notes=reference_notes,
            )
            log_prompt_trace(
                logger,
                "panel_edit_final_image_prompt_composed",
                context=task_trace_context(
                    task,
                    "panel_edit_generate_image",
                    panel_id=panel.id,
                    panel_order=panel.panel_order,
                    generated_image_id=image.id,
                    generation_number=image.generation_number,
                ),
                reference_notes=reference_notes,
                reference_count=len(reference_paths),
                visual_prompt=image.image_prompt,
                image_text_json=image.image_text_json,
                final_prompt_chars=len(image.final_prompt or ""),
                final_prompt=image.final_prompt,
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
                storage_backend=generated.storage_backend,
                storage_key=generated.storage_key,
                public_url=generated.public_url,
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
