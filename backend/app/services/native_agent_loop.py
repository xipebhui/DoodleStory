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
from app.services.agent_skill_management import parse_tool_names
from app.services.image_generation import (
    GeneratedImageFile,
    ImageProviderResponseError,
    ImageReference,
    generate_xg_image,
)
from app.services.native_agent_persistence import (
    CompletedNativeSpeech,
    CompletedNativeTool,
    NativeAgentDatabaseSession,
    NativeAgentStore,
)
from app.services.storage import materialize_asset_to_local
from app.services.volcengine_speech import (
    GeneratedSpeech,
    VolcengineSpeechClient,
)


MAX_NATIVE_AGENT_TURNS = 12
MAX_NATIVE_AGENT_TOOL_CONCURRENCY = 2
NATIVE_AGENT_BASE_INSTRUCTIONS = """
你是专注于内容创作的agent, 主要的工作是根据用户输入提示，生成图片，或者文本图片配音的视频。

严格按照本次 Run 固定的 Skill 工作。Runtime 只负责 Agent Loop 和真实 Tool 执行；故事改写、
分镜切割、图片 Prompt、图片 Review、视频生成、语音生成、字幕是否修改重画都由你依据 Skill 和用户目标决定。

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
SpeechGenerator = Callable[..., GeneratedSpeech]
NATIVE_RUNTIME_TOOL_NAMES = frozenset({"generate_image", "generate_speech"})


def native_runtime_tool_names(tool_names_json: str) -> list[str]:
    return [
        name
        for name in parse_tool_names(tool_names_json)
        if name in NATIVE_RUNTIME_TOOL_NAMES
    ]


def _tool_description() -> str:
    return (
        "根据完整图片 Prompt 生成一张真实图片，并把图片直接返回给当前模型进行视觉 Review。"
        "prompt 必须包含当前画面所需的全部视觉信息；Runtime 不会在背后拼接或改写 Prompt。"
    )


def _speech_tool_description(settings: Settings) -> str:
    return (
        "把给定文本合成为一段真实语音，并保存为当前 Run 的可播放音频。"
        "每次调用只处理 text 原文，不会改写、拆分或拼接文本。"
        f"语音模型固定为 {settings.doubao_voice_gen_model.strip()}，"
        f"音色固定为 {settings.doubao_voice_gen_speaker.strip()}。"
        "工具返回音频资产元数据；不要声称已经听取或审核音频内容。"
    )


def generate_volcengine_speech(
    *,
    text: str,
    settings: Settings | None = None,
) -> GeneratedSpeech:
    return VolcengineSpeechClient(settings=settings).generate_speech(text=text)


def _image_tool_failure_output(
    _context: object,
    error: Exception,
) -> str | None:
    if (
        not isinstance(error, ImageProviderResponseError)
        or "HTTP 400" not in str(error)
    ):
        return None
    return json.dumps(
        {
            "status": "failed",
            "error_type": "image_provider_error",
            "message": str(error),
            "next_action": (
                "这是一次已确认失败的图片工具调用。请根据错误和当前 Skill 决定是否修改 Prompt "
                "后再次调用 generate_image，或向用户说明无法继续；不要声称本次已经生成图片。"
            ),
        },
        ensure_ascii=False,
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
        failure_error_function=_image_tool_failure_output,
    )


def build_generate_speech_tool(
    run_id: str,
    *,
    settings: Settings,
    speech_generator: SpeechGenerator,
    store: NativeAgentStore,
) -> FunctionTool:
    async def generate_speech(
        tool_context: ToolContext[None],
        text: str,
    ) -> list[ToolOutputText]:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise NativeAgentLoopError("generate_speech text 不能为空")
        prepared = store.prepare_speech_tool(
            tool_call_id=tool_context.tool_call_id,
            text=cleaned_text,
        )
        if isinstance(prepared, CompletedNativeSpeech):
            store.append_event(
                "tool.reused",
                {
                    "tool": "generate_speech",
                    "tool_call_id": tool_context.tool_call_id,
                    "step_id": prepared.step_id,
                    "audio_id": prepared.audio_id,
                },
            )
            return _speech_tool_outputs(prepared)
        store.start_tool(prepared.id)
        with agent_span(
            "native_agent.generate_speech",
            agent_run_id=run_id,
            span_type="TOOL",
            attributes={
                "tool_name": "generate_speech",
                "resource_id": settings.doubao_voice_gen_resource_id.strip(),
                "model": settings.doubao_voice_gen_model.strip(),
                "speaker": settings.doubao_voice_gen_speaker.strip(),
            },
        ) as tool_span:
            set_span_inputs(tool_span, {"text": cleaned_text})
            started = time.perf_counter()
            try:
                with agent_span(
                    "native_agent.speech_provider",
                    agent_run_id=run_id,
                    span_type="TASK",
                    attributes={
                        "provider": "volcengine",
                        "resource_id": settings.doubao_voice_gen_resource_id.strip(),
                        "model": settings.doubao_voice_gen_model.strip(),
                        "speaker": settings.doubao_voice_gen_speaker.strip(),
                    },
                ) as provider_span:
                    set_span_inputs(provider_span, {"text": cleaned_text})
                    try:
                        generated = await asyncio.to_thread(
                            speech_generator,
                            text=cleaned_text,
                        )
                    except Exception:
                        set_span_status(
                            provider_span,
                            "ERROR",
                            agent_run_id=run_id,
                        )
                        raise
                    set_span_result(
                        provider_span,
                        {
                            "byte_size": len(generated.content),
                            "duration_ms": generated.duration_ms,
                            "provider_request_id": generated.provider_request_id,
                        },
                    )
                    set_span_outputs(
                        provider_span,
                        {
                            "response_format": generated.response_format,
                            "sample_rate": generated.sample_rate,
                            "duration_ms": generated.duration_ms,
                        },
                    )
                    set_span_status(
                        provider_span,
                        "OK",
                        agent_run_id=run_id,
                    )
                completed = store.complete_speech_tool(
                    prepared.id,
                    text=cleaned_text,
                    generated=generated,
                    resource_id=settings.doubao_voice_gen_resource_id.strip(),
                    model=settings.doubao_voice_gen_model.strip(),
                    speaker=settings.doubao_voice_gen_speaker.strip(),
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
                set_span_status(tool_span, "ERROR", agent_run_id=run_id)
                raise
            latency_ms = round((time.perf_counter() - started) * 1000)
            set_span_result(
                tool_span,
                {
                    "result_status": "succeeded",
                    "latency_ms": latency_ms,
                    "byte_size": completed.byte_size,
                    "duration_ms": completed.duration_ms,
                    "provider_request_id": completed.provider_request_id,
                },
            )
            set_span_outputs(
                tool_span,
                {
                    "status": "succeeded",
                    "audio_id": completed.audio_id,
                    "asset_id": completed.asset_id,
                },
            )
            set_span_status(tool_span, "OK", agent_run_id=run_id)
            return _speech_tool_outputs(completed)

    return function_tool(
        generate_speech,
        name_override="generate_speech",
        description_override=_speech_tool_description(settings),
    )


def _speech_tool_outputs(completed: CompletedNativeSpeech) -> list[ToolOutputText]:
    return [
        ToolOutputText(
            text=json.dumps(
                {
                    "status": "succeeded",
                    "audio_id": completed.audio_id,
                    "asset_id": completed.asset_id,
                    "content_type": completed.content_type,
                    "byte_size": completed.byte_size,
                    "response_format": completed.response_format,
                    "sample_rate": completed.sample_rate,
                    "duration_ms": completed.duration_ms,
                },
                ensure_ascii=False,
            )
        )
    ]


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
    allowed_tools = set(parse_tool_names(run.skill_version.tool_names_json))
    image_generation_context = json.dumps(
        {
            "style_name": run.style_name_snapshot,
            "aspect_ratio": run.aspect_ratio_snapshot,
            "style_prompt": run.style_prompt_snapshot,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    instructions = (
        f"{NATIVE_AGENT_BASE_INSTRUCTIONS}\n\n"
        f"<skill name={json.dumps(run.skill_name_snapshot, ensure_ascii=False)} "
        f"version={run.skill_version_snapshot}>\n"
        f"{run.skill_version.instructions}\n"
        "</skill>"
    )
    if "generate_image" in allowed_tools:
        instructions += (
            "\n\n<image_generation_context>\n"
            "以下 Style 只用于规划图片、编写 generate_image prompt 和 Review 图片，不得改变故事事实、"
            "旁白或对白。每次调用 generate_image 时，必须把适用于该画面的视觉规则和比例写入完整 "
            "prompt；Runtime 不会代为拼接。\n"
            f"{image_generation_context}\n"
            "</image_generation_context>"
        )
    return instructions


async def execute_native_agent_run(
    run_id: str,
    *,
    settings: Settings | None = None,
    image_generator: ImageGenerator = generate_xg_image,
    speech_generator: SpeechGenerator | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    resolved_speech_generator = speech_generator or (
        lambda *, text: generate_volcengine_speech(
            text=text,
            settings=resolved_settings,
        )
    )
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
        exposed_tool_names = native_runtime_tool_names(
            run.skill_version.tool_names_json
        )
        instructions = native_agent_instructions(run)
        trace_context = {
            "conversation_id": run.conversation_id,
            "skill_version_id": run.skill_version_id,
            "style_id": run.style_id,
        }
    resumed = await sdk_session.has_items()
    store.start_run(resumed=resumed)

    tools: list[FunctionTool] = []
    if "generate_image" in exposed_tool_names:
        tools.append(
            build_generate_image_tool(
                context,
                image_generator=image_generator,
                store=store,
            )
        )
    if "generate_speech" in exposed_tool_names:
        tools.append(
            build_generate_speech_tool(
                run_id,
                settings=resolved_settings,
                speech_generator=resolved_speech_generator,
                store=store,
            )
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
                tools=tools,
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
                    "tool_count": len(tools),
                    "max_function_tool_concurrency": MAX_NATIVE_AGENT_TOOL_CONCURRENCY,
                },
            ) as model_span:
                set_span_inputs(
                    model_span,
                    {
                        "user_content": user_content,
                        "instructions": instructions,
                        "tools": exposed_tool_names,
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
                                max_function_tool_concurrency=MAX_NATIVE_AGENT_TOOL_CONCURRENCY,
                            ),
                        ),
                        max_turns=MAX_NATIVE_AGENT_TURNS,
                        session=sdk_session,
                    )
                    text_delta_buffer = ""
                    last_delta_flush = time.monotonic()
                    current_response_id: str | None = None
                    function_argument_buffers: dict[str, str] = {}
                    function_argument_last_flush: dict[str, float] = {}
                    function_call_metadata: dict[str, dict[str, object]] = {}

                    def flush_text_delta() -> None:
                        nonlocal text_delta_buffer, last_delta_flush
                        if not text_delta_buffer or current_response_id is None:
                            return
                        store.append_response_text_delta(
                            current_response_id,
                            text_delta_buffer,
                        )
                        text_delta_buffer = ""
                        last_delta_flush = time.monotonic()

                    def flush_function_arguments(item_id: str) -> None:
                        delta = function_argument_buffers.get(item_id, "")
                        if not delta or current_response_id is None:
                            return
                        metadata = function_call_metadata.get(item_id, {})
                        store.append_function_call_arguments_delta(
                            response_id=current_response_id,
                            item_id=item_id,
                            tool_call_id=str(metadata.get("tool_call_id") or ""),
                            name=str(metadata.get("name") or ""),
                            delta=delta,
                        )
                        function_argument_buffers[item_id] = ""
                        function_argument_last_flush[item_id] = time.monotonic()

                    async for event in result.stream_events():
                        if event.type != "raw_response_event":
                            continue
                        raw_event = event.data
                        raw_type = getattr(raw_event, "type", "")
                        if raw_type == "response.created":
                            current_response_id = raw_event.response.id
                            store.start_model_step(current_response_id)
                        elif raw_type == "response.output_text.delta":
                            text_delta_buffer += raw_event.delta
                            now = time.monotonic()
                            if (
                                len(text_delta_buffer) >= 80
                                or now - last_delta_flush >= 0.25
                            ):
                                flush_text_delta()
                        elif raw_type == "response.output_item.added":
                            item = raw_event.item
                            if getattr(item, "type", "") != "function_call":
                                continue
                            item_id = str(item.id)
                            metadata = {
                                "tool_call_id": str(item.call_id),
                                "name": str(item.name),
                                "output_index": int(raw_event.output_index),
                            }
                            function_call_metadata[item_id] = metadata
                            function_argument_buffers[item_id] = ""
                            function_argument_last_flush[item_id] = time.monotonic()
                            store.start_function_call(
                                response_id=current_response_id or "",
                                item_id=item_id,
                                tool_call_id=str(metadata["tool_call_id"]),
                                name=str(metadata["name"]),
                                output_index=int(metadata["output_index"]),
                            )
                        elif raw_type == "response.function_call_arguments.delta":
                            item_id = str(raw_event.item_id)
                            function_argument_buffers[item_id] = (
                                function_argument_buffers.get(item_id, "")
                                + raw_event.delta
                            )
                            now = time.monotonic()
                            if (
                                len(function_argument_buffers[item_id]) >= 80
                                or now
                                - function_argument_last_flush.get(item_id, now)
                                >= 0.25
                            ):
                                flush_function_arguments(item_id)
                        elif raw_type == "response.function_call_arguments.done":
                            item_id = str(raw_event.item_id)
                            flush_function_arguments(item_id)
                            metadata = function_call_metadata.get(item_id, {})
                            store.complete_function_call_arguments(
                                response_id=current_response_id or "",
                                item_id=item_id,
                                tool_call_id=str(metadata.get("tool_call_id") or ""),
                                name=str(
                                    getattr(raw_event, "name", None)
                                    or metadata.get("name")
                                    or ""
                                ),
                                arguments=str(raw_event.arguments),
                            )
                        elif raw_type == "response.completed":
                            flush_text_delta()
                            for item_id in tuple(function_argument_buffers):
                                flush_function_arguments(item_id)
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
                    flush_text_delta()
                    for item_id in tuple(function_argument_buffers):
                        flush_function_arguments(item_id)
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
                speech_call_count = run.speech_call_count
            set_native_agent_run_trace_status(
                root_span,
                native_agent_run_id=run_id,
                run_status=AgentRunStatus.succeeded.value,
                model_call_count=model_call_count,
                image_call_count=image_call_count,
                speech_call_count=speech_call_count,
                error_code=None,
            )
        except Exception as exc:
            store.fail_run(exc)
            with SessionLocal() as db:
                run = db.get(NativeAgentRun, run_id)
                model_call_count = run.model_call_count if run is not None else 0
                image_call_count = run.image_call_count if run is not None else 0
                speech_call_count = run.speech_call_count if run is not None else 0
            set_native_agent_run_trace_status(
                root_span,
                native_agent_run_id=run_id,
                run_status=AgentRunStatus.failed.value,
                model_call_count=model_call_count,
                image_call_count=image_call_count,
                speech_call_count=speech_call_count,
                error_code=type(exc).__name__,
            )
        finally:
            await client.close()
