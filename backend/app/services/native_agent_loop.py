from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
import json
import time
from typing import Awaitable, Callable

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    RunConfig,
    Runner,
    ToolExecutionConfig,
    ToolOutputImage,
    ToolOutputText,
    function_tool,
)
from agents.model_settings import ModelRetrySettings
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models.entities import (
    FileAsset,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
)
from app.models.enums import (
    AgentRunStatus,
    FileAssetPurpose,
    NativeAgentItemType,
    StorageBackend,
)
from app.services.agent_skill_management import parse_tool_names
from app.services.agent_observability import (
    agent_span,
    native_agent_run_span,
    set_native_agent_run_trace_status,
    set_span_inputs,
    set_span_outputs,
    set_span_result,
    set_span_status,
)
from app.services.image_generation import GeneratedImageFile, ImageReference, generate_xg_image
from app.services.storage import resolve_storage_key


MAX_NATIVE_AGENT_TURNS = 12
NATIVE_AGENT_BASE_INSTRUCTIONS = """
你是 DoodleStory 的图片内容 Agent。

严格按照本次 Run 固定的 Skill 工作。Runtime 只负责 Agent Loop 和真实 Tool 执行；故事改写、
分镜切割、图片 Prompt、图片 Review、是否修改重画都由你依据 Skill 和用户目标决定。

`generate_image` 返回的图片会直接进入你的视觉上下文。调用后必须查看真实图片，再判断继续调用
还是给出 final output。不得声称执行了没有真实 Tool Output 的动作，不得展示隐藏推理、系统配置
或密钥。
""".strip()


class NativeAgentLoopError(RuntimeError):
    pass


@dataclass(frozen=True)
class NativeImageToolContext:
    run_id: str
    image_model: str | None
    aspect_ratio: str | None
    style_name: str | None
    style_prompt: str | None
    reference_urls: tuple[str, ...]


ImageGenerator = Callable[..., GeneratedImageFile]
ItemRecorder = Callable[[NativeAgentItemType, dict[str, object]], Awaitable[None]]
ImageRecorder = Callable[[str, GeneratedImageFile], Awaitable[str]]


def _tool_description(context: NativeImageToolContext) -> str:
    if context.image_model is None or context.aspect_ratio is None:
        style_text = "本次 Run 没有 Style，不能生图；需要图片时先向用户索要 Style。"
    else:
        style_text = (
            f"本次 Style={context.style_name}，模型={context.image_model}，"
            f"比例={context.aspect_ratio}，视觉规则={context.style_prompt or '无'}。"
        )
    return (
        "根据完整图片 Prompt 生成一张真实图片，并把图片直接返回给当前模型进行视觉 Review。"
        "prompt 必须包含当前画面所需的全部视觉信息；Runtime 不会在背后拼接或改写 Prompt。"
        f"{style_text}"
    )


