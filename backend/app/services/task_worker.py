import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from typing import Any
from uuid import uuid4

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
    TaskStyleReferenceImage,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskPanelCharacterAppearance,
)
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageJobKind,
    GeneratedImageStatus,
    GeneratedImageSourceType,
    GeneratedImageWorkflowStep,
    GenerationStepName,
    PanelType,
    PromptStatus,
    StepStatus,
    StoryInputMode,
    TaskStatus,
    WorkflowStatus,
)
from app.services.character_references import (
    build_character_reference_prompt,
    build_character_style_reference_pack,
    build_panel_reference_pack,
    characters_to_plans,
    clear_panel_character_links,
    ensure_fixed_character_panel_links_by_name,
    ensure_character_reference_image_jobs,
    is_fixed_task_character,
    load_task_characters,
    persist_character_plans,
    persist_missing_generated_character_plans,
    save_character_plan_panel_links,
    save_panel_character_links,
)
from app.services.credits import (
    CreditError,
    InsufficientCreditsError,
    charge_reserved_image_credit,
    release_reserved_image_credit,
    reserve_image_credit,
)
from app.services.image_generation import (
    GeneratedImageFile,
    ImageReference,
    ImageProviderConfigError,
    ImageProviderResponseError,
    generate_xg_image,
    image_gateway_reference_limit,
)
from app.services.llm import (
    LLMProviderError,
    LLMResponseError,
    StorySegment,
    compose_final_image_prompts,
    extract_task_characters,
    generate_panel_prompts,
    generate_panel_prompts_with_characters,
    ImageTextPlan,
    parse_extracted_storyboard,
    plan_storyboard_from_brief,
    revise_panel_prompt,
    rewrite_policy_blocked_image_prompt,
    segment_story,
)
from app.services.prompt_logging import log_prompt_trace
from app.services.style_references import build_task_style_reference_pack, is_prompt_reference_mode

_queue: asyncio.Queue[str] | None = None
_queue_loop: asyncio.AbstractEventLoop | None = None
_worker_tasks: list[asyncio.Task[None]] = []
_image_worker_tasks: list[asyncio.Task[None]] = []
_running_task_ids: set[str] = set()
_running_task_ids_lock: asyncio.Lock | None = None
_image_job_claim_lock: asyncio.Lock | None = None
_image_worker_instance_id = uuid4().hex
logger = logging.getLogger(__name__)
POLICY_BLOCKED_ERROR_MARKERS = (
    "Unable to show the generated image",
    "Generative AI Prohibited Use policy",
    "filtered out",
    "violated Google's",
)


@dataclass(frozen=True)
class PreparedPanelImageRequest:
    panel_id: str
    panel_order: int
    image_id: str
    final_prompt: str
    references: list[ImageReference]
    reference_count: int
    character_reference_count: int
    style_reference_count: int


@dataclass(frozen=True)
class GenerationReferencePack:
    references: list[ImageReference]
    notes: list[str]
    character_reference_count: int
    style_reference_count: int


@dataclass(frozen=True)
class PanelImageGenerationResult:
    request: PreparedPanelImageRequest
    generated: GeneratedImageFile | None = None
    error: Exception | None = None
    final_prompt: str | None = None
    prompt_change_summary: str | None = None


def is_policy_blocked_image_error(exc: Exception) -> bool:
    if not isinstance(exc, ImageProviderResponseError):
        return False
    message = str(exc)
    return all(marker in message for marker in POLICY_BLOCKED_ERROR_MARKERS[:2]) or (
        "HTTP 400" in message and any(marker in message for marker in POLICY_BLOCKED_ERROR_MARKERS)
    )


def generate_image_with_policy_prompt_rewrite(
    *,
    prompt: str,
    references: list[ImageReference],
    image_model_name: str,
    aspect_ratio: str,
    task_id: str,
    panel_id: str,
    image_id: str,
    panel_order: int | None = None,
) -> tuple[GeneratedImageFile, str, str | None]:
    try:
        return (
            generate_xg_image(
                prompt=prompt,
                references=references,
                image_model_name=image_model_name,
                aspect_ratio=aspect_ratio,
            ),
            prompt,
            None,
        )
    except ImageProviderResponseError as exc:
        if not is_policy_blocked_image_error(exc):
            raise
        logger.warning(
            "story_drawing_debug policy_blocked_image_prompt_rewrite_start task_id=%s panel_id=%s panel_order=%s image_id=%s image_model=%s reference_count=%s error=%s",
            task_id,
            panel_id,
            panel_order,
            image_id,
            image_model_name,
            len(references),
            exc,
        )
        revision = rewrite_policy_blocked_image_prompt(
            final_prompt=prompt,
            provider_error=str(exc),
            trace_context={
                "task_id": task_id,
                "step": "policy_blocked_image_prompt_rewrite",
                "panel_id": panel_id,
                "panel_order": panel_order,
                "generated_image_id": image_id,
                "image_model_name": image_model_name,
                "reference_count": len(references),
            },
        )
        rewritten_final_prompt = final_prompt_with_aspect_ratio_prefix(aspect_ratio, revision.final_prompt)
        logger.info(
            "story_drawing_debug policy_blocked_image_prompt_rewrite_done task_id=%s panel_id=%s panel_order=%s image_id=%s image_model=%s original_prompt_chars=%s rewritten_prompt_chars=%s change_summary=%s",
            task_id,
            panel_id,
            panel_order,
            image_id,
            image_model_name,
            len(prompt),
            len(rewritten_final_prompt),
            revision.change_summary,
        )
        try:
            return (
                generate_xg_image(
                    prompt=rewritten_final_prompt,
                    references=references,
                    image_model_name=image_model_name,
                    aspect_ratio=aspect_ratio,
                ),
                rewritten_final_prompt,
                revision.change_summary,
            )
        except (ImageProviderConfigError, ImageProviderResponseError) as rewritten_exc:
            logger.warning(
                "story_drawing_debug policy_blocked_image_prompt_rewrite_failed task_id=%s panel_id=%s panel_order=%s image_id=%s image_model=%s error_type=%s error=%s",
                task_id,
                panel_id,
                panel_order,
                image_id,
                image_model_name,
                rewritten_exc.__class__.__name__,
                rewritten_exc,
            )
            raise rewritten_exc from exc


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
            "story_drawing_debug provider_request_start task_id=%s panel_id=%s panel_order=%s image_id=%s image_model=%s aspect_ratio=%s prompt_chars=%s reference_count=%s character_reference_count=%s style_reference_count=%s",
            task_id,
            request.panel_id,
            request.panel_order,
            request.image_id,
            image_model_name,
            aspect_ratio,
            len(request.final_prompt),
            request.reference_count,
            request.character_reference_count,
            request.style_reference_count,
        )
        generated, actual_final_prompt, prompt_change_summary = generate_image_with_policy_prompt_rewrite(
            prompt=request.final_prompt,
            references=request.references,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
            task_id=task_id,
            panel_id=request.panel_id,
            panel_order=request.panel_order,
            image_id=request.image_id,
        )
        logger.info(
            "story_drawing_debug provider_request_done task_id=%s panel_id=%s panel_order=%s image_id=%s image_model=%s prompt_rewritten=%s provider_request_id=%s storage_backend=%s storage_key=%s byte_size=%s elapsed_ms=%s",
            task_id,
            request.panel_id,
            request.panel_order,
            request.image_id,
            image_model_name,
            actual_final_prompt != request.final_prompt,
            generated.provider_request_id,
            generated.storage_backend.value,
            generated.storage_key,
            generated.byte_size,
            round((monotonic() - started) * 1000),
        )
        return PanelImageGenerationResult(
            request=request,
            generated=generated,
            final_prompt=actual_final_prompt,
            prompt_change_summary=prompt_change_summary if actual_final_prompt != request.final_prompt else None,
        )
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
    global _queue, _queue_loop, _worker_tasks, _image_worker_tasks, _running_task_ids_lock, _image_job_claim_lock
    settings = get_settings()
    _queue_loop = asyncio.get_running_loop()
    _queue = asyncio.Queue()
    _running_task_ids.clear()
    _running_task_ids_lock = asyncio.Lock()
    _image_job_claim_lock = asyncio.Lock()
    _worker_tasks = [
        asyncio.create_task(worker_loop(worker_index=worker_index))
        for worker_index in range(settings.task_worker_concurrency)
    ]
    _image_worker_tasks = [
        asyncio.create_task(image_job_worker_loop(worker_index=worker_index))
        for worker_index in range(settings.image_job_concurrency)
    ]
    logger.info(
        "task queue initialized worker_count=%s image_worker_count=%s image_job_user_concurrency=%s",
        len(_worker_tasks),
        len(_image_worker_tasks),
        settings.image_job_user_concurrency,
    )


