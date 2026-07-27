from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json
import time
from typing import Callable

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
from agents.tool_context import ToolContext
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models.entities import FileAsset, NativeAgentItem, NativeAgentRun
from app.models.enums import (
    AgentRunStatus,
    NativeAgentItemType,
)
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
from app.services.native_agent_persistence import (
    CompletedNativeTool,
    NativeAgentDatabaseSession,
    NativeAgentStore,
)
from app.services.storage import materialize_asset_to_local


MAX_NATIVE_AGENT_TURNS = 12
NATIVE_AGENT_BASE_INSTRUCTIONS = """
你是 DoodleStory 的图片内容 Agent。

严格按照本次 Run 固定的 Skill 工作。Runtime 只负责 Agent Loop 和真实 Tool 执行；故事改写、
分镜切割、图片 Prompt、图片 Review、是否修改重画都由你依据 Skill 和用户目标决定。

像 Codex 一样主动向用户提供简短、可核查的创作进展，不要沉默执行：
1. 开始创作时，说明故事切分思路、旁白/对白取舍和整体画面节奏。
2. 每次调用 `generate_image` 前，先说明当前画面要表达的剧情、情绪、构图和文字安排。
3. 查看工具返回的真实图片后，说明 Review 结论、发现的问题，以及接受或重画的决定。
这些内容是面向用户的创作决策摘要，不是隐藏思维链；不要输出冗长自言自语。

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
    reference_urls: tuple[str, ...]


ImageGenerator = Callable[..., GeneratedImageFile]


def _tool_description() -> str:
    return (
        "根据完整图片 Prompt 生成一张真实图片，并把图片直接返回给当前模型进行视觉 Review。"
        "prompt 必须包含当前画面所需的全部视觉信息；Runtime 不会在背后拼接或改写 Prompt。"
    )


def build_generate_image_tool(
    context: NativeImageToolContext,
    *,
    image_generator: ImageGenerator,
    store: NativeAgentStore,
) -> FunctionTool:
    async def generate_image(
        tool_context: ToolContext[None],
        prompt: str,
    ) -> list[ToolOutputText | ToolOutputImage]:
        if context.image_model is None or context.aspect_ratio is None:
            raise NativeAgentLoopError("本次 Run 没有 Style，不能调用 generate_image")
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise NativeAgentLoopError("generate_image prompt 不能为空")
        prepared = store.prepare_tool(
            tool_call_id=tool_context.tool_call_id,
            prompt=cleaned_prompt,
        )
        if isinstance(prepared, CompletedNativeTool):
            store.append_event(
                "tool.reused",
                {
                    "tool": "generate_image",
                    "tool_call_id": tool_context.tool_call_id,
                    "step_id": prepared.step_id,
                    "image_id": prepared.image_id,
                },
            )
            return await _tool_outputs(prepared)
        store.start_tool(prepared.id)
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
                completed = store.complete_tool(
                    prepared.id,
                    prompt=cleaned_prompt,
                    generated=generated,
                    image_model=context.image_model,
                    aspect_ratio=context.aspect_ratio,
                )
            except Exception as exc:
                latency_ms = round((time.perf_counter() - started) * 1000)
                store.fail_tool(prepared.id, exc)
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
            return await _tool_outputs(completed)

    return function_tool(
        generate_image,
        name_override="generate_image",
        description_override=_tool_description(),
        failure_error_function=None,
    )


def _completed_image_url(completed: CompletedNativeTool) -> str:
    if completed.public_url and completed.public_url.startswith("data:"):
        return completed.public_url
    with SessionLocal() as db:
        asset = db.get(FileAsset, completed.asset_id)
        if asset is None:
            raise NativeAgentLoopError("生成图片引用的资产不存在")
        content = materialize_asset_to_local(asset).read_bytes()
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{completed.content_type};base64,{encoded}"


async def _tool_outputs(
    completed: CompletedNativeTool,
) -> list[ToolOutputText | ToolOutputImage]:
    image_url = await asyncio.to_thread(_completed_image_url, completed)
    return [
        ToolOutputText(
            text=json.dumps(
                {
                    "status": "succeeded",
                    "image_id": completed.image_id,
                    "width": completed.width,
                    "height": completed.height,
                },
                ensure_ascii=False,
            )
        ),
        ToolOutputImage(
            image_url=image_url,
            detail="high",
        ),
    ]


def native_agent_instructions(run: NativeAgentRun) -> str:
    image_generation_context = json.dumps(
        {
            "style_name": run.style_name_snapshot,
            "aspect_ratio": run.aspect_ratio_snapshot,
            "style_prompt": run.style_prompt_snapshot,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"{NATIVE_AGENT_BASE_INSTRUCTIONS}\n\n"
        f"<skill name={json.dumps(run.skill_name_snapshot, ensure_ascii=False)} "
        f"version={run.skill_version_snapshot}>\n"
        f"{run.skill_version.instructions}\n"
        "</skill>\n\n"
        "<image_generation_context>\n"
        "以下 Style 只用于规划图片、编写 generate_image prompt 和 Review 图片，不得改变故事事实、"
        "旁白或对白。每次调用 generate_image 时，必须把适用于该画面的视觉规则和比例写入完整 "
        "prompt；Runtime 不会代为拼接。\n"
        f"{image_generation_context}\n"
        "</image_generation_context>"
    )


async def execute_native_agent_run(
    run_id: str,
    *,
    settings: Settings | None = None,
    image_generator: ImageGenerator = generate_xg_image,
) -> None:
    resolved_settings = settings or get_settings()
    store = NativeAgentStore(run_id, session_factory=SessionLocal)
    sdk_session = NativeAgentDatabaseSession(
        run_id,
        session_factory=SessionLocal,
    )
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
            reference_urls=reference_urls,
        )
        instructions = native_agent_instructions(run)
        trace_context = {
            "conversation_id": run.conversation_id,
            "skill_version_id": run.skill_version_id,
            "style_id": run.style_id,
        }
    resumed = await sdk_session.has_items()
    store.start_run(resumed=resumed)

    tool = build_generate_image_tool(
        context,
        image_generator=image_generator,
        store=store,
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
                    result = Runner.run_streamed(
                        agent,
                        [] if resumed else user_content,
                        run_config=RunConfig(
                            model_provider=provider,
                            tracing_disabled=True,
                            workflow_name="DoodleStory Native Agent Loop",
                            tool_execution=ToolExecutionConfig(
                                max_function_tool_concurrency=1,
                            ),
                        ),
                        max_turns=MAX_NATIVE_AGENT_TURNS,
                        session=sdk_session,
                    )
                    text_delta_buffer = ""
                    last_delta_flush = time.monotonic()
                    async for event in result.stream_events():
                        if event.type != "raw_response_event":
                            continue
                        raw_event = event.data
                        raw_type = getattr(raw_event, "type", "")
                        if raw_type == "response.created":
                            store.start_model_step(raw_event.response.id)
                        elif raw_type == "response.output_text.delta":
                            text_delta_buffer += raw_event.delta
                            now = time.monotonic()
                            if (
                                len(text_delta_buffer) >= 80
                                or now - last_delta_flush >= 0.25
                            ):
                                store.append_text_delta(text_delta_buffer)
                                text_delta_buffer = ""
                                last_delta_flush = now
                        elif raw_type == "response.completed":
                            if text_delta_buffer:
                                store.append_text_delta(text_delta_buffer)
                                text_delta_buffer = ""
                                last_delta_flush = time.monotonic()
                            usage = getattr(raw_event.response, "usage", None)
                            usage_payload = (
                                usage.model_dump(mode="json")
                                if usage is not None
                                else None
                            )
                            store.complete_model_step(
                                raw_event.response.id,
                                usage=usage_payload,
                            )
                    if text_delta_buffer:
                        store.append_text_delta(text_delta_buffer)
                except Exception as exc:
                    store.fail_active_model_step(exc)
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
            store.complete_run(final_output)
            with SessionLocal() as db:
                run = db.get(NativeAgentRun, run_id)
                if run is None:
                    raise NativeAgentLoopError("Native Agent Run 不存在")
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
            store.fail_run(exc)
            with SessionLocal() as db:
                run = db.get(NativeAgentRun, run_id)
                model_call_count = run.model_call_count if run is not None else 0
                image_call_count = run.image_call_count if run is not None else 0
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