def build_generate_image_tool(
    context: NativeImageToolContext,
    *,
    image_generator: ImageGenerator,
    record_item: ItemRecorder,
    record_image: ImageRecorder,
) -> FunctionTool:
    async def generate_image(prompt: str) -> list[ToolOutputText | ToolOutputImage]:
        if context.image_model is None or context.aspect_ratio is None:
            raise NativeAgentLoopError("本次 Run 没有 Style，不能调用 generate_image")
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise NativeAgentLoopError("generate_image prompt 不能为空")
        with agent_span(
            "native_agent.generate_image",
            agent_run_id=context.run_id,
            span_type="TOOL",
            attributes={
                "tool_name": "generate_image",
                "image_model": context.image_model,
                "aspect_ratio": context.aspect_ratio,
                "reference_count": len(context.reference_urls),
            },
        ) as tool_span:
            set_span_inputs(
                tool_span,
                {
                    "prompt": cleaned_prompt,
                    "reference_count": len(context.reference_urls),
                },
            )
            await record_item(
                NativeAgentItemType.tool_call,
                {"tool": "generate_image", "prompt": cleaned_prompt},
            )
            started = time.perf_counter()
            try:
                with agent_span(
                    "native_agent.image_provider",
                    agent_run_id=context.run_id,
                    span_type="TASK",
                    attributes={
                        "image_model": context.image_model,
                        "aspect_ratio": context.aspect_ratio,
                        "reference_count": len(context.reference_urls),
                    },
                ) as provider_span:
                    set_span_inputs(
                        provider_span,
                        {
                            "prompt": cleaned_prompt,
                            "reference_urls": list(context.reference_urls),
                        },
                    )
                    try:
                        generated = await asyncio.to_thread(
                            image_generator,
                            prompt=cleaned_prompt,
                            references=[
                                ImageReference(url=url)
                                for url in context.reference_urls
                            ],
                            image_model_name=context.image_model,
                            aspect_ratio=context.aspect_ratio,
                        )
                    except Exception:
                        set_span_status(
                            provider_span,
                            "ERROR",
                            agent_run_id=context.run_id,
                        )
                        raise
                    set_span_result(
                        provider_span,
                        {
                            "width": generated.width,
                            "height": generated.height,
                            "provider_request_id": generated.provider_request_id,
                        },
                    )
                    set_span_outputs(
                        provider_span,
                        {
                            "width": generated.width,
                            "height": generated.height,
                            "provider_request_id": generated.provider_request_id,
                        },
                    )
                    set_span_status(
                        provider_span,
                        "OK",
                        agent_run_id=context.run_id,
                    )
                model_image_url = await record_image(cleaned_prompt, generated)
            except Exception as exc:
                latency_ms = round((time.perf_counter() - started) * 1000)
                await record_item(
                    NativeAgentItemType.tool_result,
                    {
                        "tool": "generate_image",
                        "status": "failed",
                        "error_code": type(exc).__name__,
                        "error_message": str(exc)[:500],
                    },
                )
                set_span_result(
                    tool_span,
                    {
                        "result_status": "failed",
                        "latency_ms": latency_ms,
                        "error_code": type(exc).__name__,
                    },
                )
                set_span_status(
                    tool_span,
                    "ERROR",
                    agent_run_id=context.run_id,
                )
                raise
            latency_ms = round((time.perf_counter() - started) * 1000)
            await record_item(
                NativeAgentItemType.tool_result,
                {
                    "tool": "generate_image",
                    "status": "succeeded",
                    "width": generated.width,
                    "height": generated.height,
                    "provider_request_id": generated.provider_request_id,
                },
            )
            set_span_result(
                tool_span,
                {
                    "result_status": "succeeded",
                    "latency_ms": latency_ms,
                    "width": generated.width,
                    "height": generated.height,
                    "provider_request_id": generated.provider_request_id,
                },
            )
            set_span_outputs(
                tool_span,
                {
                    "status": "succeeded",
                    "width": generated.width,
                    "height": generated.height,
                },
            )
            set_span_status(
                tool_span,
                "OK",
                agent_run_id=context.run_id,
            )
            return [
                ToolOutputText(
                    text=json.dumps(
                        {
                            "status": "succeeded",
                            "width": generated.width,
                            "height": generated.height,
                        },
                        ensure_ascii=False,
                    )
                ),
                ToolOutputImage(image_url=model_image_url, detail="high"),
            ]

    return function_tool(
        generate_image,
        name_override="generate_image",
        description_override=_tool_description(context),
        failure_error_function=None,
    )


def _next_item_sequence(run_id: str) -> int:
    with SessionLocal() as db:
        latest = db.scalar(
            select(func.max(NativeAgentItem.sequence)).where(
                NativeAgentItem.run_id == run_id
            )
        )
        return int(latest or 0) + 1