async def shutdown_task_queue() -> None:
    global _worker_tasks, _image_worker_tasks, _running_task_ids_lock, _image_job_claim_lock, _queue_loop
    if not _worker_tasks and not _image_worker_tasks:
        return
    for worker_task in [*_worker_tasks, *_image_worker_tasks]:
        worker_task.cancel()
    await asyncio.gather(*_worker_tasks, *_image_worker_tasks, return_exceptions=True)
    _worker_tasks = []
    _image_worker_tasks = []
    _running_task_ids.clear()
    _running_task_ids_lock = None
    _image_job_claim_lock = None
    _queue_loop = None
    logger.info("task queue shutdown complete")


async def enqueue_task(task_id: str) -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    await _queue.put(task_id)
    logger.info("task enqueued task_id=%s queue_size=%s", task_id, _queue.qsize())


def enqueue_task_from_thread(task_id: str) -> None:
    if _queue_loop is None:
        raise RuntimeError("任务队列事件循环尚未初始化")
    future = asyncio.run_coroutine_threadsafe(enqueue_task(task_id), _queue_loop)
    future.result(timeout=5)


async def enqueue_panel_edit(generated_image_id: str) -> None:
    logger.info("panel edit queued for image job worker generated_image_id=%s", generated_image_id)


def image_job_owner_id(image: GeneratedImage) -> str:
    return image.owner_user_id or image.task.owner_user_id


def image_job_queue_group(image: GeneratedImage) -> str:
    return image.queue_group or image_job_owner_id(image)


def image_claim_is_current(image: GeneratedImage, *, attempts: int, locked_by: str | None) -> bool:
    return (
        image.status == GeneratedImageStatus.running
        and image.attempts == attempts
        and image.locked_by == locked_by
        and image.asset_id is None
    )


def image_job_has_terminal_credit(db: Session, image_id: str) -> bool:
    from app.models.entities import CreditTransaction
    from app.models.enums import CreditTransactionType

    transactions = db.scalars(
        select(CreditTransaction).where(CreditTransaction.generated_image_id == image_id)
    ).all()
    has_reserve = any(
        transaction.transaction_type == CreditTransactionType.image_generation_reserve
        for transaction in transactions
    )
    has_terminal = any(
        transaction.transaction_type
        in {CreditTransactionType.image_generation_charge, CreditTransactionType.image_generation_release}
        for transaction in transactions
    )
    return (not has_reserve) or has_terminal


def release_interrupted_image_job_credit(db: Session, image: GeneratedImage) -> None:
    if image_job_has_terminal_credit(db, image.id):
        return
    try:
        release_reserved_image_credit(
            db,
            user_id=image_job_owner_id(image),
            task_id=image.task_id,
            panel_id=image.panel_id,
            generated_image_id=image.id,
            character_appearance_id=image.character_appearance_id,
            note="图片任务中断后释放旧占用",
        )
    except CreditError:
        logger.info("image job interrupted credit release skipped image_id=%s", image.id)


def recover_interrupted_image_jobs() -> int:
    now = datetime.utcnow()
    recovered_count = 0
    with SessionLocal() as db:
        images = db.scalars(
            select(GeneratedImage)
            .where(GeneratedImage.status == GeneratedImageStatus.running)
            .options(selectinload(GeneratedImage.task))
            .order_by(GeneratedImage.updated_at.asc())
        ).all()
        for image in images:
            if image.asset_id is not None:
                continue
            release_interrupted_image_job_credit(db, image)
            image.status = GeneratedImageStatus.queued
            image.queued_at = image.queued_at or now
            image.lease_until = None
            image.locked_by = None
            image.error_code = None
            image.error_message = None
            recovered_count += 1
        db.commit()
    if recovered_count:
        logger.warning("recovered interrupted image jobs count=%s", recovered_count)
    return recovered_count


def claim_next_image_job() -> str | None:
    settings = get_settings()
    now = datetime.utcnow()
    lease_until = now + timedelta(seconds=settings.image_job_lease_seconds)
    with SessionLocal() as db:
        candidates = db.scalars(
            select(GeneratedImage)
            .where(GeneratedImage.status == GeneratedImageStatus.queued)
            .options(selectinload(GeneratedImage.task))
            .order_by(GeneratedImage.priority.desc(), GeneratedImage.queued_at.asc(), GeneratedImage.created_at.asc())
            .limit(100)
        ).all()
        for image in candidates:
            owner_id = image_job_owner_id(image)
            running_for_user = db.scalar(
                select(func.count(GeneratedImage.id)).where(
                    GeneratedImage.status == GeneratedImageStatus.running,
                    GeneratedImage.owner_user_id == owner_id,
                    GeneratedImage.lease_until.is_not(None),
                    GeneratedImage.lease_until > now,
                )
            )
            if (running_for_user or 0) >= settings.image_job_user_concurrency:
                continue
            image.owner_user_id = owner_id
            image.queue_group = image.queue_group or owner_id
            image.status = GeneratedImageStatus.running
            image.started_at = image.started_at or now
            image.lease_until = lease_until
            image.locked_by = _image_worker_instance_id
            image.attempts += 1
            image.error_code = None
            image.error_message = None
            db.commit()
            logger.info(
                "image job claimed image_id=%s task_id=%s panel_id=%s character_appearance_id=%s job_kind=%s source_type=%s owner_user_id=%s attempts=%s lease_until=%s",
                image.id,
                image.task_id,
                image.panel_id,
                image.character_appearance_id,
                image.job_kind.value,
                image.source_type.value,
                owner_id,
                image.attempts,
                lease_until.isoformat(),
            )
            return image.id
    return None