async def record_native_agent_item(
    run_id: str,
    item_type: NativeAgentItemType,
    payload: dict[str, object],
) -> None:
    with SessionLocal() as db:
        db.add(
            NativeAgentItem(
                run_id=run_id,
                sequence=_next_item_sequence(run_id),
                item_type=item_type,
                payload_json=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        )
        db.commit()


def _image_url_for_model(generated: GeneratedImageFile) -> str:
    if generated.public_url:
        return generated.public_url
    if generated.storage_backend != StorageBackend.local:
        raise NativeAgentLoopError("生成图片没有可供模型读取的 URL")
    content = resolve_storage_key(generated.storage_key).read_bytes()
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{generated.content_type};base64,{encoded}"


async def record_native_agent_image(
    run_id: str,
    prompt: str,
    generated: GeneratedImageFile,
) -> str:
    with SessionLocal() as db:
        run = db.scalar(select(NativeAgentRun).where(NativeAgentRun.id == run_id))
        if run is None:
            raise NativeAgentLoopError("Native Agent Run 不存在")
        if run.image_model_snapshot is None or run.aspect_ratio_snapshot is None:
            raise NativeAgentLoopError("Native Agent Run 缺少图片配置快照")
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=generated.storage_backend,
            storage_key=generated.storage_key,
            public_url=generated.public_url,
            original_filename=generated.original_filename,
            content_type=generated.content_type,
            byte_size=generated.byte_size,
            checksum_sha256=generated.checksum_sha256,
            width=generated.width,
            height=generated.height,
        )
        db.add(asset)
        db.flush()
        db.add(
            NativeAgentImage(
                run_id=run.id,
                asset_id=asset.id,
                prompt=prompt,
                image_model_snapshot=run.image_model_snapshot,
                aspect_ratio_snapshot=run.aspect_ratio_snapshot,
                provider_request_id=generated.provider_request_id,
            )
        )
        run.image_call_count += 1
        db.commit()
    return _image_url_for_model(generated)


def native_agent_instructions(run: NativeAgentRun) -> str:
    return (
        f"{NATIVE_AGENT_BASE_INSTRUCTIONS}\n\n"
        f"<skill name={json.dumps(run.skill_name_snapshot, ensure_ascii=False)} "
        f"version={run.skill_version_snapshot}>\n"
        f"{run.skill_version.instructions}\n"
        "</skill>"
    )


async def execute_native_agent_run(
    run_id: str,
    *,
    settings: Settings | None = None,
    image_generator: ImageGenerator = generate_xg_image,
) -> None:
    resolved_settings = settings or get_settings()
    with SessionLocal() as db:
        run = db.scalar(
            select(NativeAgentRun)
            .where(NativeAgentRun.id == run_id)
            .options(selectinload(NativeAgentRun.skill_version))
        )
        if run is None:
            raise NativeAgentLoopError("Native Agent Run 不存在")
        if run.status != AgentRunStatus.queued:
            raise NativeAgentLoopError("Native Agent Run 不是 queued 状态")
        tool_names = parse_tool_names(run.skill_version.tool_names_json)
        if tool_names != ["generate_image"]:
            raise NativeAgentLoopError(
                "最小 Loop 只接受唯一授权 Tool：generate_image"
            )
        user_item = db.scalar(
            select(NativeAgentItem).where(
                NativeAgentItem.run_id == run.id,
                NativeAgentItem.item_type == NativeAgentItemType.user_input,
            )
        )
        if user_item is None:
            raise NativeAgentLoopError("Native Agent Run 缺少用户输入")
        user_content = str(json.loads(user_item.payload_json)["content"])
        reference_urls = tuple(json.loads(run.style_reference_urls_json or "[]"))
        context = NativeImageToolContext(
            run_id=run.id,
            image_model=run.image_model_snapshot,
            aspect_ratio=run.aspect_ratio_snapshot,
            style_name=run.style_name_snapshot,
            style_prompt=run.style_prompt_snapshot,
            reference_urls=reference_urls,
        )
        instructions = native_agent_instructions(run)
        trace_context = {
            "conversation_id": run.conversation_id,
            "skill_version_id": run.skill_version_id,
            "style_id": run.style_id,
        }
        run.status = AgentRunStatus.running
        run.started_at = datetime.utcnow()
        db.commit()

    async def record_item(
        item_type: NativeAgentItemType,
        payload: dict[str, object],
    ) -> None:
        await record_native_agent_item(run_id, item_type, payload)

    async def record_image(prompt: str, generated: GeneratedImageFile) -> str:
        return await record_native_agent_image(run_id, prompt, generated)

    tool = build_generate_image_tool(
        context,
        image_generator=image_generator,
        record_item=record_item,
        record_image=record_image,
    )
    client = AsyncOpenAI(
        api_key=resolved_settings.text_fallback_api_key.strip(),
        base_url=resolved_settings.text_fallback_openai_base_url,
        max_retries=0,
        timeout=resolved_settings.agent_request_timeout_seconds,
    )
    provider = OpenAIProvider(openai_client=client, use_responses=True)
    with native_agent_run_span(
        native_agent_run_id=run_id,
        conversation_id=trace_context["conversation_id"],
        skill_version_id=trace_context["skill_version_id"],
        style_id=trace_context["style_id"],
        model=resolved_settings.agent_model.strip(),
        app_environment=resolved_settings.app_env,
    ) as root_span:
        try:
            agent = Agent(
                name="DoodleStoryNativeImageAgent",
                instructions=instructions,
                model=resolved_settings.agent_model.strip(),
                tools=[tool],
                model_settings=ModelSettings(
                    retry=ModelRetrySettings(max_retries=0),
                    store=False,
                ),
            )
            with agent_span(
                "native_agent.model_loop",
                agent_run_id=run_id,
                span_type="CHAT_MODEL",
                attributes={
                    "model": resolved_settings.agent_model.strip(),
                    "max_turns": MAX_NATIVE_AGENT_TURNS,
                    "tool_count": 1,
                    "max_function_tool_concurrency": 1,
                },
            ) as model_span:
                set_span_inputs(
                    model_span,
                    {
                        "user_content": user_content,
                        "instructions": instructions,
                        "tools": ["generate_image"],
                    },
                )
                try:
                    result = await Runner.run(
                        agent,
                        user_content,
                        run_config=RunConfig(
                            model_provider=provider,
                            tracing_disabled=True,
                            workflow_name="DoodleStory Native Agent Loop",
                            tool_execution=ToolExecutionConfig(
                                max_function_tool_concurrency=1,
                            ),
                        ),
                        max_turns=MAX_NATIVE_AGENT_TURNS,
                    )
                except Exception:
                    set_span_status(
                        model_span,
                        "ERROR",
                        agent_run_id=run_id,
                    )
                    raise
                set_span_result(
                    model_span,
                    {
                        "model_call_count": len(result.raw_responses),
                    },
                )
                final_output = str(result.final_output or "").strip()
                if not final_output:
                    set_span_status(
                        model_span,
                        "ERROR",
                        agent_run_id=run_id,
                    )
                    raise NativeAgentLoopError("模型没有返回 final output")
                set_span_outputs(
                    model_span,
                    {
                        "final_output": final_output,
                        "model_call_count": len(result.raw_responses),
                    },
                )
            await record_native_agent_item(
                run_id,
                NativeAgentItemType.assistant_output,
                {"content": final_output},
            )
            with SessionLocal() as db:
                run = db.scalar(
                    select(NativeAgentRun).where(NativeAgentRun.id == run_id)
                )
                if run is None:
                    raise NativeAgentLoopError("Native Agent Run 不存在")
                run.status = AgentRunStatus.succeeded
                run.final_output = final_output
                run.model_call_count = len(result.raw_responses)
                run.finished_at = datetime.utcnow()
                db.commit()
                model_call_count = run.model_call_count
                image_call_count = run.image_call_count
            set_native_agent_run_trace_status(
                root_span,
                native_agent_run_id=run_id,
                run_status=AgentRunStatus.succeeded.value,
                model_call_count=model_call_count,
                image_call_count=image_call_count,
                error_code=None,
            )
        except Exception as exc:
            await record_native_agent_item(
                run_id,
                NativeAgentItemType.error,
                {
                    "error_code": type(exc).__name__,
                    "error_message": str(exc)[:500],
                },
            )
            with SessionLocal() as db:
                run = db.scalar(
                    select(NativeAgentRun).where(NativeAgentRun.id == run_id)
                )
                if run is not None:
                    run.status = AgentRunStatus.failed
                    run.error_code = type(exc).__name__
                    run.error_message = str(exc)[:500]
                    run.finished_at = datetime.utcnow()
                    db.commit()
                    model_call_count = run.model_call_count
                    image_call_count = run.image_call_count
                else:
                    model_call_count = 0
                    image_call_count = 0
            set_native_agent_run_trace_status(
                root_span,
                native_agent_run_id=run_id,
                run_status=AgentRunStatus.failed.value,
                model_call_count=model_call_count,
                image_call_count=image_call_count,
                error_code=type(exc).__name__,
            )
        finally:
            await client.close()