async def image_job_worker_loop(*, worker_index: int) -> None:
    if _image_job_claim_lock is None:
        raise RuntimeError("图片任务领取锁尚未初始化")
    logger.info("image job worker loop started worker_index=%s", worker_index)
    while True:
        image_id: str | None = None
        try:
            async with _image_job_claim_lock:
                image_id = claim_next_image_job()
            if image_id is None:
                await asyncio.sleep(1)
                continue
            await asyncio.to_thread(process_generated_image_job, image_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("image job worker unexpected error image_id=%s worker_index=%s", image_id, worker_index)
            if image_id:
                mark_image_job_failed_by_unhandled_error(image_id, exc)


def process_generated_image_job(generated_image_id: str) -> None:
    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            logger.warning("image job skipped missing image_id=%s", generated_image_id)
            return
        source_type = image.source_type
        job_kind = image.job_kind

    if job_kind == GeneratedImageJobKind.character_reference:
        process_character_reference_image_job(generated_image_id)
    elif source_type == GeneratedImageSourceType.user_edit:
        process_panel_edit(generated_image_id)
    else:
        process_initial_panel_image_job(generated_image_id)

    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is not None and image.job_kind == GeneratedImageJobKind.character_reference:
            update_task_character_reference_state(db, image.task_id)
        elif image is not None and image.source_type != GeneratedImageSourceType.user_edit:
            update_task_image_generation_state(db, image.task_id)


def mark_image_job_failed_by_unhandled_error(generated_image_id: str, exc: Exception) -> None:
    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            return
        release_interrupted_image_job_credit(db, image)
        image.status = GeneratedImageStatus.failed
        image.error_code = exc.__class__.__name__
        image.error_message = str(exc)
        image.finished_at = datetime.utcnow()
        image.lease_until = None
        image.locked_by = None
        db.commit()
        if image.job_kind == GeneratedImageJobKind.character_reference:
            update_task_character_reference_state(db, image.task_id)
        elif image.source_type != GeneratedImageSourceType.user_edit:
            update_task_image_generation_state(db, image.task_id)


def process_character_reference_image_job(generated_image_id: str) -> None:
    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            logger.warning("character reference image job skipped missing image_id=%s", generated_image_id)
            return
        if image.character_appearance is None:
            image.status = GeneratedImageStatus.failed
            image.error_code = "CharacterAppearanceMissing"
            image.error_message = "人物参考图任务缺少人物外观记录"
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            db.commit()
            return
        task = image.task
        appearance = image.character_appearance
        character = appearance.character
        claim_attempts = image.attempts
        claim_locked_by = image.locked_by
        try:
            reference_pack = build_character_style_reference_pack(task)
        except ImageProviderConfigError as exc:
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            appearance.status = WorkflowStatus.failed
            appearance.error_code = exc.__class__.__name__
            appearance.error_message = str(exc)
            db.commit()
            return
        prompt = image.final_prompt or appearance.reference_prompt or ""
        if reference_pack.notes and not all(note in prompt for note in reference_pack.notes):
            prompt = build_character_reference_prompt(
                style_prompt=task.style_prompt_snapshot,
                aspect_ratio=task.style_aspect_ratio_snapshot,
                character_name=character.name,
                age_stage=appearance.age_stage,
                visual_prompt=appearance.visual_prompt,
                style_reference_notes=reference_pack.notes,
            )
            image.final_prompt = prompt
            appearance.reference_prompt = prompt
        appearance.status = WorkflowStatus.running
        appearance.error_code = None
        appearance.error_message = None
        try:
            reserve_image_credit(
                db,
                user_id=task.owner_user_id,
                task_id=task.id,
                generated_image_id=image.id,
                character_appearance_id=appearance.id,
                note=f"人物参考图 {character.name} 占用",
            )
            db.commit()
        except InsufficientCreditsError as exc:
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            appearance.status = WorkflowStatus.failed
            appearance.error_code = exc.__class__.__name__
            appearance.error_message = str(exc)
            db.commit()
            return

        logger.info(
            "character reference image request task_id=%s character_key=%s appearance_key=%s image_id=%s prompt_chars=%s "
            "reference_count=%s style_reference_count=%s reference_notes=%s",
            task.id,
            character.character_key,
            appearance.appearance_key,
            image.id,
            len(prompt),
            len(reference_pack.references),
            reference_pack.style_count,
            reference_pack.notes,
        )
        image_model_name = task.image_model_name_snapshot
        aspect_ratio = task.style_aspect_ratio_snapshot
        references = list(reference_pack.references)
        task_id = task.id
        appearance_id = appearance.id

    try:
        generated = generate_xg_image(
            prompt=prompt,
            references=references,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
        error: Exception | None = None
    except (ImageProviderConfigError, ImageProviderResponseError) as exc:
        generated = None
        error = exc

    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            return
        task = image.task
        appearance = image.character_appearance
        if appearance is None:
            return
        if not image_claim_is_current(image, attempts=claim_attempts, locked_by=claim_locked_by):
            logger.warning(
                "stale character reference image result ignored image_id=%s task_id=%s appearance_id=%s claim_attempts=%s current_attempts=%s claim_locked_by=%s current_locked_by=%s status=%s",
                image.id,
                task_id,
                appearance_id,
                claim_attempts,
                image.attempts,
                claim_locked_by,
                image.locked_by,
                image.status.value,
            )
            return
        if error is not None:
            image.status = GeneratedImageStatus.failed
            image.error_code = error.__class__.__name__
            image.error_message = str(error)
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            appearance.status = WorkflowStatus.failed
            appearance.error_code = error.__class__.__name__
            appearance.error_message = str(error)
            try:
                release_reserved_image_credit(
                    db,
                    user_id=task.owner_user_id,
                    task_id=task.id,
                    generated_image_id=image.id,
                    character_appearance_id=appearance.id,
                    note="人物参考图失败释放积分占用",
                )
            except CreditError:
                logger.info("character reference release skipped no reserved credit image_id=%s", image.id)
            db.commit()
            return
        if generated is None:
            image.status = GeneratedImageStatus.failed
            image.error_code = "ImageGenerationFailed"
            image.error_message = "图片 Provider 未返回人物参考图"
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            appearance.status = WorkflowStatus.failed
            appearance.error_code = image.error_code
            appearance.error_message = image.error_message
            try:
                release_reserved_image_credit(
                    db,
                    user_id=task.owner_user_id,
                    task_id=task.id,
                    generated_image_id=image.id,
                    character_appearance_id=appearance.id,
                    note="人物参考图未返回结果释放积分占用",
                )
            except CreditError:
                logger.info("character reference empty-result release skipped no reserved credit image_id=%s", image.id)
            db.commit()
            return

        asset = FileAsset(
            purpose=FileAssetPurpose.character_reference,
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
        image.lease_until = None
        image.locked_by = None
        appearance.reference_image_id = asset.id
        appearance.provider_request_id = generated.provider_request_id
        appearance.status = WorkflowStatus.succeeded
        appearance.error_code = None
        appearance.error_message = None
        charge_reserved_image_credit(
            db,
            user_id=task.owner_user_id,
            task_id=task.id,
            generated_image_id=image.id,
            character_appearance_id=appearance.id,
            note="人物参考图成功产出扣费",
        )
        logger.info(
            "character reference image succeeded task_id=%s appearance_id=%s image_id=%s asset_storage_key=%s bytes=%s",
            task.id,
            appearance.id,
            image.id,
            generated.storage_key,
            generated.byte_size,
        )
        db.commit()


def process_initial_panel_image_job(generated_image_id: str) -> None:
    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            logger.warning("initial image job skipped missing image_id=%s", generated_image_id)
            return
        task = image.task
        panel = image.panel
        if panel is None:
            image.status = GeneratedImageStatus.failed
            image.error_code = "PanelMissing"
            image.error_message = "分镜图片任务缺少 panel"
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            db.commit()
            update_task_image_generation_state(db, task.id)
            return
        task_id = task.id
        owner_user_id = task.owner_user_id
        image_model_name = task.image_model_name_snapshot
        aspect_ratio = task.style_aspect_ratio_snapshot
        claim_attempts = image.attempts
        claim_locked_by = image.locked_by
        try:
            reference_pack = build_generation_reference_pack(task, panel)
        except ImageProviderConfigError as exc:
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            db.commit()
            update_task_image_generation_state(db, task.id)
            return

        request = PreparedPanelImageRequest(
            panel_id=panel.id,
            panel_order=panel.panel_order,
            image_id=image.id,
            final_prompt=image.final_prompt or "",
            references=reference_pack.references,
            reference_count=len(reference_pack.references),
            character_reference_count=reference_pack.character_reference_count,
            style_reference_count=reference_pack.style_reference_count,
        )
        try:
            reserve_image_credit(
                db,
                user_id=owner_user_id,
                task_id=task_id,
                panel_id=panel.id,
                generated_image_id=image.id,
                note=f"任务分镜 {panel.panel_order} 生图占用",
            )
            db.commit()
        except InsufficientCreditsError as exc:
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            db.commit()
            update_task_image_generation_state(db, task.id)
            return

    result = generate_panel_image_request(
        task_id=task_id,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
        request=request,
    )

    with SessionLocal() as db:
        image = load_generated_image(db, generated_image_id)
        if image is None:
            return
        task = image.task
        if not image_claim_is_current(image, attempts=claim_attempts, locked_by=claim_locked_by):
            logger.warning(
                "stale panel image result ignored image_id=%s task_id=%s panel_id=%s claim_attempts=%s current_attempts=%s claim_locked_by=%s current_locked_by=%s status=%s",
                image.id,
                task_id,
                image.panel_id,
                claim_attempts,
                image.attempts,
                claim_locked_by,
                image.locked_by,
                image.status.value,
            )
            return
        if result.error is not None:
            image.status = GeneratedImageStatus.failed
            image.error_code = result.error.__class__.__name__
            image.error_message = str(result.error)
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            try:
                release_reserved_image_credit(
                    db,
                    user_id=task.owner_user_id,
                    task_id=task.id,
                    panel_id=image.panel_id,
                    generated_image_id=image.id,
                    note="任务分镜生图失败释放积分占用",
                )
            except CreditError:
                logger.info("initial image job release skipped no reserved credit image_id=%s", image.id)
            db.commit()
            update_task_image_generation_state(db, task.id)
            return
        generated = result.generated
        if generated is None:
            image.status = GeneratedImageStatus.failed
            image.error_code = "ImageGenerationFailed"
            image.error_message = "图片 Provider 未返回生成结果"
            image.finished_at = datetime.utcnow()
            image.lease_until = None
            image.locked_by = None
            try:
                release_reserved_image_credit(
                    db,
                    user_id=task.owner_user_id,
                    task_id=task.id,
                    panel_id=image.panel_id,
                    generated_image_id=image.id,
                    note="任务分镜生图未返回结果释放积分占用",
                )
            except CreditError:
                logger.info("initial image job empty-result release skipped no reserved credit image_id=%s", image.id)
            db.commit()
            update_task_image_generation_state(db, task.id)
            return
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
        if result.final_prompt and result.final_prompt != image.final_prompt:
            image.final_prompt = result.final_prompt
            image.prompt_change_summary = result.prompt_change_summary
        charge_reserved_image_credit(
            db,
            user_id=task.owner_user_id,
            task_id=task.id,
            panel_id=image.panel_id,
            generated_image_id=image.id,
            note="任务分镜图片成功产出扣费",
        )
        image.status = GeneratedImageStatus.succeeded
        image.finished_at = datetime.utcnow()
        image.lease_until = None
        image.locked_by = None
        mark_image_current(db, image)
        db.commit()
        update_task_image_generation_state(db, task.id)


def update_task_character_reference_state(db: Session, task_id: str) -> None:
    task = load_task(db, task_id)
    if task is None or not task.use_character_references:
        return
    appearances = [appearance for character in task.characters for appearance in character.appearances]
    if not appearances:
        return
    active_count = active_character_reference_job_count(db, task_id)
    if active_count > 0:
        task.status = TaskStatus.running
        task.current_step = GenerationStepName.generate_character_references
        set_step(db, task, GenerationStepName.generate_character_references, StepStatus.running)
        return
    failed = [
        appearance
        for appearance in appearances
        if appearance.status == WorkflowStatus.failed or (appearance.status != WorkflowStatus.succeeded and not appearance.reference_image_id)
    ]
    if failed:
        set_step(db, task, GenerationStepName.generate_character_references, StepStatus.failed)
        task.status = TaskStatus.failed
        task.error_code = "CharacterReferenceImageFailed"
        task.error_message = f"人物参考图生成失败：{len(failed)} 个角色形象未生成成功"
        task.finished_at = datetime.utcnow()
        db.commit()
        return
    task.progress_current = max(task.progress_current, 3)
    task.status = TaskStatus.queued
    task.error_code = None
    task.error_message = None
    task.finished_at = None
    set_step(db, task, GenerationStepName.generate_character_references, StepStatus.succeeded)
    db.commit()
    enqueue_task_from_thread(task.id)


def update_task_image_generation_state(db: Session, task_id: str) -> None:
    task = load_task(db, task_id)
    if task is None:
        return
    panel_count = len(task.panels)
    if panel_count == 0:
        return
    current_success_count = len(current_succeeded_images_by_panel(task))
    active_count = sum(
        1
        for image in task.generated_images
        if image.job_kind == GeneratedImageJobKind.panel_image
        and image.source_type != GeneratedImageSourceType.user_edit
        and image.status in {GeneratedImageStatus.queued, GeneratedImageStatus.running}
    )
    if active_count > 0:
        task.status = TaskStatus.running
        task.current_step = GenerationStepName.generate_images
        set_step(db, task, GenerationStepName.generate_images, StepStatus.running)
        db.commit()
        return
    set_step(
        db,
        task,
        GenerationStepName.generate_images,
        StepStatus.succeeded if current_success_count == panel_count else StepStatus.failed,
    )
    task.finished_at = datetime.utcnow()
    if current_success_count == panel_count:
        task.progress_current = task.progress_total
        task.status = TaskStatus.succeeded
        task.error_code = None
        task.error_message = None
    elif current_success_count > 0:
        task.progress_current = max(task.progress_total - 1, 0)
        task.status = TaskStatus.partial_succeeded
        task.error_code = "ImageGenerationPartialFailed"
        task.error_message = f"部分分镜图片生成失败：成功 {current_success_count} / 共 {panel_count} 张"
    else:
        task.progress_current = max(task.progress_total - 1, 0)
        task.status = TaskStatus.failed
        task.error_code = "ImageGenerationFailed"
        task.error_message = "所有分镜图片生成失败"
    db.commit()


def active_initial_image_job_count(db: Session, task_id: str) -> int:
    return db.scalar(
        select(func.count(GeneratedImage.id)).where(
            GeneratedImage.task_id == task_id,
            GeneratedImage.job_kind == GeneratedImageJobKind.panel_image,
            GeneratedImage.source_type != GeneratedImageSourceType.user_edit,
            GeneratedImage.status.in_([GeneratedImageStatus.queued, GeneratedImageStatus.running]),
        )
    ) or 0


def active_character_reference_job_count(db: Session, task_id: str) -> int:
    return db.scalar(
        select(func.count(GeneratedImage.id)).where(
            GeneratedImage.task_id == task_id,
            GeneratedImage.job_kind == GeneratedImageJobKind.character_reference,
            GeneratedImage.status.in_([GeneratedImageStatus.queued, GeneratedImageStatus.running]),
        )
    ) or 0


def task_has_incomplete_character_references(task: GenerationTask) -> bool:
    return any(
        appearance.status != WorkflowStatus.succeeded or appearance.reference_image_id is None
        for character in task.characters
        for appearance in character.appearances
    )


async def recover_queued_tasks() -> None:
    if _queue is None:
        raise RuntimeError("任务队列尚未初始化")
    recover_interrupted_image_jobs()
    with SessionLocal() as db:
        interrupted_tasks = db.scalars(
            select(GenerationTask)
            .where(GenerationTask.status.in_([TaskStatus.running, TaskStatus.cancel_requested]))
            .order_by(GenerationTask.created_at.asc())
        ).all()
        failed_count = 0
        resumed_image_planning_count = 0
        continued_image_job_count = 0
        for task in interrupted_tasks:
            if task.current_step == GenerationStepName.generate_images:
                if active_initial_image_job_count(db, task.id) > 0:
                    continued_image_job_count += 1
                    continue
                task.status = TaskStatus.queued
                task.error_code = None
                task.error_message = None
                task.finished_at = None
                resumed_image_planning_count += 1
                logger.warning("re-queued interrupted image-planning task without active image jobs task_id=%s", task.id)
                continue
            if task.current_step == GenerationStepName.generate_character_references:
                if active_character_reference_job_count(db, task.id) > 0:
                    continued_image_job_count += 1
                    continue
                if task_has_incomplete_character_references(task):
                    task.status = TaskStatus.queued
                    task.error_code = None
                    task.error_message = None
                    task.finished_at = None
                    resumed_image_planning_count += 1
                    logger.warning("re-queued interrupted character-reference task without active image jobs task_id=%s", task.id)
                    continue
            task.status = TaskStatus.failed
            task.error_code = "WorkerInterrupted"
            task.error_message = "服务重启导致任务中断，请重新创建任务"
            task.finished_at = datetime.utcnow()
            failed_count += 1
        db.commit()
        if failed_count or resumed_image_planning_count or continued_image_job_count:
            logger.warning(
                "recovered interrupted tasks failed_count=%s resumed_image_planning_count=%s continued_image_job_count=%s",
                failed_count,
                resumed_image_planning_count,
                continued_image_job_count,
            )

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
            selectinload(GenerationTask.style_reference_images).selectinload(TaskStyleReferenceImage.asset),
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
        lines.append(f"以标题字呈现：「{title.strip()}」")
    if narration:
        lines.append(f"以旁白框或字幕框呈现：「{narration.strip()}」")
    dialogue = values.get("dialogue")
    if dialogue:
        lines.append(f"以对白气泡呈现：「{dialogue.strip()}」")
    if inner_os:
        lines.append(f"以思想气泡或心理独白框呈现：「{inner_os.strip()}」")
    if emphasis:
        lines.append(f"以强调字呈现：「{emphasis.strip()}」")
    return "\n".join(lines)


def storyboard_layout_label(text_layout: str | None) -> str:
    cleaned = (text_layout or "").strip()
    if not cleaned:
        return "单页"
    if cleaned in {"单页", "单页构图", "单页漫画构图", "单页漫画"}:
        return "单页"
    return cleaned


def storyboard_text_value(value: str | None) -> str:
    cleaned = (value or "").strip()
    return cleaned if cleaned else "无"


def structured_storyboard_block(
    *,
    panel_order: int,
    visual_prompt: str,
    image_text: ImageTextPlan | dict[str, str | None] | None,
    text_layout: str | None,
) -> str:
    values = image_text_to_dict(image_text)
    lines = [
        "当前分镜：",
        f"【分格】{storyboard_layout_label(text_layout)}",
        f"画面：{visual_prompt.strip()}",
    ]
    title = storyboard_text_value(values.get("title"))
    if title != "无":
        lines.append(f"标题：{title}")
    lines.extend(
        [
            f"旁白：{storyboard_text_value(values.get('narration'))}",
            f"对话：{storyboard_text_value(values.get('dialogue'))}",
            f"内心OS：{storyboard_text_value(values.get('inner_os'))}",
        ]
    )
    emphasis = storyboard_text_value(values.get("emphasis"))
    if emphasis != "无":
        lines.append(f"强调：{emphasis}")
    return "\n".join(lines)


def layout_instruction(text_layout: str | None) -> str | None:
    cleaned = (text_layout or "").strip()
    if not cleaned:
        return None
    if cleaned in {"单页", "单页构图", "单页漫画构图", "单页漫画"}:
        return None
    return f"画面必须采用{cleaned}。"


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


def text_rules_block(
    visual_prompt: str,
    image_text: ImageTextPlan | dict[str, str | None] | None,
    text_layout: str | None = None,
) -> str:
    values = image_text_to_dict(image_text)
    rules = ["图片内文字字号偏大、清晰可读，保留足够留白，优先保证文字可读性。"]
    if any(values.get(key) for key in ("title", "narration", "dialogue", "inner_os", "emphasis")):
        rules.append("所有指定文字只出现一次，不能在不同分格重复绘制同一段文字。")
    if values.get("narration"):
        rules.append("旁白使用漫画旁白框或字幕框呈现，只选择一个位置放置完整旁白，并与对白气泡明确区分。")
        layout_hint = f"{visual_prompt}\n{text_layout or ''}"
        if re.search(r"(上下|上格|下格|上中下|中格|多格|分格|分屏|左右|左栏|右栏|多栏)", layout_hint):
            rules.append(
                "如果是分格或多栏页面，整页旁白只使用一个旁白框，不要在上格、下格或不同分栏里重复放置同一段旁白；"
                "只有文字列表明确拆成上格旁白、下格旁白时，才分别放到对应格子。"
            )
    if dialogue_block(image_text) or visual_prompt_has_dialogue(visual_prompt):
        rules.append("对白出现在对应人物附近的对白气泡中，气泡尾巴指向说话人物；气泡里呈现人物说出的句子。")
        if values.get("narration"):
            rules.append("如果旁白原文中包含同一句直接引语，而画面描述已经把它绑定到人物说话动作，最终只画一次这句台词：用对白气泡呈现，不要在旁白框里重复。")
    if values.get("inner_os"):
        rules.append("内心OS使用思想气泡、虚线气泡或半透明心理独白框呈现，明显区别于对白。")
    return "".join(rules)


def normalize_prompt_text_for_label_match(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().strip("「」『』“”\"'"))


def prompt_label_content_matches(content: str, expected: str | None) -> bool:
    if not expected:
        return False
    normalized_content = normalize_prompt_text_for_label_match(content)
    normalized_expected = normalize_prompt_text_for_label_match(expected)
    if not normalized_content or not normalized_expected:
        return False
    return normalized_content == normalized_expected or normalized_expected.startswith(normalized_content)


def render_image_text_instruction(label: str, content: str) -> str:
    if label == "标题":
        return f"以醒目标题字写入「{content}」"
    if label == "对话":
        return f"以对白气泡写入「{content}」"
    if label == "内心OS":
        return f"以心理独白框写入「{content}」"
    if label == "强调":
        return f"以强调字写入「{content}」"
    return f"在留白文字区写入「{content}」"


def sanitize_compiled_final_prompt(
    final_prompt: str,
    image_text: ImageTextPlan | dict[str, str | None] | None,
) -> str:
    values = image_text_to_dict(image_text)
    labels = [
        ("标题", "title"),
        ("旁白", "narration"),
        ("对话", "dialogue"),
        ("内心OS", "inner_os"),
        ("强调", "emphasis"),
    ]
    sanitized_lines: list[str] = []
    for raw_line in final_prompt.splitlines():
        stripped = raw_line.strip()
        if is_page_number_heading_or_instruction(stripped):
            continue
        leading_space = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        rewritten_line: str | None = None
        for label, key in labels:
            for separator in ("：", ":"):
                prefix = f"{label}{separator}"
                if not stripped.startswith(prefix):
                    continue
                content = stripped[len(prefix):].strip()
                if content in {"", "无", "null", "None"} and not values.get(key):
                    rewritten_line = ""
                    break
                if prompt_label_content_matches(content, values.get(key)) or content:
                    rewritten_line = leading_space + render_image_text_instruction(label, content)
                    break
            if rewritten_line is not None:
                break
        if rewritten_line is None:
            sanitized_lines.append(raw_line)
        elif rewritten_line:
            sanitized_lines.append(rewritten_line)
    return "\n".join(sanitized_lines).strip()


def is_page_number_heading_or_instruction(line: str) -> bool:
    if not line:
        return False
    page_pattern = r"(?:第\s*\d+\s*[页頁格]|Page\s*\d+)"
    if re.fullmatch(rf"{page_pattern}(?:[：:，,。.、\s]*|\s*[（(][^）)]*[）)])", line, flags=re.IGNORECASE):
        return True
    if re.search(page_pattern, line, flags=re.IGNORECASE) and re.search(
        r"(写入|显示|标注|角落|右下角|左下角|页码|编号|角标)", line
    ):
        return True
    return False


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


def normalized_task_reference_lines(reference_notes: list[str] | None) -> list[str]:
    lines: list[str] = []
    for note in reference_notes or []:
        first_line = note.strip().splitlines()[0].strip() if note and note.strip() else ""
        if not first_line:
            continue
        fixed_character_match = re.match(r"固定角色参考（参考图(\d+)）：(.+)", first_line)
        if fixed_character_match:
            index, name = fixed_character_match.groups()
            lines.append(f"角色外观参考图{index}（{name.strip()}）")
            continue
        style_match = re.match(r"风格参考（参考图(\d+)）", first_line)
        if style_match:
            lines.append(f"风格参考（图{style_match.group(1)}）")
            continue
        character_match = re.match(r"(.+?)参考（参考图(\d+)）", first_line)
        if character_match:
            name, index = character_match.groups()
            lines.append(f"角色外观参考图{index}（{name.strip()}）")
    return lines


def task_reference_block(reference_notes: list[str] | None, style_prompt: str | None = None) -> str | None:
    lines = normalized_task_reference_lines(reference_notes)
    if not lines:
        return None
    cleaned_style_prompt = (style_prompt or "").strip()
    block_lines = [
        "任务参考（最高优先级，必须优先执行）：",
        *lines,
    ]
    if cleaned_style_prompt:
        block_lines.extend(
            [
                "当前风格提示（仅对本任务选择的风格生效，必须和风格参考图共同约束画面）：",
                cleaned_style_prompt,
            ]
        )
    block_lines.extend(
        [
            "以上参考图已随请求传入；角色外观以角色参考图为准，画风、线条、色彩和背景质感以风格参考图为准。",
            "当剧情氛围词与当前风格提示或风格参考图冲突时，必须优先保持当前风格，不要转译成脱离参考图的独立背景色、纸张材质或装饰底纹。",
        ]
    )
    return "\n".join(block_lines)


def remove_image_mode_reference_summary_lines(final_prompt: str) -> str:
    kept_lines: list[str] = []
    for raw_line in final_prompt.splitlines():
        stripped = raw_line.strip()
        if re.match(r"^(整体风格|整体色调/风格|整体色调|风格)[：:]", stripped):
            continue
        kept_lines.append(raw_line)
    return "\n".join(kept_lines).strip()


def style_prompt_block(style_prompt: str | None) -> list[str]:
    cleaned = (style_prompt or "").strip()
    if not cleaned:
        return []
    return [
        "",
        "风格提示词（必须直接用于本张图的画风、人物比例、线条、色彩、构图、文字呈现和整体质感）：",
        cleaned,
    ]


def final_prompt_with_aspect_ratio_prefix(aspect_ratio: str, final_prompt: str) -> str:
    cleaned_prompt = final_prompt.strip()
    cleaned_ratio = (aspect_ratio or "").strip()
    if not cleaned_ratio:
        return cleaned_prompt

    prefix = (
        f"画面比例：{cleaned_ratio}。必须严格按 {cleaned_ratio} 宽高比构图和出图，"
        "不要生成横竖方向或比例不一致的画面。"
    )
    if cleaned_prompt.startswith(f"画面比例：{cleaned_ratio}"):
        return cleaned_prompt
    return "\n".join([prefix, "", cleaned_prompt]).strip()


def final_prompt_with_real_photo_style(aspect_ratio: str, final_prompt: str) -> str:
    cleaned_prompt = final_prompt.strip()
    real_photo_block = "\n".join(
        [
            "本张图片启用“最后一张真人图片”模式，必须按真实摄影照片生成。",
            "画面风格覆盖：真实人物、真实环境、真实光线、真实相机拍摄质感，优先呈现真人自拍、纪实照片或生活照效果。",
            "不要生成漫画、手绘、绘本、水彩、线稿、二次元、卡通人物、插画纸张质感或漫画分镜质感。",
            "如果画面描述中出现“照片式构图”“自拍”“合影”“照片”，必须理解为真实照片拍摄，而不是漫画里的照片构图。",
            "保留当前分镜中的人物身份、动作、场景、道具和所有图片内文字要求；如有文字，仍需放在画面安全区内并保持清晰可读。",
            "",
            "最终画面指令：",
            cleaned_prompt,
        ]
    ).strip()
    return final_prompt_with_aspect_ratio_prefix(aspect_ratio, real_photo_block)


def final_prompt_with_explicit_style(
    task: GenerationTask,
    final_prompt: str,
    reference_notes: list[str] | None = None,
    force_real_photo: bool = False,
) -> str:
    cleaned_prompt = final_prompt.strip()
    if force_real_photo:
        return final_prompt_with_real_photo_style(task.style_aspect_ratio_snapshot, cleaned_prompt)

    style_prompt = task.style_prompt_snapshot
    cleaned_style = (style_prompt or "").strip()
    if not is_prompt_reference_mode(task.style_reference_mode_snapshot):
        cleaned_prompt = remove_image_mode_reference_summary_lines(cleaned_prompt)
        reference_block = task_reference_block(reference_notes, style_prompt=cleaned_style)
        prompt_with_ratio = final_prompt_with_aspect_ratio_prefix(task.style_aspect_ratio_snapshot, cleaned_prompt)
        if reference_block:
            return "\n\n".join([reference_block, prompt_with_ratio]).strip()
        return prompt_with_ratio
    if not cleaned_style:
        return final_prompt_with_aspect_ratio_prefix(task.style_aspect_ratio_snapshot, cleaned_prompt)
    styled_prompt = "\n".join(
        [
            "风格提示词（必须直接用于本张图的画风、人物比例、线条、色彩、构图、文字呈现和整体质感）：",
            cleaned_style,
            "",
            (
                "风格执行优先级：角色身份与外观锁定 > 当前剧情动作/情绪 > 风格表现方式 > "
                "风格模板默认人物外观。风格模板只控制画风、人物比例、线条、色彩、构图、"
                "文字呈现和整体质感；不得覆盖最终画面指令中已经锁定的角色年龄阶段、发型、"
                "体态、服装轮廓和标志性配饰。"
            ),
            "",
            "最终画面指令：",
            cleaned_prompt,
        ]
    ).strip()
    return final_prompt_with_aspect_ratio_prefix(task.style_aspect_ratio_snapshot, styled_prompt)


def is_last_panel_real_photo_panel(task: GenerationTask, panel: TaskPanel) -> bool:
    if not task.last_panel_real_photo:
        return False
    panel_orders = [item.panel_order for item in task.panels]
    if not panel_orders:
        return False
    return panel.panel_order == max(panel_orders)


def build_original_story_final_prompt(
    aspect_ratio: str,
    visual_prompt: str,
    reference_notes: list[str] | None = None,
    exact_text: str = "",
    style_prompt: str | None = None,
    panel_order: int = 1,
) -> str:
    image_text = {
        "title": None,
        "narration": exact_text,
        "dialogue": None,
        "inner_os": None,
        "emphasis": None,
    }
    lines = [
        f"画面比例：{aspect_ratio}",
        "",
        "参考：",
        reference_notes_block(reference_notes),
    ]
    lines.extend(style_prompt_block(style_prompt))
    lines.extend(
        [
            "",
            "结构化分镜：",
            structured_storyboard_block(
                panel_order=panel_order,
                visual_prompt=visual_prompt,
                image_text=image_text,
                text_layout="单页漫画构图",
            ),
            "",
            "上面的字段名只用于理解分镜结构，不要把“画面”“旁白”“对话”“内心OS”等字段名画进图片。",
            "必须把“旁白”中的原文完整写入图片中，逐字一致，不能增加、删除、替换或改写任何一个字。",
            "不要添加这段原文之外的任何文字、Logo 或水印。",
        ]
    )
    return "\n".join(lines).strip()


def build_adapted_story_final_prompt(
    aspect_ratio: str,
    visual_prompt: str,
    story_beat: str,
    panel_type: PanelType = PanelType.scene,
    image_text: ImageTextPlan | dict[str, str | None] | None = None,
    reference_notes: list[str] | None = None,
    text_layout: str | None = None,
    style_prompt: str | None = None,
    panel_order: int = 1,
) -> str:
    lines = [
        f"画面比例：{aspect_ratio}",
        "",
        "参考：",
        reference_notes_block(reference_notes),
    ]
    lines.extend(style_prompt_block(style_prompt))
    lines.extend(
        [
            "",
            "剧情意图：",
            story_beat.strip(),
            "",
            "结构化分镜：",
            structured_storyboard_block(
                panel_order=panel_order,
                visual_prompt=visual_prompt,
                image_text=image_text,
                text_layout=text_layout,
            ),
        ]
    )
    layout_line = layout_instruction(text_layout)
    if layout_line:
        lines.extend(["", layout_line])
    lines.extend(
        [
            "",
            "上面的字段名只用于理解分镜结构，不要把“画面”“旁白”“对话”“内心OS”“标题”“强调”等字段名画进图片。",
            "图片里只绘制字段值对应的内容：旁白用旁白框或字幕框，visual_prompt 中的人物说话用对白气泡，内心OS用思想气泡或心理独白框，标题和强调字按画面需要突出呈现。",
        ]
    )
    rules = text_rules_block(visual_prompt, image_text, text_layout)
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
    style_prompt = task.style_prompt_snapshot
    if task.story_input_mode == StoryInputMode.original:
        return build_original_story_final_prompt(
            aspect_ratio=task.style_aspect_ratio_snapshot,
            visual_prompt=visual_prompt,
            reference_notes=reference_notes,
            exact_text=panel.original_text_segment,
            style_prompt=style_prompt,
            panel_order=panel.panel_order,
        )
    return build_adapted_story_final_prompt(
        aspect_ratio=task.style_aspect_ratio_snapshot,
        visual_prompt=visual_prompt,
        story_beat=panel.original_text_segment,
        panel_type=panel.panel_type,
        image_text=image_text,
        reference_notes=reference_notes,
        text_layout=panel.text_layout,
        style_prompt=style_prompt,
        panel_order=panel.panel_order,
    )


def build_generation_reference_pack(task: GenerationTask, panel: TaskPanel) -> GenerationReferencePack:
    if is_last_panel_real_photo_panel(task, panel):
        return GenerationReferencePack(
            references=[],
            notes=["最后一张真人图片：本 panel 不携带漫画风格参考图或人物参考图，按真实摄影照片生成。"],
            character_reference_count=0,
            style_reference_count=0,
        )

    if task.use_character_references:
        character_pack = build_panel_reference_pack(panel=panel)
        references = list(character_pack.references)
        notes = list(character_pack.notes)
        character_reference_count = character_pack.character_count
    else:
        references = []
        notes = []
        character_reference_count = 0

    style_pack = build_task_style_reference_pack(task, start_index=len(references) + 1)
    references.extend(style_pack.references)
    notes.extend(style_pack.notes)

    reference_pack = GenerationReferencePack(
        references=references,
        notes=notes,
        character_reference_count=character_reference_count,
        style_reference_count=style_pack.style_count,
    )
    return trim_generation_reference_pack_for_model(reference_pack, task.image_model_name_snapshot)


def trim_generation_reference_pack_for_model(
    reference_pack: GenerationReferencePack, image_model_name: str
) -> GenerationReferencePack:
    reference_limit = image_gateway_reference_limit(image_model_name)
    if len(reference_pack.references) <= reference_limit:
        return reference_pack

    kept_character_count = min(reference_pack.character_reference_count, reference_limit)
    kept_style_count = max(0, reference_limit - kept_character_count)
    logger.warning(
        "generation reference pack truncated image_model=%s original_reference_count=%s kept_reference_count=%s "
        "original_character_reference_count=%s kept_character_reference_count=%s "
        "original_style_reference_count=%s kept_style_reference_count=%s",
        image_model_name,
        len(reference_pack.references),
        reference_limit,
        reference_pack.character_reference_count,
        kept_character_count,
        reference_pack.style_reference_count,
        kept_style_count,
    )
    return GenerationReferencePack(
        references=reference_pack.references[:reference_limit],
        notes=reference_pack.notes[:reference_limit],
        character_reference_count=kept_character_count,
        style_reference_count=kept_style_count,
    )


def panel_image_text_payload(panel: TaskPanel) -> dict[str, str | None]:
    return parse_image_text_json(panel.image_text_json) or {
        "title": None,
        "narration": panel.narration_text,
        "dialogue": panel.dialogue_text,
        "inner_os": None,
        "emphasis": None,
    }


def task_character_payload(db: Session, task: GenerationTask) -> list[dict[str, Any]]:
    characters = load_task_characters(db, task.id)
    payload: list[dict[str, Any]] = []
    for character in sorted(characters, key=lambda item: item.character_key):
        source_type = "user_fixed_character" if is_fixed_task_character(character) else "task_temporary_character"
        payload.append(
            {
                "character_key": character.character_key,
                "name": character.name,
                "source_type": source_type,
                "description": character.description,
                "appearances": [
                    {
                        "appearance_key": appearance.appearance_key,
                        "age_stage": appearance.age_stage,
                        "visual_prompt": appearance.visual_prompt,
                        "reference_image_ready": bool(
                            appearance.status == WorkflowStatus.succeeded and appearance.reference_image_id
                        ),
                    }
                    for appearance in sorted(character.appearances, key=lambda item: item.appearance_key)
                ],
            }
        )
    return payload


def final_prompt_task_payload(task: GenerationTask) -> dict[str, Any]:
    style_prompt = task.style_prompt_snapshot
    return {
        "task_id": task.id,
        "story_input_mode": task.story_input_mode.value,
        "original_text": task.original_text,
        "story_context": story_text_for_generation(task),
        "aspect_ratio": task.style_aspect_ratio_snapshot,
        "style_name": task.style_name_snapshot,
        "style_reference_mode": task.style_reference_mode_snapshot.value,
        "style_prompt": style_prompt,
        "image_model_name": task.image_model_name_snapshot,
        "role_priority_rule": "角色身份 > 当前剧情动作/情绪 > 风格表现方式 > 风格模板默认人物外观",
    }


def final_prompt_panel_payload(
    *,
    panel: TaskPanel,
    visual_prompt: str,
    image_text: dict[str, str | None],
    reference_pack: GenerationReferencePack,
) -> dict[str, Any]:
    return {
        "panel_id": panel.id,
        "panel_order": panel.panel_order,
        "panel_type": panel.panel_type.value,
        "story_beat": panel.original_text_segment,
        "visual_prompt": visual_prompt,
        "text_layout": panel.text_layout,
        "image_text": image_text,
        "structured_storyboard": structured_storyboard_block(
            panel_order=panel.panel_order,
            visual_prompt=visual_prompt,
            image_text=image_text,
            text_layout=panel.text_layout,
        ),
        "layout_instruction": layout_instruction(panel.text_layout),
        "text_rules": text_rules_block(visual_prompt, image_text, panel.text_layout),
        "reference_notes": reference_pack.notes,
        "reference_count": len(reference_pack.references),
        "character_reference_count": reference_pack.character_reference_count,
        "style_reference_count": reference_pack.style_reference_count,
    }


def compose_final_prompts_for_panels(
    *,
    db: Session,
    task: GenerationTask,
    panels: list[TaskPanel],
    reference_packs: dict[str, GenerationReferencePack],
    image_text_by_panel_id: dict[str, dict[str, str | None]] | None = None,
    visual_prompt_by_panel_id: dict[str, str] | None = None,
    trace_step: str,
) -> dict[int, str]:
    if not panels:
        return {}
    panel_payloads = []
    for panel in panels:
        visual_prompt = (
            visual_prompt_by_panel_id.get(panel.id)
            if visual_prompt_by_panel_id is not None
            else panel.generated_prompt
        ) or ""
        image_text = (
            image_text_by_panel_id.get(panel.id)
            if image_text_by_panel_id is not None
            else panel_image_text_payload(panel)
        )
        panel_payloads.append(
            final_prompt_panel_payload(
                panel=panel,
                visual_prompt=visual_prompt,
                image_text=image_text,
                reference_pack=reference_packs[panel.id],
            )
        )

    result = compose_final_image_prompts(
        task_payload=final_prompt_task_payload(task),
        panels=panel_payloads,
        characters=task_character_payload(db, task),
        trace_context=task_trace_context(
            task,
            trace_step,
            panel_orders=[panel.panel_order for panel in panels],
            panel_count=len(panels),
        ),
    )
    image_text_by_order = {payload["panel_order"]: payload["image_text"] for payload in panel_payloads}
    reference_notes_by_order = {payload["panel_order"]: payload["reference_notes"] for payload in panel_payloads}
    real_photo_orders = {
        panel.panel_order
        for panel in panels
        if is_last_panel_real_photo_panel(task, panel)
    }
    prompt_by_order = {}
    for panel in result.panels:
        sanitized_prompt = sanitize_compiled_final_prompt(
            panel.final_prompt,
            image_text_by_order.get(panel.panel_order),
        )
        prompt_by_order[panel.panel_order] = final_prompt_with_explicit_style(
            task,
            sanitized_prompt,
            reference_notes=reference_notes_by_order.get(panel.panel_order),
            force_real_photo=panel.panel_order in real_photo_orders,
        )
    for panel in result.panels:
        final_prompt = prompt_by_order[panel.panel_order]
        log_prompt_trace(
            logger,
            "final_image_prompt_composed_by_llm",
            context=task_trace_context(task, trace_step, panel_order=panel.panel_order),
            consistency_notes=panel.consistency_notes,
            llm_final_prompt_chars=len(panel.final_prompt),
            llm_final_prompt=panel.final_prompt,
            style_prompt_included=is_prompt_reference_mode(task.style_reference_mode_snapshot)
            and bool((task.style_prompt_snapshot or "").strip()),
            final_prompt_chars=len(final_prompt),
            final_prompt=final_prompt,
        )
    return prompt_by_order


def current_succeeded_images_by_panel(task: GenerationTask) -> dict[str, GeneratedImage]:
    return {
        image.panel_id: image
        for image in task.generated_images
        if image.job_kind == GeneratedImageJobKind.panel_image
        and image.panel_id is not None
        and image.is_current
        and image.status == GeneratedImageStatus.succeeded
        and image.asset_id is not None
    }


def next_generation_number(db: Session, panel_id: str) -> int:
    current_max = db.scalar(select(func.max(GeneratedImage.generation_number)).where(GeneratedImage.panel_id == panel_id))
    return (current_max or 0) + 1


def mark_image_current(db: Session, image: GeneratedImage) -> None:
    if image.panel_id is None:
        return
    for existing in db.scalars(
        select(GeneratedImage).where(
            GeneratedImage.job_kind == GeneratedImageJobKind.panel_image,
            GeneratedImage.panel_id == image.panel_id,
        )
    ).all():
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
            len(task.style_reference_images),
            len(story_segments),
        )

        if task.use_character_references:
            characters = load_task_characters(db, task.id)
            has_generated_characters = any(not is_fixed_task_character(character) for character in characters)
            if characters and has_generated_characters:
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
                        persisted_character_plans = []
                        logger.info(
                            "story_drawing_debug character_extraction_empty task_id=%s existing_character_count=%s elapsed_ms=%s",
                            task.id,
                            len(characters),
                            round((monotonic() - step_started) * 1000),
                        )
                    elif characters:
                        persisted_character_plans = persist_missing_generated_character_plans(
                            db,
                            task,
                            character_result.characters,
                        )
                    else:
                        persist_character_plans(db, task, character_result.characters)
                        persisted_character_plans = character_result.characters
                    if task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
                        task = load_task(db, task_id)
                        if task is None:
                            return
                        if persisted_character_plans:
                            save_character_plan_panel_links(
                                db=db,
                                task=task,
                                character_plans=persisted_character_plans,
                            )
                    task.progress_current = 2
                    set_step(db, task, GenerationStepName.extract_characters, StepStatus.succeeded)
                    logger.info(
                        "story_drawing_debug character_extraction_done task_id=%s character_count=%s appearance_count=%s persisted_character_count=%s elapsed_ms=%s",
                        task.id,
                        len(character_result.characters),
                        sum(len(character.appearances) for character in character_result.characters),
                        len(persisted_character_plans),
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
                    len(task.style_reference_images),
                )
                job_plan = ensure_character_reference_image_jobs(
                    db=db,
                    task=task,
                )
                if job_plan.failed_count > 0:
                    fail_step_and_task(
                        db,
                        task,
                        GenerationStepName.generate_character_references,
                        ImageProviderResponseError(f"人物参考图生成失败：{job_plan.failed_count} 个角色形象未生成成功"),
                    )
                    return
                if job_plan.created_count > 0 or job_plan.active_count > 0:
                    task.status = TaskStatus.running
                    task.current_step = GenerationStepName.generate_character_references
                    task.progress_current = max(task.progress_current, 2)
                    db.commit()
                    logger.info(
                        "story_drawing_debug character_reference_jobs_waiting task_id=%s created_count=%s active_count=%s succeeded_count=%s elapsed_ms=%s",
                        task.id,
                        job_plan.created_count,
                        job_plan.active_count,
                        job_plan.succeeded_count,
                        round((monotonic() - step_started) * 1000),
                    )
                    return
                task.progress_current = 3
                set_step(db, task, GenerationStepName.generate_character_references, StepStatus.succeeded)
                logger.info(
                    "story_drawing_debug character_reference_done task_id=%s elapsed_ms=%s",
                    task.id,
                    round((monotonic() - step_started) * 1000),
                )
            except ImageProviderConfigError as exc:
                fail_step_and_task(db, task, GenerationStepName.generate_character_references, exc)
                return

        task = load_task(db, task_id)
        if task is None:
            return
        if should_stop_for_cancel(db, task):
            return

        if task.use_character_references and task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
            ensure_fixed_character_panel_links_by_name(db, task)
            db.commit()

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
            len(task.style_reference_images),
            task.image_model_name_snapshot,
            task.style_aspect_ratio_snapshot,
        )
        success_count = 0
        skipped_count = 0
        pending_panels: list[TaskPanel] = []
        reference_packs_by_panel_id: dict[str, GenerationReferencePack] = {}
        existing_successes = current_succeeded_images_by_panel(task)
        active_panel_ids = {
            image.panel_id
            for image in task.generated_images
            if image.job_kind == GeneratedImageJobKind.panel_image
            and image.source_type != GeneratedImageSourceType.user_edit
            and image.status in {GeneratedImageStatus.queued, GeneratedImageStatus.running}
        }
        for panel in sorted(task.panels, key=lambda item: item.panel_order):
            if should_stop_for_cancel(db, task):
                return
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
            if panel.id in active_panel_ids:
                skipped_count += 1
                logger.info(
                    "task panel image skipped existing active job task_id=%s panel_id=%s panel_order=%s",
                    task.id,
                    panel.id,
                    panel.panel_order,
                )
                continue
            try:
                reference_packs_by_panel_id[panel.id] = build_generation_reference_pack(task, panel)
                pending_panels.append(panel)
            except ImageProviderConfigError as exc:
                fail_step_and_task(db, task, GenerationStepName.generate_images, exc)
                return

        try:
            final_prompts_by_order = compose_final_prompts_for_panels(
                db=db,
                task=task,
                panels=pending_panels,
                reference_packs=reference_packs_by_panel_id,
                trace_step="generate_images_final_prompt",
            )
        except LLMProviderError as exc:
            fail_step_and_task(db, task, GenerationStepName.generate_images, exc)
            return

        for panel in pending_panels:
            reference_pack = reference_packs_by_panel_id[panel.id]
            panel_references = reference_pack.references
            character_reference_count = reference_pack.character_reference_count
            style_reference_count = reference_pack.style_reference_count
            final_prompt = final_prompts_by_order[panel.panel_order]
            log_prompt_trace(
                logger,
                "final_image_prompt_ready",
                context=task_trace_context(
                    task,
                    "generate_images",
                    panel_id=panel.id,
                    panel_order=panel.panel_order,
                ),
                reference_notes=reference_pack.notes,
                reference_count=len(panel_references),
                character_reference_count=character_reference_count,
                style_reference_count=style_reference_count,
                visual_prompt=panel.generated_prompt,
                image_text_json=panel.image_text_json,
                final_prompt_chars=len(final_prompt),
                final_prompt=final_prompt,
            )
            logger.info(
                "story_drawing_debug final_prompt_ready task_id=%s panel_id=%s panel_order=%s reference_count=%s character_reference_count=%s style_reference_count=%s visual_prompt_chars=%s final_prompt_chars=%s",
                task.id,
                panel.id,
                panel.panel_order,
                len(panel_references),
                character_reference_count,
                style_reference_count,
                len(panel.generated_prompt or ""),
                len(final_prompt),
            )
            image = GeneratedImage(
                task_id=task.id,
                panel_id=panel.id,
                job_kind=GeneratedImageJobKind.panel_image,
                owner_user_id=task.owner_user_id,
                status=GeneratedImageStatus.queued,
                generation_number=next_generation_number(db, panel.id),
                is_current=False,
                source_type=GeneratedImageSourceType.retry if task.attempts > 0 else GeneratedImageSourceType.initial,
                workflow_step=GeneratedImageWorkflowStep.generate_image,
                queued_at=datetime.utcnow(),
                queue_group=task.owner_user_id,
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
                "story_drawing_debug generated_image_job_created task_id=%s panel_id=%s panel_order=%s image_id=%s generation_number=%s source_type=%s",
                task.id,
                panel.id,
                panel.panel_order,
                image.id,
                image.generation_number,
                image.source_type.value,
            )
        update_task_image_generation_state(db, task.id)
        logger.info(
            "story_drawing_debug image_jobs_queued task_id=%s success_count=%s skipped_existing_count=%s pending_panel_count=%s elapsed_ms=%s image_step_elapsed_ms=%s",
            task.id,
            success_count,
            skipped_count,
            len(pending_panels),
            round((monotonic() - task_started) * 1000),
            round((monotonic() - image_step_started) * 1000),
        )


def load_generated_image(db: Session, generated_image_id: str) -> GeneratedImage | None:
    return db.scalar(
        select(GeneratedImage)
        .where(GeneratedImage.id == generated_image_id)
        .options(
            selectinload(GeneratedImage.task)
            .selectinload(GenerationTask.style_reference_images)
            .selectinload(TaskStyleReferenceImage.asset),
            selectinload(GeneratedImage.panel)
            .selectinload(TaskPanel.character_appearances)
            .selectinload(TaskPanelCharacterAppearance.appearance)
            .selectinload(TaskCharacterAppearance.character),
            selectinload(GeneratedImage.panel)
            .selectinload(TaskPanel.character_appearances)
            .selectinload(TaskPanelCharacterAppearance.appearance)
            .selectinload(TaskCharacterAppearance.reference_image),
            selectinload(GeneratedImage.character_appearance).selectinload(TaskCharacterAppearance.character),
            selectinload(GeneratedImage.character_appearance).selectinload(TaskCharacterAppearance.reference_image),
            selectinload(GeneratedImage.asset),
        )
    )


def clear_image_job_lock(image: GeneratedImage) -> None:
    image.lease_until = None
    image.locked_by = None


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
            image.final_prompt = None
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
            clear_image_job_lock(image)
            db.commit()
            return

        style = db.scalar(select(Style).where(Style.id == task.style_id))
        if style is None:
            exc = ImageProviderConfigError("风格不存在")
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            clear_image_job_lock(image)
            db.commit()
            return

        try:
            reference_pack = build_generation_reference_pack(task, panel)
        except ImageProviderConfigError as exc:
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            clear_image_job_lock(image)
            db.commit()
            return
        references = reference_pack.references
        reference_notes = reference_pack.notes
        edit_image_text = parse_image_text_json(image.image_text_json) or panel_image_text_payload(panel)
        try:
            final_prompts_by_order = compose_final_prompts_for_panels(
                db=db,
                task=task,
                panels=[panel],
                reference_packs={panel.id: reference_pack},
                image_text_by_panel_id={panel.id: edit_image_text},
                visual_prompt_by_panel_id={panel.id: image.image_prompt or ""},
                trace_step="panel_edit_final_prompt",
            )
        except LLMProviderError as exc:
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            clear_image_job_lock(image)
            db.commit()
            return
        image.final_prompt = final_prompts_by_order[panel.panel_order]
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
            reference_count=len(references),
            character_reference_count=reference_pack.character_reference_count,
            style_reference_count=reference_pack.style_reference_count,
            visual_prompt=image.image_prompt,
            image_text_json=image.image_text_json,
            final_prompt_chars=len(image.final_prompt or ""),
            final_prompt=image.final_prompt,
        )
        db.commit()
        try:
            logger.info(
                "panel edit image request generated_image_id=%s task_id=%s panel_id=%s prompt_chars=%s reference_count=%s character_reference_count=%s style_reference_count=%s",
                image.id,
                task.id,
                panel.id,
                len(image.final_prompt or ""),
                len(references),
                reference_pack.character_reference_count,
                reference_pack.style_reference_count,
            )
            original_final_prompt = image.final_prompt or ""
            reserve_image_credit(
                db,
                user_id=task.owner_user_id,
                task_id=task.id,
                panel_id=panel.id,
                generated_image_id=image.id,
                note="单分镜修改生图占用",
            )
            db.commit()
            generated, actual_final_prompt, prompt_change_summary = generate_image_with_policy_prompt_rewrite(
                prompt=image.final_prompt or "",
                references=references,
                image_model_name=image.image_model_name_snapshot,
                aspect_ratio=task.style_aspect_ratio_snapshot,
                task_id=task.id,
                panel_id=panel.id,
                panel_order=panel.panel_order,
                image_id=image.id,
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
            if actual_final_prompt != original_final_prompt:
                image.final_prompt = actual_final_prompt
                image.prompt_change_summary = prompt_change_summary
            image.asset_id = asset.id
            image.provider_request_id = generated.provider_request_id
            charge_reserved_image_credit(
                db,
                user_id=task.owner_user_id,
                task_id=task.id,
                panel_id=panel.id,
                generated_image_id=image.id,
                note="单分镜修改成功产出扣费",
            )
            image.status = GeneratedImageStatus.succeeded
            image.finished_at = datetime.utcnow()
            clear_image_job_lock(image)
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
        except InsufficientCreditsError as exc:
            logger.warning(
                "panel edit image credit insufficient generated_image_id=%s task_id=%s panel_id=%s error=%s",
                image.id,
                task.id,
                panel.id,
                exc,
            )
            image.status = GeneratedImageStatus.failed
            image.error_code = exc.__class__.__name__
            image.error_message = str(exc)
            image.finished_at = datetime.utcnow()
            clear_image_job_lock(image)
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
            clear_image_job_lock(image)
            try:
                release_reserved_image_credit(
                    db,
                    user_id=task.owner_user_id,
                    task_id=task.id,
                    panel_id=panel.id,
                    generated_image_id=image.id,
                    note="单分镜修改生图失败释放积分占用",
                )
            except CreditError:
                logger.info("panel edit release skipped no reserved credit generated_image_id=%s", image.id)
        db.commit()
