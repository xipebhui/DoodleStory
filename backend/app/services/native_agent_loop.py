from __future__ import annotations

import asyncio
import base64
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Callable, Literal
from urllib.parse import urlsplit
from uuid import uuid4

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
from agents.lifecycle import AgentHooksBase
from agents.model_settings import ModelRetrySettings
from agents.models.openai_provider import OpenAIProvider
from agents.tool_context import ToolContext
from agents.usage import serialize_usage
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models.entities import (
    AudioReference,
    FileAsset,
    GeneratedImage,
    NativeAgentAudio,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    NativeAgentSubtitle,
    NativeAgentConversation,
)
from app.models.enums import (
    AgentRunStatus,
    GeneratedImageStatus,
    NativeAgentItemType,
    NativeAgentStepStatus,
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
from app.services.account_creation_context import (
    AccountCreationContextError,
    get_account_creation_context,
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
    CompletedNativeImageInspection,
    CompletedNativeSubtitle,
    CompletedNativeExternalContent,
    CompletedNativeTool,
    CompletedNativeVideo,
    NativeAgentDatabaseSession,
    NativeAgentStore,
)
from app.services.native_article_workflow import (
    ARTICLE_DRAFT,
    ARTICLE_REVIEW,
    TOPIC_CANDIDATES,
    has_pending_article_approval,
    load_compiled_workflow_plan,
    request_article_artifact_approval,
    request_final_article_approval,
    save_article_artifact,
    save_compiled_workflow_plan,
)
from app.services.agent_vision import InspectionResult, inspect_image_asset
from app.services.social_content_import import (
    SocialContentImportResult,
    import_social_content,
)
from app.services.remotion_video import (
    GeneratedRemotionVideo,
    RemotionCaption,
    RemotionScene,
    render_remotion_video,
)
from app.services.storage import materialize_asset_to_local
from app.services.volcengine_speech import (
    GeneratedSpeech,
    SpeechSpeed,
    VolcengineSpeechClient,
    speech_rate_for_speed,
)
from app.services.whisper_subtitles import GeneratedSubtitles, generate_whisper_subtitles
from app.services.youtube_publishing import (
    YoutubePublishCommand,
    create_youtube_publish_task,
)
from app.services.youtube_publisher import YoutubePublisherClient
from app.services.youtube_channel_insights import (
    YoutubeChannelInsightsResult,
    YoutubeCommentOrder,
    fetch_youtube_channel_insights,
)


MAX_NATIVE_AGENT_TURNS = 12
MAX_NATIVE_AGENT_TOOL_CONCURRENCY = 2
NATIVE_AGENT_BASE_INSTRUCTIONS = """
你是专注于内容创作的agent, 主要的工作是根据用户输入提示，生成图片，或者文本图片配音的视频。

严格按照本次 Run 固定的 Skill 工作。Runtime 只负责 Agent Loop 和真实 Tool 执行；故事改写、
分镜切割、图片 Prompt、图片 Review、视频生成、语音生成、字幕是否修改重画都由你依据 Skill 和用户目标决定。

""".strip()
ARTICLE_WORKFLOW_COMPILER_INSTRUCTIONS = """
你是 DoodleStory 的文案工作流编译器。你的唯一工作是把一个完整 Skill 编译成可执行的结构化计划，
不能执行创作任务，也不能直接写文章。

运行时固定提供 Director、Writer、Reviewer 三个角色，以及 write_article、review_article、
submit_final_article 三个工具。你需要理解 Skill 中的总体策略、角色职责、协作步骤和质量门槛，
然后：
1. 为每个角色生成只包含该角色职责的局部 instructions，不得把其他角色的完整规则复制进去；
2. 把跨角色共同遵守的约束放入 shared_constraints；
3. 把 Director 的工具调用顺序、分支条件和完成条件编译到 execution_steps；
4. 保留 Skill 的真实语义，不得自行增加 Skill 未声明的创作规则、角色或工具；
5. 输出必须能让 Director 调用 Writer 和 Reviewer，并通过 submit_final_article 进入用户审批。
""".strip()


class NativeAgentLoopError(RuntimeError):
    pass


class NativeImageInspectionExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_beat: str | None = Field(default=None, max_length=4_000)
    characters: list[str] = Field(default_factory=list, max_length=20)
    required_text: list[str] = Field(default_factory=list, max_length=50)


@dataclass(frozen=True)
class NativeImageToolContext:
    run_id: str
    image_model: str | None
    aspect_ratio: str | None
    reference_urls: tuple[str, ...]


ImageGenerator = Callable[..., GeneratedImageFile]
SpeechGenerator = Callable[..., GeneratedSpeech]
SubtitleGenerator = Callable[..., GeneratedSubtitles]
VideoRenderer = Callable[..., GeneratedRemotionVideo]
ImageInspector = Callable[..., tuple[InspectionResult, str, str, int]]
SocialContentImporter = Callable[[str], SocialContentImportResult]
YoutubeInsightsFetcher = Callable[..., YoutubeChannelInsightsResult]
NATIVE_RUNTIME_TOOL_NAMES = frozenset(
    {
        "generate_image",
        "inspect_image",
        "generate_speech",
        "generate_subtitles",
        "render_story_video",
        "publish_youtube_video",
        "capture_wechat_article",
        "get_account_creation_context",
        "inspect_youtube_channel",
        "write_article",
        "review_article",
        "submit_final_article",
    }
)

WECHAT_ARTICLE_HOST = "mp.weixin.qq.com"
WECHAT_ARTICLE_EXCERPT_MAX_CHARS = 1600


class NativeVideoSceneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str = Field(min_length=1, max_length=32)
    audio_id: str = Field(min_length=1, max_length=32)
    subtitle: str | None = Field(default=None, min_length=1, max_length=500)
    subtitle_id: str | None = Field(default=None, min_length=1, max_length=32)
    motion_preset: Literal[
        "static",
        "zoom_in",
        "zoom_out",
        "pan_left",
        "pan_right",
        "pan_up",
        "pan_down",
    ]

    @model_validator(mode="after")
    def validate_subtitle_source(self) -> "NativeVideoSceneInput":
        if (self.subtitle is None) == (self.subtitle_id is None):
            raise ValueError("subtitle 和 subtitle_id 必须且只能提供一个")
        return self


class ArticleDraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = Field(min_length=1, max_length=30_000)
    creative_summary: str = Field(min_length=1, max_length=1000)
    hook: str = Field(min_length=1, max_length=1000)


class ArticleReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["approved", "changes_required"]
    summary: str = Field(min_length=1, max_length=2000)
    strengths: list[str] = Field(max_length=10)
    issues: list[str] = Field(max_length=10)


class CompiledArticleRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["director", "writer", "reviewer"]
    mission: str = Field(min_length=1, max_length=1000)
    instructions: list[str] = Field(min_length=1, max_length=20)


class CompiledArticleWorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1, le=20)
    tool_name: Literal[
        "write_article",
        "review_article",
        "submit_final_article",
    ]
    objective: str = Field(min_length=1, max_length=1000)
    required_inputs: list[str] = Field(min_length=1, max_length=20)
    completion_condition: str = Field(min_length=1, max_length=1000)
    branch_condition: str | None = Field(default=None, max_length=1000)


class CompiledArticleWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_summary: str = Field(min_length=1, max_length=2000)
    shared_constraints: list[str] = Field(min_length=1, max_length=20)
    roles: list[CompiledArticleRole] = Field(min_length=3, max_length=3)
    execution_steps: list[CompiledArticleWorkflowStep] = Field(
        min_length=3,
        max_length=20,
    )
    quality_gates: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_executable_topology(self) -> "CompiledArticleWorkflow":
        role_names = [role.name for role in self.roles]
        if set(role_names) != {"director", "writer", "reviewer"}:
            raise ValueError("编译计划必须且只能包含 Director、Writer、Reviewer")
        if len(role_names) != len(set(role_names)):
            raise ValueError("编译计划角色不能重复")
        sequences = [step.sequence for step in self.execution_steps]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("编译计划步骤 sequence 必须严格递增且不能重复")
        tools = {step.tool_name for step in self.execution_steps}
        required_tools = {
            "write_article",
            "review_article",
            "submit_final_article",
        }
        if tools != required_tools:
            raise ValueError("编译计划必须覆盖 Writer、Reviewer 与最终审批工具")
        return self

    def role(self, name: Literal["director", "writer", "reviewer"]) -> CompiledArticleRole:
        return next(role for role in self.roles if role.name == name)


class NativeModelMetricHooks(AgentHooksBase):
    def __init__(self, store: NativeAgentStore, *, phase: str) -> None:
        self._store = store
        self._phase = phase
        self._active_calls: dict[str, deque[str]] = {}
        self.started_count = 0
        self.completed_count = 0
        self.role_counts: dict[str, int] = {}

    @staticmethod
    def _role_name(agent: Agent) -> str:
        mapping = {
            "DoodleStoryArticleWorkflowCompiler": "workflow_compiler",
            "DoodleStoryArticleDirector": "director",
            "DoodleStoryArticleWriter": "writer",
            "DoodleStoryArticleReviewer": "reviewer",
        }
        return mapping.get(agent.name, "main_agent")

    async def on_llm_start(
        self,
        context,
        agent: Agent,
        system_prompt: str | None,
        input_items: list[object],
    ) -> None:
        del context, system_prompt, input_items
        role = self._role_name(agent)
        metric_call_id = uuid4().hex
        self._active_calls.setdefault(role, deque()).append(metric_call_id)
        self.started_count += 1
        self.role_counts[role] = self.role_counts.get(role, 0) + 1
        self._store.record_model_request_started(
            metric_call_id=metric_call_id,
            role=role,
            phase=self._phase,
        )

    async def on_llm_end(self, context, agent: Agent, response) -> None:
        del context
        role = self._role_name(agent)
        role_calls = self._active_calls.get(role)
        if not role_calls:
            raise NativeAgentLoopError("模型调用完成事件缺少开始记录")
        metric_call_id = role_calls.popleft()
        if not role_calls:
            self._active_calls.pop(role, None)
        response_usage = getattr(response, "usage", None)
        usage = serialize_usage(response_usage) if response_usage is not None else None
        self.completed_count += 1
        self._store.record_model_request_completed(
            metric_call_id=metric_call_id,
            role=role,
            phase=self._phase,
            usage=usage,
        )


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
        "每次调用只处理 text 原文，不会改写、拆分或拼接文本；speed 只允许 "
        "0.5、0.75、1.0、1.25、1.5、2.0。"
        f"语音模型固定为 {settings.doubao_voice_gen_model.strip()}，"
        f"音色固定为 {settings.doubao_voice_gen_speaker.strip()}。"
        "工具返回音频资产元数据；不要声称已经听取或审核音频内容。"
    )


def generate_volcengine_speech(
    *,
    text: str,
    speed: SpeechSpeed = 1.0,
    settings: Settings | None = None,
) -> GeneratedSpeech:
    return VolcengineSpeechClient(settings=settings).generate_speech(
        text=text,
        speed=speed,
    )


def _video_tool_description() -> str:
    return (
        "使用固定 narrated-panel-v1 Remotion 模板，把图片和当前 Run 已生成的旁白音频"
        "按 scenes 顺序渲染为跟随首张图片比例、30fps 的 MP4。image_id 可以是当前 Run "
        "所在会话的 Native 图片 ID，也可以是当前用户已有任务中成功且 current 的图片 ID；每个 "
        "scene 还必须提供当前 Run 的 audio_id、subtitle 或对应音频的 subtitle_id（二选一）"
        "和一个 motion_preset；可选 "
        "bgm_asset_id。"
        "允许的 motion_preset 只有 static、zoom_in、zoom_out、pan_left、pan_right、"
        "pan_up、pan_down。Scene 时长严格使用对应语音的真实 duration_ms；不要编造 ID、"
        "时间、URL、React/CSS 或渲染参数。"
    )


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


def build_inspect_image_tool(
    run_id: str,
    *,
    store: NativeAgentStore,
    image_inspector: ImageInspector = inspect_image_asset,
) -> FunctionTool:
    async def inspect_image(
        tool_context: ToolContext[None],
        image_id: str,
        checks: list[str],
        expected: NativeImageInspectionExpected,
    ) -> list[ToolOutputText]:
        normalized_checks = [item.strip() for item in checks if item.strip()]
        if not normalized_checks or len(normalized_checks) > 10:
            raise NativeAgentLoopError("inspect_image checks 必须包含 1 到 10 项")
        if len(normalized_checks) != len(set(normalized_checks)):
            raise NativeAgentLoopError("inspect_image checks 不能重复")
        expected_data = expected.model_dump(mode="json")
        prepared = store.prepare_image_inspection_tool(
            tool_call_id=tool_context.tool_call_id,
            image_id=image_id,
            checks=normalized_checks,
            expected=expected_data,
        )
        if isinstance(prepared, CompletedNativeImageInspection):
            completed = prepared
        else:
            store.start_tool(prepared.id)
            try:
                with SessionLocal() as db:
                    image = db.scalar(
                        select(NativeAgentImage)
                        .where(
                            NativeAgentImage.id == image_id,
                            NativeAgentImage.run_id == run_id,
                        )
                        .options(selectinload(NativeAgentImage.asset))
                    )
                    if image is None:
                        raise NativeAgentLoopError("image_id 不属于当前 Run")
                    result, provider, model, latency_ms = await asyncio.to_thread(
                        image_inspector,
                        image.asset,
                        checks=normalized_checks,
                        expected=expected_data,
                    )
                completed = store.complete_image_inspection_tool(
                    prepared.id,
                    image_id=image_id,
                    verdict=result.verdict,
                    scores=result.scores,
                    issues=[issue.model_dump(mode="json") for issue in result.issues],
                    provider=provider,
                    model=model,
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                store.fail_tool(prepared.id, exc)
                raise
        return [
            ToolOutputText(
                text=json.dumps(
                    {
                        "status": "succeeded",
                        "image_id": completed.image_id,
                        "verdict": completed.verdict,
                        "scores": completed.scores,
                        "issues": completed.issues,
                        "provider": completed.provider,
                        "model": completed.model,
                        "latency_ms": completed.latency_ms,
                    },
                    ensure_ascii=False,
                )
            )
        ]

    return function_tool(
        inspect_image,
        name_override="inspect_image",
        description_override=(
            "对当前 Run 的 image_id 执行一次真实视觉质量检查。checks 列出要检查的维度，"
            "expected 描述预期画面；返回 accept、revise、ask_user 或 blocked。"
            "只有 verdict=accept 的图片才能进入视频渲染。"
        ),
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
        speed: SpeechSpeed = 1.0,
    ) -> list[ToolOutputText]:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise NativeAgentLoopError("generate_speech text 不能为空")
        prepared = store.prepare_speech_tool(
            tool_call_id=tool_context.tool_call_id,
            text=cleaned_text,
            speed=speed,
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
            set_span_inputs(tool_span, {"text": cleaned_text, "speed": speed})
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
                    set_span_inputs(provider_span, {"text": cleaned_text, "speed": speed})
                    try:
                        generated = await asyncio.to_thread(
                            speech_generator,
                            text=cleaned_text,
                            speed=speed,
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
                    speed=speed,
                    speech_rate=speech_rate_for_speed(speed),
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
                    "speed": completed.speed,
                    "speech_rate": completed.speech_rate,
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
                    "speed": completed.speed,
                    "speech_rate": completed.speech_rate,
                },
                ensure_ascii=False,
            )
        )
    ]


def build_generate_subtitles_tool(
    run_id: str,
    *,
    settings: Settings,
    subtitle_generator: SubtitleGenerator,
    store: NativeAgentStore,
) -> FunctionTool:
    async def generate_subtitles(
        tool_context: ToolContext[None],
        audio_id: str,
    ) -> list[ToolOutputText]:
        prepared = store.prepare_subtitle_tool(
            tool_call_id=tool_context.tool_call_id,
            audio_id=audio_id,
        )
        if isinstance(prepared, CompletedNativeSubtitle):
            return _subtitle_tool_outputs(prepared)
        store.start_tool(prepared.id)
        try:
            with SessionLocal() as db:
                audio = db.scalar(
                    select(NativeAgentAudio)
                    .where(
                        NativeAgentAudio.id == audio_id,
                        NativeAgentAudio.run_id == run_id,
                    )
                    .options(selectinload(NativeAgentAudio.asset))
                )
                if audio is None:
                    raise NativeAgentLoopError("audio_id 不属于当前 Run")
                if audio.duration_ms is None or audio.duration_ms <= 0:
                    raise NativeAgentLoopError("音频缺少真实 duration_ms")
                audio_path = materialize_asset_to_local(audio.asset)
                duration_ms = audio.duration_ms
                reference_text = audio.text
            generated = await asyncio.to_thread(
                subtitle_generator,
                audio_path=audio_path,
                duration_ms=duration_ms,
                reference_text=reference_text,
                settings=settings,
            )
            completed = store.complete_subtitle_tool(
                prepared.id,
                audio_id=audio_id,
                generated=generated,
            )
        except Exception as exc:
            store.fail_tool(prepared.id, exc)
            raise
        return _subtitle_tool_outputs(completed)

    return function_tool(
        generate_subtitles,
        name_override="generate_subtitles",
        description_override=(
            "使用当前 audio_id 保存的语音生成原文校准字幕文字，并使用本地 OpenAI "
            "Whisper 提取真实时间轴，生成 WebVTT 字幕资产；返回 subtitle_id、字幕 "
            "asset_id、语言、模型、时长和 cue 数量。"
        ),
    )


def _subtitle_tool_outputs(
    completed: CompletedNativeSubtitle,
) -> list[ToolOutputText]:
    return [
        ToolOutputText(
            text=json.dumps(
                {
                    "status": "succeeded",
                    "subtitle_id": completed.subtitle_id,
                    "audio_id": completed.audio_id,
                    "asset_id": completed.asset_id,
                    "content_type": completed.content_type,
                    "byte_size": completed.byte_size,
                    "cue_count": len(completed.cues),
                    "duration_ms": completed.duration_ms,
                    "language": completed.language,
                    "model": completed.model,
                },
                ensure_ascii=False,
            )
        )
    ]


def _resolve_video_inputs(
    run_id: str,
    *,
    scenes: list[NativeVideoSceneInput],
    bgm_asset_id: str | None,
) -> tuple[list[RemotionScene], list[dict[str, object]], Path | None]:
    with SessionLocal() as db:
        run = db.scalar(
            select(NativeAgentRun)
            .where(NativeAgentRun.id == run_id)
            .options(
                selectinload(NativeAgentRun.conversation),
                selectinload(NativeAgentRun.skill_version),
            )
        )
        if run is None:
            raise NativeAgentLoopError("Native Agent Run 不存在")
        requires_image_inspection = "inspect_image" in parse_tool_names(
            run.skill_version.tool_names_json
        )
        accepted_inspection_image_ids: set[str] = set()
        if requires_image_inspection:
            inspection_steps = db.scalars(
                select(NativeAgentStep).where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.name == "inspect_image",
                    NativeAgentStep.status == NativeAgentStepStatus.succeeded,
                )
            ).all()
            for inspection_step in inspection_steps:
                inspection = json.loads(inspection_step.output_ref_json or "{}")
                if inspection.get("verdict") == "accept" and inspection.get("image_id"):
                    accepted_inspection_image_ids.add(str(inspection["image_id"]))
        image_ids = [scene.image_id for scene in scenes]
        audio_ids = [scene.audio_id for scene in scenes]
        images = {
            image.id: image
            for image in db.scalars(
                select(NativeAgentImage)
                .join(
                    NativeAgentRun,
                    NativeAgentRun.id == NativeAgentImage.run_id,
                )
                .where(
                    NativeAgentRun.conversation_id == run.conversation_id,
                    NativeAgentImage.id.in_(image_ids),
                )
                .options(selectinload(NativeAgentImage.asset))
            ).all()
        }
        task_images = {
            image.id: image
            for image in db.scalars(
                select(GeneratedImage)
                .where(
                    GeneratedImage.id.in_(image_ids),
                    GeneratedImage.status
                    == GeneratedImageStatus.succeeded,
                    GeneratedImage.is_current.is_(True),
                    GeneratedImage.asset_id.is_not(None),
                    GeneratedImage.task.has(
                        owner_user_id=run.conversation.owner_user_id
                    ),
                )
                .options(selectinload(GeneratedImage.asset))
            ).all()
        }
        audios = {
            audio.id: audio
            for audio in db.scalars(
                select(NativeAgentAudio)
                .where(
                    NativeAgentAudio.run_id == run_id,
                    NativeAgentAudio.id.in_(audio_ids),
                )
                .options(selectinload(NativeAgentAudio.asset))
            ).all()
        }
        subtitle_ids = [
            scene.subtitle_id for scene in scenes if scene.subtitle_id is not None
        ]
        subtitles = {
            subtitle.id: subtitle
            for subtitle in db.scalars(
                select(NativeAgentSubtitle).where(
                    NativeAgentSubtitle.run_id == run_id,
                    NativeAgentSubtitle.id.in_(subtitle_ids),
                )
            ).all()
        }
        resolved: list[RemotionScene] = []
        snapshots: list[dict[str, object]] = []
        for index, scene in enumerate(scenes, start=1):
            native_image = images.get(scene.image_id)
            task_image = task_images.get(scene.image_id)
            image_asset = (
                native_image.asset
                if native_image is not None
                else task_image.asset
                if task_image is not None
                else None
            )
            audio = audios.get(scene.audio_id)
            if image_asset is None:
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的 image_id 不是当前 Run 图片，"
                    "也不是当前用户任务的成功 current 图片"
                )
            if (
                requires_image_inspection
                and scene.image_id not in accepted_inspection_image_ids
            ):
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的图片尚未通过 inspect_image；"
                    "必须先获得 verdict=accept"
                )
            if audio is None:
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的 audio_id 不属于当前 Run"
                )
            if audio.duration_ms is None or audio.duration_ms <= 0:
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的音频缺少真实 duration_ms"
                )
            if image_asset.width is None or image_asset.height is None:
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的图片缺少真实宽高"
                )
            subtitle = scene.subtitle.strip() if scene.subtitle else None
            subtitle_record = (
                subtitles.get(scene.subtitle_id) if scene.subtitle_id else None
            )
            if scene.subtitle_id and subtitle_record is None:
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的 subtitle_id 不属于当前 Run"
                )
            if subtitle_record is not None and subtitle_record.audio_id != audio.id:
                raise NativeAgentLoopError(
                    f"第 {index} 个 Scene 的字幕不属于对应 audio_id"
                )
            cues = tuple(
                RemotionCaption(
                    start_ms=int(cue["start_ms"]),
                    end_ms=int(cue["end_ms"]),
                    text=str(cue["text"]),
                )
                for cue in (
                    json.loads(subtitle_record.cues_json)
                    if subtitle_record is not None
                    else []
                )
            )
            resolved.append(
                RemotionScene(
                    scene_id=f"{index:03d}",
                    image_path=materialize_asset_to_local(image_asset),
                    audio_path=materialize_asset_to_local(audio.asset),
                    subtitle=subtitle,
                    captions=cues,
                    duration_ms=audio.duration_ms,
                    motion_preset=scene.motion_preset,
                    image_width=image_asset.width,
                    image_height=image_asset.height,
                )
            )
            snapshots.append(
                {
                    "scene_order": index,
                    "image_id": scene.image_id,
                    "image_source": (
                        "current_native_run"
                        if native_image is not None
                        and native_image.run_id == run_id
                        else "conversation_native_run"
                        if native_image is not None
                        else "generation_task"
                    ),
                    "image_asset_id": image_asset.id,
                    "audio_id": audio.id,
                    "audio_asset_id": audio.asset_id,
                    "subtitle": subtitle,
                    "subtitle_id": (
                        subtitle_record.id if subtitle_record is not None else None
                    ),
                    "subtitle_asset_id": (
                        subtitle_record.asset_id
                        if subtitle_record is not None
                        else None
                    ),
                    "duration_ms": audio.duration_ms,
                    "motion_preset": scene.motion_preset,
                }
            )
        bgm_path = None
        if bgm_asset_id:
            bgm_asset = db.get(FileAsset, bgm_asset_id)
            if bgm_asset is None or not bgm_asset.content_type.startswith("audio/"):
                raise NativeAgentLoopError("BGM 资产不存在或不是音频")
            native_bgm = db.scalar(
                select(NativeAgentAudio)
                .join(
                    NativeAgentRun,
                    NativeAgentRun.id == NativeAgentAudio.run_id,
                )
                .where(
                    NativeAgentAudio.asset_id == bgm_asset.id,
                    NativeAgentRun.conversation_id == run.conversation_id,
                )
            )
            reference_bgm = db.scalar(
                select(AudioReference).where(
                    AudioReference.asset_id == bgm_asset.id,
                    AudioReference.owner_user_id
                    == run.conversation.owner_user_id,
                    AudioReference.deleted_at.is_(None),
                )
            )
            if native_bgm is None and reference_bgm is None:
                raise NativeAgentLoopError("当前会话无权使用该 BGM 资产")
            bgm_path = materialize_asset_to_local(bgm_asset)
        return resolved, snapshots, bgm_path


def build_render_story_video_tool(
    run_id: str,
    *,
    settings: Settings,
    video_renderer: VideoRenderer,
    store: NativeAgentStore,
) -> FunctionTool:
    async def render_story_video(
        tool_context: ToolContext[None],
        scenes: list[NativeVideoSceneInput],
        bgm_asset_id: str | None = None,
    ) -> list[ToolOutputText]:
        if not scenes:
            raise NativeAgentLoopError(
                "render_story_video 至少需要一个 Scene"
            )
        if len(scenes) > 30:
            raise NativeAgentLoopError(
                "render_story_video 最多支持 30 个 Scene"
            )
        scene_arguments = [
            scene.model_dump(mode="json")
            for scene in scenes
        ]
        prepared = store.prepare_video_tool(
            tool_call_id=tool_context.tool_call_id,
            scenes=scene_arguments,
            bgm_asset_id=bgm_asset_id,
        )
        if isinstance(prepared, CompletedNativeVideo):
            store.append_event(
                "tool.reused",
                {
                    "tool": "render_story_video",
                    "tool_call_id": tool_context.tool_call_id,
                    "step_id": prepared.step_id,
                    "video_id": prepared.video_id,
                },
            )
            return _video_tool_outputs(prepared)
        store.start_tool(prepared.id)
        with agent_span(
            "native_agent.render_story_video",
            agent_run_id=run_id,
            span_type="TOOL",
            attributes={
                "tool_name": "render_story_video",
                "template_id": "narrated-panel-v1",
                "scene_count": len(scenes),
                "has_bgm": bgm_asset_id is not None,
            },
        ) as tool_span:
            set_span_inputs(
                tool_span,
                {
                    "scenes": scene_arguments,
                    "bgm_asset_id": bgm_asset_id,
                },
            )
            started = time.perf_counter()
            try:
                resolved_scenes, snapshots, bgm_path = await asyncio.to_thread(
                    _resolve_video_inputs,
                    run_id,
                    scenes=scenes,
                    bgm_asset_id=bgm_asset_id,
                )
                with agent_span(
                    "native_agent.remotion_renderer",
                    agent_run_id=run_id,
                    span_type="TASK",
                    attributes={
                        "template_id": "narrated-panel-v1",
                        "scene_count": len(scenes),
                        "has_bgm": bgm_asset_id is not None,
                    },
                ) as provider_span:
                    set_span_inputs(
                        provider_span,
                        {
                            "scene_count": len(scenes),
                            "has_bgm": bgm_asset_id is not None,
                        },
                    )
                    try:
                        generated = await asyncio.to_thread(
                            video_renderer,
                            scenes=resolved_scenes,
                            bgm_path=bgm_path,
                            settings=settings,
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
                            "renderer_version": generated.renderer_version,
                        },
                    )
                    set_span_outputs(
                        provider_span,
                        {
                            "fps": generated.fps,
                            "width": generated.width,
                            "height": generated.height,
                        },
                    )
                    set_span_status(
                        provider_span,
                        "OK",
                        agent_run_id=run_id,
                    )
                completed = store.complete_video_tool(
                    prepared.id,
                    scenes=snapshots,
                    bgm_asset_id=bgm_asset_id,
                    generated=generated,
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
                },
            )
            set_span_outputs(
                tool_span,
                {
                    "status": "succeeded",
                    "video_id": completed.video_id,
                    "asset_id": completed.asset_id,
                },
            )
            set_span_status(tool_span, "OK", agent_run_id=run_id)
            return _video_tool_outputs(completed)

    return function_tool(
        render_story_video,
        name_override="render_story_video",
        description_override=_video_tool_description(),
    )


def _video_tool_outputs(
    completed: CompletedNativeVideo,
) -> list[ToolOutputText]:
    return [
        ToolOutputText(
            text=json.dumps(
                {
                    "status": "succeeded",
                    "video_id": completed.video_id,
                    "asset_id": completed.asset_id,
                    "template_id": completed.template_id,
                    "duration_ms": completed.duration_ms,
                    "fps": completed.fps,
                    "width": completed.width,
                    "height": completed.height,
                },
                ensure_ascii=False,
            )
        )
    ]


def _normalize_wechat_article_url(url: str) -> str:
    normalized = url.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != WECHAT_ARTICLE_HOST:
        raise NativeAgentLoopError(
            "capture_wechat_article 只接受 https://mp.weixin.qq.com/ 文章链接"
        )
    return normalized


def _read_wechat_markdown(result: SocialContentImportResult) -> bytes:
    if result.platform != "wechat":
        raise NativeAgentLoopError(
            f"素材导入服务返回平台 {result.platform!r}，预期为 'wechat'"
        )
    output_dir = result.output_dir.expanduser().resolve()
    markdown_candidates = [
        path.expanduser().resolve()
        for path in result.metadata_files
        if path.name == "content.md"
    ]
    if len(markdown_candidates) != 1:
        raise NativeAgentLoopError(
            "微信公众号抓取结果必须包含且只能包含一个 content.md"
        )
    markdown_path = markdown_candidates[0]
    try:
        markdown_path.relative_to(output_dir)
    except ValueError as exc:
        raise NativeAgentLoopError(
            "微信公众号抓取结果的 content.md 不在导入输出目录内"
        ) from exc
    if not markdown_path.is_file():
        raise NativeAgentLoopError("微信公众号抓取结果的 content.md 不存在")
    content = markdown_path.read_bytes()
    if not content:
        raise NativeAgentLoopError("微信公众号抓取结果的 content.md 为空")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NativeAgentLoopError(
            "微信公众号抓取结果的 content.md 不是 UTF-8 文本"
        ) from exc
    return content


def _external_content_tool_outputs(
    completed: CompletedNativeExternalContent,
) -> list[ToolOutputText]:
    return [
        ToolOutputText(
            text=json.dumps(
                {
                    "status": "succeeded",
                    "external_content_id": completed.external_content_id,
                    "asset_id": completed.asset_id,
                    "platform": completed.platform,
                    "title": completed.title,
                    "author_name": completed.author_name,
                    "publish_time": completed.publish_time,
                    "source_url": completed.source_url,
                    "byte_size": completed.byte_size,
                    "content_excerpt": completed.excerpt,
                    "message": (
                        "完整 Markdown 正文已保存为素材；正文预览仅用于本轮快速理解。"
                    ),
                },
                ensure_ascii=False,
            )
        )
    ]


def build_capture_wechat_article_tool(
    run_id: str,
    *,
    importer: SocialContentImporter = import_social_content,
    store: NativeAgentStore,
) -> FunctionTool:
    async def capture_wechat_article(
        tool_context: ToolContext[None],
        url: str,
    ) -> list[ToolOutputText]:
        normalized_url = _normalize_wechat_article_url(url)
        prepared = store.prepare_external_content_tool(
            tool_call_id=tool_context.tool_call_id,
            url=normalized_url,
        )
        if isinstance(prepared, CompletedNativeExternalContent):
            store.append_event(
                "tool.reused",
                {
                    "tool": "capture_wechat_article",
                    "tool_call_id": tool_context.tool_call_id,
                    "step_id": prepared.step_id,
                    "external_content_id": prepared.external_content_id,
                },
            )
            return _external_content_tool_outputs(prepared)
        store.start_tool(prepared.id)
        try:
            result = await asyncio.to_thread(importer, normalized_url)
            markdown = await asyncio.to_thread(_read_wechat_markdown, result)
            markdown_text = markdown.decode("utf-8")
            completed = store.complete_external_content_tool(
                prepared.id,
                platform=result.platform,
                content_type=result.content_type,
                source_url=result.url,
                resolved_url=result.resolved_url,
                source_content_id=result.content_id,
                title=result.title,
                description=result.description,
                author_name=result.author_name,
                publish_time=result.publish_time,
                publish_timestamp=result.publish_timestamp,
                tags=result.tags,
                metrics=result.metrics,
                markdown=markdown,
                excerpt=markdown_text[:WECHAT_ARTICLE_EXCERPT_MAX_CHARS],
            )
        except Exception as exc:
            store.fail_tool(prepared.id, exc)
            raise
        return _external_content_tool_outputs(completed)

    return function_tool(
        capture_wechat_article,
        name_override="capture_wechat_article",
        description_override=(
            "抓取一个 https://mp.weixin.qq.com/ 微信公众号文章链接，保存完整 Markdown "
            "正文与来源元数据，并返回 external_content_id、asset_id 和有限长度正文预览。"
            "只用于用户明确要求读取或采集公众号文章时；不要传入其他平台链接。"
        ),
    )


def _youtube_insights_tool_outputs(
    result: YoutubeChannelInsightsResult,
) -> list[ToolOutputText | ToolOutputImage]:
    payload = result.model_dump(mode="json")
    payload.pop("output_dir", None)
    channel = payload["channel"]
    if isinstance(channel, dict):
        avatar = channel.get("avatar")
        if isinstance(avatar, dict):
            avatar.pop("file_path", None)
    videos = payload["videos"]
    if isinstance(videos, list):
        for video in videos:
            if not isinstance(video, dict):
                continue
            thumbnail = video.get("thumbnail")
            if isinstance(thumbnail, dict):
                thumbnail.pop("file_path", None)
    outputs: list[ToolOutputText | ToolOutputImage] = [
        ToolOutputText(text=json.dumps(payload, ensure_ascii=False))
    ]
    outputs.append(
        ToolOutputImage(
            image_url=result.channel.avatar.url,
            detail="high",
        )
    )
    outputs.extend(
        ToolOutputImage(
            image_url=video.thumbnail.url,
            detail="high",
        )
        for video in result.videos
    )
    return outputs


def build_inspect_youtube_channel_tool(
    *,
    fetcher: YoutubeInsightsFetcher = fetch_youtube_channel_insights,
) -> FunctionTool:
    async def inspect_youtube_channel(
        tool_context: ToolContext[None],
        channel: str,
        video_limit: int = 1,
        comments_per_video: int = 2,
        comment_order: YoutubeCommentOrder = "relevance",
    ) -> list[ToolOutputText | ToolOutputImage]:
        del tool_context
        normalized_channel = channel.strip()
        if not normalized_channel:
            raise NativeAgentLoopError(
                "inspect_youtube_channel channel 不能为空"
            )
        if len(normalized_channel) > 500:
            raise NativeAgentLoopError(
                "inspect_youtube_channel channel 不能超过 500 字符"
            )
        if not 1 <= video_limit <= 5:
            raise NativeAgentLoopError(
                "inspect_youtube_channel video_limit 必须在 1–5 之间"
            )
        if not 0 <= comments_per_video <= 10:
            raise NativeAgentLoopError(
                "inspect_youtube_channel comments_per_video 必须在 0–10 之间"
            )
        if comment_order not in {"relevance", "time"}:
            raise NativeAgentLoopError(
                "inspect_youtube_channel comment_order 只允许 relevance 或 time"
            )
        result = await asyncio.to_thread(
            fetcher,
            normalized_channel,
            video_limit=video_limit,
            comments_per_video=comments_per_video,
            comment_order=comment_order,
        )
        return _youtube_insights_tool_outputs(result)

    return function_tool(
        inspect_youtube_channel,
        name_override="inspect_youtube_channel",
        description_override=(
            "使用 YouTube Data API v3 读取公开频道资料、订阅/播放/视频数、最近视频的"
            "标题、完整描述、标签、发布时间、时长、播放/点赞/评论数和顶级评论，同时实际"
            "下载频道头像与视频封面，并把图片交给你查看。channel 可传频道 URL、@handle、"
            "handle 或 UC Channel ID。快速看最新表现时 video_limit=1；比较近期内容时可选"
            " 3–5。comments_per_video 可选 0–10；热门评论用 relevance，最新评论用 time。"
        ),
    )


def build_get_account_creation_context_tool(
    run_id: str,
    *,
    session_factory: sessionmaker = SessionLocal,
) -> FunctionTool:
    async def read_account_creation_context(
        tool_context: ToolContext[None],
        account_name: str,
    ) -> list[ToolOutputText]:
        del tool_context
        try:
            payload = await asyncio.to_thread(
                get_account_creation_context,
                account_name,
                run_id=run_id,
                session_factory=session_factory,
            )
        except AccountCreationContextError as exc:
            raise NativeAgentLoopError(str(exc)) from exc
        return [ToolOutputText(text=json.dumps(payload, ensure_ascii=False))]

    return function_tool(
        read_account_creation_context,
        name_override="get_account_creation_context",
        description_override=(
            "根据用户说出的账号名称读取平台数据库中的账号创作上下文。account_name 直接传"
            "用户使用的账号别名、频道标题或 @Handle，不要要求用户提供内部账号 ID。唯一精确"
            "命中时返回账号定位、目标受众、阶段目标、AI 定义、运营备注、对标账号、频道统计"
            "和近期视频；模糊或重名时只返回候选，必须让用户确认后再继续。"
        ),
    )


def build_publish_youtube_video_tool(
    run_id: str,
    *,
    session_factory: sessionmaker = SessionLocal,
    publisher_client: YoutubePublisherClient | None = None,
) -> FunctionTool:
    async def publish_youtube_video(
        tool_context: ToolContext[None],
    ) -> list[ToolOutputText]:
        del tool_context

        def submit_publish_task():
            with session_factory() as db:
                run = db.scalar(
                    select(NativeAgentRun)
                    .join(
                        NativeAgentConversation,
                        NativeAgentConversation.id == NativeAgentRun.conversation_id,
                    )
                    .where(NativeAgentRun.id == run_id)
                )
                if (
                    run is None
                    or run.youtube_channel_id is None
                    or run.youtube_publishable_video_id is None
                    or run.youtube_publish_confirmation_json is None
                    or run.youtube_publish_confirmed_at is None
                ):
                    raise NativeAgentLoopError(
                        "当前 Run 没有经过确认的结构化 YouTube 发布上下文"
                    )
                confirmation = json.loads(run.youtube_publish_confirmation_json)
                task = create_youtube_publish_task(
                    db,
                    YoutubePublishCommand(
                        owner_user_id=run.conversation.owner_user_id,
                        channel_id=run.youtube_channel_id,
                        publishable_video_id=run.youtube_publishable_video_id,
                        visibility=str(confirmation["visibility"]),
                        planned_publish_at=(
                            datetime.fromisoformat(
                                str(confirmation["planned_publish_at"]).replace(
                                    "Z", "+00:00"
                                )
                            )
                            if confirmation.get("planned_publish_at")
                            else None
                        ),
                        notify_subscribers=bool(
                            confirmation["notify_subscribers"]
                        ),
                        confirmed=bool(confirmation["confirmed"]),
                        idempotency_key=f"native-run:{run.id}:youtube-publish",
                    ),
                    client=publisher_client,
                )
                return {
                    "status": task.status,
                    "publish_task_id": task.id,
                    "remote_task_id": task.remote_task_id,
                    "channel_id": task.channel_id,
                    "source_native_agent_video_id": (
                        task.source_native_agent_video_id
                    ),
                    "message": (
                        "发布任务已提交；请在频道详情手动获取状态，不要等待或重复创建"
                    ),
                }

        result = await asyncio.to_thread(submit_publish_task)
        return [
            ToolOutputText(
                text=json.dumps(result, ensure_ascii=False)
            )
        ]

    return function_tool(
        publish_youtube_video,
        name_override="publish_youtube_video",
        description_override=(
            "提交当前 Run 已由用户确认的 YouTube 发布任务。目标频道、视频、标题、可见性和"
            "计划时间均由 Runtime 固定；不得从普通文本猜测或改写。提交后立即返回任务 ID，"
            "不要等待上传完成，也不要重复调用。"
        ),
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


def native_agent_instructions(
    run: NativeAgentRun,
    *,
    active_role: str | None = None,
) -> str:
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
    instructions += creation_account_context_instructions(run)
    if active_role is not None:
        instructions += (
            "\n\n<execution_context>\n"
            f"active_role={active_role}\n"
            "只执行 Skill 中该角色的职责。角色规则属于 instructions；当前任务内容来自输入。"
            "\n</execution_context>"
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
    if run.youtube_publish_confirmation_json:
        instructions += (
            "\n\n<youtube_publish_context>\n"
            "用户已在界面中明确选择并确认以下发布配置。只有需要真正提交发布时才调用一次 "
            "publish_youtube_video；Tool 不接收目标参数，禁止从普通文本猜测或替换频道。"
            "Tool 返回本地任务 ID 后立即向用户说明已提交，并结束当前对话，不等待上传完成。\n"
            f"{run.youtube_publish_confirmation_json}\n"
            f"channel_id={run.youtube_channel_id}\n"
            f"publishable_video_id={run.youtube_publishable_video_id}\n"
            "</youtube_publish_context>"
        )
    return instructions


def creation_account_context_instructions(run: NativeAgentRun) -> str:
    if not run.creation_channel_context_json:
        return ""
    try:
        context = json.loads(run.creation_channel_context_json)
    except json.JSONDecodeError as exc:
        raise NativeAgentLoopError("创作账号 Context 快照不是合法 JSON") from exc
    if not isinstance(context, dict):
        raise NativeAgentLoopError("创作账号 Context 快照必须是对象")
    return (
        "\n\n<creation_account_context>\n"
        "以下资料来自用户在本轮通过 @创作账号 明确选择的账号，是当前 Run 的权威账号上下文。"
        "规划选题、语气、受众、内容结构和文案时必须使用这些资料；不得声称没有读取到账号 "
        "Context，也不得用同名账号或模型猜测覆盖。资料中的历史内容只作为创作依据，不代表"
        "用户要求逐字复制。\n"
        f"{json.dumps(context, ensure_ascii=False, separators=(',', ':'))}\n"
        "</creation_account_context>"
    )


def article_role_instructions(
    run: NativeAgentRun,
    workflow: CompiledArticleWorkflow,
    *,
    active_role: Literal["director", "writer", "reviewer"],
    durable_task_key: str | None = None,
) -> str:
    role = workflow.role(active_role)
    shared_constraints = "\n".join(
        f"- {constraint}" for constraint in workflow.shared_constraints
    )
    role_instructions = "\n".join(
        f"{index}. {instruction}"
        for index, instruction in enumerate(role.instructions, start=1)
    )
    instructions = (
        "你属于 DoodleStory 的内容创作与脚本编写系统。当前 Run 的完整 Skill 已由"
        " Workflow Compiler 编译并校验；你只执行下面分配给当前角色的局部计划。\n\n"
        f"<workflow_summary>\n{workflow.workflow_summary}\n</workflow_summary>\n\n"
        f"<shared_constraints>\n{shared_constraints}\n</shared_constraints>\n\n"
        f"<role name={json.dumps(active_role)}>\n"
        f"任务：{role.mission}\n"
        f"{role_instructions}\n"
        "</role>"
    )
    instructions += creation_account_context_instructions(run)
    if durable_task_key:
        task_constraint = {
            "research_topics": (
                "当前 Durable Task 是候选选题。只能生成候选选题并等待用户确认；"
                "不得生成 approved_topic、正文、Review、封面或媒体计划。"
            ),
            "write_draft": (
                "当前 Durable Task 是正文。只能基于已经批准的选题生成完整正文草稿；"
                "不得重新生成候选选题、Review、封面或媒体计划。"
            ),
            "review_draft": (
                "当前 Durable Task 是 Review。只能审阅当前正文并输出审稿结论；"
                "不得改写正文、重新选题或生成媒体计划。"
            ),
            "supplement_research": (
                "当前 Durable Task 是补充研究。只能基于已批准选题和 Review 反馈补充研究依据，"
                "不得重新选题、写正文、审稿或生成媒体计划。"
            ),
        }.get(durable_task_key)
        if task_constraint:
            instructions += (
                "\n\n<durable_task_constraint>\n"
                f"{task_constraint}\n"
                "</durable_task_constraint>"
            )
    if active_role == "director":
        steps = [
            step.model_dump(mode="json")
            for step in workflow.execution_steps
        ]
        gates = "\n".join(f"- {gate}" for gate in workflow.quality_gates)
        instructions += (
            "\n\n<execution_plan>\n"
            f"{json.dumps(steps, ensure_ascii=False, separators=(',', ':'))}\n"
            "</execution_plan>\n\n"
            f"<quality_gates>\n{gates}\n</quality_gates>\n\n"
            "你负责按 execution_plan 给子 Agent 分配任务并保持用户会话控制权。"
            "角色协作使用 Agent Tool，不使用 handoff。子 Agent 返回的 Artifact 是后续步骤的"
            "正式输入；submit_final_article 返回等待审批后立即停止。"
        )
    return instructions


async def compile_article_workflow(
    run: NativeAgentRun,
    *,
    provider: OpenAIProvider,
    model: str,
    store: NativeAgentStore,
    hooks: NativeModelMetricHooks,
) -> CompiledArticleWorkflow:
    persisted = load_compiled_workflow_plan(
        run.id,
        skill_content_hash=run.skill_content_hash_snapshot,
        session_factory=store.session_factory,
    )
    if persisted is not None:
        return CompiledArticleWorkflow.model_validate(persisted)
    compiler = Agent(
        name="DoodleStoryArticleWorkflowCompiler",
        instructions=ARTICLE_WORKFLOW_COMPILER_INSTRUCTIONS,
        model=model,
        model_settings=ModelSettings(
            retry=ModelRetrySettings(max_retries=0),
            store=False,
        ),
        output_type=CompiledArticleWorkflow,
        hooks=hooks,
    )
    compiler_input = json.dumps(
        {
            "skill_name": run.skill_name_snapshot,
            "skill_version": run.skill_version_snapshot,
            "skill_content_hash": run.skill_content_hash_snapshot,
            "available_roles": ["director", "writer", "reviewer"],
            "available_tools": [
                "write_article",
                "review_article",
                "submit_final_article",
            ],
            "skill": run.skill_version.instructions,
        },
        ensure_ascii=False,
    )
    with agent_span(
        "native_agent.workflow_compiler",
        agent_run_id=run.id,
        span_type="CHAT_MODEL",
        attributes={
            "model": model,
            "skill_content_hash": run.skill_content_hash_snapshot,
        },
    ) as compiler_span:
        set_span_inputs(
            compiler_span,
            {
                "instructions": ARTICLE_WORKFLOW_COMPILER_INSTRUCTIONS,
                "skill": run.skill_version.instructions,
            },
        )
        result = await Runner.run(
            compiler,
            compiler_input,
            run_config=RunConfig(
                model_provider=provider,
                tracing_disabled=True,
                workflow_name="DoodleStory Article Workflow Compiler",
            ),
            max_turns=2,
        )
        workflow = CompiledArticleWorkflow.model_validate(result.final_output)
        set_span_outputs(
            compiler_span,
            {"compiled_workflow": workflow.model_dump(mode="json")},
        )
        set_span_result(
            compiler_span,
            {
                "model_call_count": len(result.raw_responses),
                "role_count": len(workflow.roles),
                "step_count": len(workflow.execution_steps),
            },
        )
    save_compiled_workflow_plan(
        run.id,
        skill_content_hash=run.skill_content_hash_snapshot,
        plan=workflow.model_dump(mode="json"),
        session_factory=store.session_factory,
    )
    return workflow


def build_article_agent_tools(
    run: NativeAgentRun,
    *,
    workflow: CompiledArticleWorkflow,
    model: str,
    store: NativeAgentStore,
    hooks: NativeModelMetricHooks,
    durable_task_key: str | None = None,
) -> list[FunctionTool]:
    if durable_task_key and durable_task_key.startswith("image:"):
        return []
    model_settings = ModelSettings(
        retry=ModelRetrySettings(max_retries=0),
        store=False,
    )
    writer = Agent(
        name="DoodleStoryArticleWriter",
        instructions=article_role_instructions(
            run,
            workflow,
            active_role="writer",
            durable_task_key=durable_task_key,
        ),
        model=model,
        model_settings=model_settings,
        output_type=ArticleDraftOutput,
        hooks=hooks,
    )
    reviewer = Agent(
        name="DoodleStoryArticleReviewer",
        instructions=article_role_instructions(
            run,
            workflow,
            active_role="reviewer",
            durable_task_key=durable_task_key,
        ),
        model=model,
        model_settings=model_settings,
        output_type=ArticleReviewOutput,
        hooks=hooks,
    )

    async def extract_writer_output(result) -> str:
        output = ArticleDraftOutput.model_validate(result.final_output)
        artifact_type = (
            TOPIC_CANDIDATES
            if durable_task_key == "research_topics"
            else ARTICLE_DRAFT
        )
        artifact = save_article_artifact(
            run.id,
            artifact_type=artifact_type,
            producer_role="writer",
            content=output.model_dump(mode="json"),
            session_factory=store.session_factory,
        )
        if durable_task_key in {"research_topics", "write_draft"}:
            approval = request_article_artifact_approval(
                run.id,
                artifact_id=str(artifact["id"]),
                purpose=(
                    "topic_selection"
                    if durable_task_key == "research_topics"
                    else "article_draft_review"
                ),
                session_factory=store.session_factory,
            )
            return json.dumps(approval, ensure_ascii=False)
        return json.dumps(
            {"status": "succeeded", "artifact": artifact},
            ensure_ascii=False,
        )

    async def extract_reviewer_output(result) -> str:
        output = ArticleReviewOutput.model_validate(result.final_output)
        artifact = save_article_artifact(
            run.id,
            artifact_type=ARTICLE_REVIEW,
            producer_role="reviewer",
            content=output.model_dump(mode="json"),
            session_factory=store.session_factory,
        )
        if durable_task_key == "review_draft":
            approval = request_article_artifact_approval(
                run.id,
                artifact_id=str(artifact["id"]),
                purpose="editorial_review",
                session_factory=store.session_factory,
            )
            return json.dumps(approval, ensure_ascii=False)
        return json.dumps(
            {"status": "succeeded", "artifact": artifact},
            ensure_ascii=False,
        )

    async def submit_final_article(
        title: str,
        body_markdown: str,
    ) -> list[ToolOutputText]:
        result = request_final_article_approval(
            run.id,
            title=title,
            body_markdown=body_markdown,
            session_factory=store.session_factory,
        )
        return [ToolOutputText(text=json.dumps(result, ensure_ascii=False))]

    tools = [
        writer.as_tool(
            tool_name="write_article",
            tool_description=(
                "调用同一 Skill 中的 Writer 子 Agent。输入必须包含用户原始要求，以及需要时的"
                "旧稿和审稿意见；返回已落库的完整文案草稿 Artifact。"
            ),
            custom_output_extractor=extract_writer_output,
            max_turns=4,
        ),
        reviewer.as_tool(
            tool_name="review_article",
            tool_description=(
                "调用同一 Skill 中的 Reviewer 子 Agent。输入必须包含用户原始要求和完整草稿；"
                "返回已落库的独立审稿 Artifact。"
            ),
            custom_output_extractor=extract_reviewer_output,
            max_turns=4,
        ),
        function_tool(
            submit_final_article,
            name_override="submit_final_article",
            description_override=(
                "保存最终标题和完整 Markdown 正文，创建用户审批并暂停当前文案 Run。"
                "Writer 和 Reviewer 均完成后才能调用；调用后停止执行。"
            ),
        ),
    ]
    if durable_task_key in {"research_topics", "write_draft", "supplement_research"}:
        return [tools[0]]
    if durable_task_key == "review_draft":
        return [tools[1]]
    return tools


async def execute_native_agent_run(
    run_id: str,
    *,
    settings: Settings | None = None,
    image_generator: ImageGenerator = generate_xg_image,
    speech_generator: SpeechGenerator | None = None,
    subtitle_generator: SubtitleGenerator = generate_whisper_subtitles,
    video_renderer: VideoRenderer = render_remotion_video,
) -> None:
    resolved_settings = settings or get_settings()
    resolved_speech_generator = speech_generator or (
        lambda *, text, speed=1.0: generate_volcengine_speech(
            text=text,
            speed=speed,
            settings=resolved_settings,
        )
    )
    store = NativeAgentStore(run_id, session_factory=SessionLocal)
    sdk_session = NativeAgentDatabaseSession(
        run_id,
        session_factory=SessionLocal,
    )
    durable_task_key: str | None = None
    with SessionLocal() as db:
        run = db.scalar(
            select(NativeAgentRun)
            .where(NativeAgentRun.id == run_id)
            .options(
                selectinload(NativeAgentRun.skill_version),
                selectinload(NativeAgentRun.conversation),
            )
        )
        if run is None:
            raise NativeAgentLoopError("Native Agent Run 不存在")
        if run.status not in {
            AgentRunStatus.queued,
            AgentRunStatus.retrying,
        }:
            raise NativeAgentLoopError("Native Agent Run 不是 queued 或 retrying 状态")
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
        has_youtube_publish_context = bool(
            run.youtube_channel_id
            and run.youtube_publishable_video_id
            and run.youtube_publish_confirmation_json
            and run.youtube_publish_confirmed_at
        )
        article_tool_names = {
            "write_article",
            "review_article",
            "submit_final_article",
        }
        is_article_workflow = bool(
            article_tool_names.intersection(exposed_tool_names)
        )
        if is_article_workflow:
            from app.services.durable_agent_runtime import current_task_key

            durable_task_key = current_task_key(db, native_run_id=run.id)
        instructions = (
            None if is_article_workflow else native_agent_instructions(run)
        )
        trace_context = {
            "conversation_id": run.conversation_id,
            "skill_version_id": run.skill_version_id,
            "style_id": run.style_id,
        }
    resumed = await sdk_session.has_items()
    execution_attempt = store.start_run(resumed=resumed)
    client = AsyncOpenAI(
        api_key=resolved_settings.text_fallback_api_key.strip(),
        base_url=resolved_settings.text_fallback_openai_base_url,
        max_retries=0,
        timeout=resolved_settings.agent_request_timeout_seconds,
    )
    provider = OpenAIProvider(openai_client=client, use_responses=True)
    with native_agent_run_span(
        native_agent_run_id=run_id,
        execution_attempt=execution_attempt,
        conversation_id=trace_context["conversation_id"],
        skill_version_id=trace_context["skill_version_id"],
        style_id=trace_context["style_id"],
        model=resolved_settings.agent_model.strip(),
        app_environment=resolved_settings.app_env,
    ) as root_span:
        try:
            metric_hooks = NativeModelMetricHooks(
                store,
                phase=f"execution_attempt_{execution_attempt}",
            )
            workflow: CompiledArticleWorkflow | None = None
            if is_article_workflow:
                workflow = await compile_article_workflow(
                    run,
                    provider=provider,
                    model=resolved_settings.agent_model.strip(),
                    store=store,
                    hooks=metric_hooks,
                )
                instructions = article_role_instructions(
                    run,
                    workflow,
                    active_role="director",
                    durable_task_key=durable_task_key,
                )
                if durable_task_key and durable_task_key.startswith("image:"):
                    from app.services.durable_agent_runtime import (
                        pending_media_context,
                    )

                    with SessionLocal() as media_db:
                        pending_panels = pending_media_context(
                            media_db,
                            native_run_id=run_id,
                        )
                    instructions += (
                        "\n\n<durable_media_tasks>\n"
                        "当前只执行下列已经由用户批准的图片 Panel。每个 Panel 必须严格使用"
                        "其 prompt 调用一次 generate_image；不要调用文案 Tool，不要新增、合并或"
                        "遗漏 Panel。所有 Panel 完成后再返回简短结果。\n"
                        f"{json.dumps(pending_panels, ensure_ascii=False, separators=(',', ':'))}\n"
                        "</durable_media_tasks>"
                    )
            if instructions is None:
                raise NativeAgentLoopError("Native Agent 缺少运行 instructions")

            tools: list[FunctionTool] = []
            if "generate_image" in exposed_tool_names:
                tools.append(
                    build_generate_image_tool(
                        context,
                        image_generator=image_generator,
                        store=store,
                    )
                )
            if "inspect_image" in exposed_tool_names:
                tools.append(build_inspect_image_tool(run_id, store=store))
            if "generate_speech" in exposed_tool_names:
                tools.append(
                    build_generate_speech_tool(
                        run_id,
                        settings=resolved_settings,
                        speech_generator=resolved_speech_generator,
                        store=store,
                    )
                )
            if "generate_subtitles" in exposed_tool_names:
                tools.append(
                    build_generate_subtitles_tool(
                        run_id,
                        settings=resolved_settings,
                        subtitle_generator=subtitle_generator,
                        store=store,
                    )
                )
            if "render_story_video" in exposed_tool_names:
                tools.append(
                    build_render_story_video_tool(
                        run_id,
                        settings=resolved_settings,
                        video_renderer=video_renderer,
                        store=store,
                    )
                )
            if "capture_wechat_article" in exposed_tool_names:
                tools.append(
                    build_capture_wechat_article_tool(
                        run_id,
                        store=store,
                    )
                )
            if "get_account_creation_context" in exposed_tool_names:
                tools.append(
                    build_get_account_creation_context_tool(run_id)
                )
            if "inspect_youtube_channel" in exposed_tool_names:
                tools.append(build_inspect_youtube_channel_tool())
            if (
                has_youtube_publish_context
                and "publish_youtube_video" in exposed_tool_names
            ):
                tools.append(build_publish_youtube_video_tool(run_id))
            if workflow is not None:
                article_tools = build_article_agent_tools(
                    run,
                    workflow=workflow,
                    model=resolved_settings.agent_model.strip(),
                    store=store,
                    hooks=metric_hooks,
                    durable_task_key=durable_task_key,
                )
                tools.extend(
                    tool
                    for tool in article_tools
                    if tool.name in exposed_tool_names
                )
            agent = Agent(
                name=(
                    "DoodleStoryArticleDirector"
                    if workflow is not None
                    else "DoodleStoryNativeContentAgent"
                ),
                instructions=instructions,
                model=resolved_settings.agent_model.strip(),
                tools=tools,
                model_settings=ModelSettings(
                    retry=ModelRetrySettings(max_retries=0),
                    store=False,
                ),
                hooks=metric_hooks,
            )
            model_loop_start_count = metric_hooks.started_count
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
                        "model_call_count": (
                            metric_hooks.started_count - model_loop_start_count
                        ),
                        "model_call_count_by_role": metric_hooks.role_counts,
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
                        "model_call_count": (
                            metric_hooks.started_count - model_loop_start_count
                        ),
                        "model_call_count_by_role": metric_hooks.role_counts,
                    },
                )
            if has_pending_article_approval(
                run_id,
                session_factory=SessionLocal,
            ):
                store.pause_for_article_approval(final_output)
                terminal_status = AgentRunStatus.waiting_for_input
            else:
                from app.services.durable_agent_runtime import (
                    can_complete_native_run,
                    finalize_workflow_if_complete,
                    inspect_pending_native_media,
                    media_ready_for_quality,
                )

                await asyncio.to_thread(
                    inspect_pending_native_media,
                    native_run_id=run_id,
                    session_factory=SessionLocal,
                )
                with SessionLocal() as durable_db:
                    waiting_for_quality = media_ready_for_quality(
                        durable_db,
                        native_run_id=run_id,
                    )
                    durable_db.commit()
                    can_complete = can_complete_native_run(
                        durable_db,
                        native_run_id=run_id,
                    )
                    if can_complete and not waiting_for_quality:
                        finalize_workflow_if_complete(
                            durable_db,
                            native_run_id=run_id,
                        )
                        durable_db.commit()
                if waiting_for_quality:
                    store.pause_for_media_quality(final_output)
                    terminal_status = AgentRunStatus.waiting_for_input
                elif not can_complete:
                    raise NativeAgentLoopError(
                        "当前 Durable Task 尚未完成或仍等待人工 Gate，不能将 Run 标记成功"
                    )
                else:
                    store.complete_run(final_output)
                    terminal_status = AgentRunStatus.succeeded
            with SessionLocal() as db:
                run = db.get(NativeAgentRun, run_id)
                if run is None:
                    raise NativeAgentLoopError("Native Agent Run 不存在")
                model_call_count = run.model_call_count
                image_call_count = run.image_call_count
                speech_call_count = run.speech_call_count
                video_call_count = run.video_call_count
            set_span_result(
                root_span,
                {
                    "execution_attempt": execution_attempt,
                    "attempt_model_call_count": metric_hooks.started_count,
                    "attempt_model_call_completed_count": metric_hooks.completed_count,
                    "attempt_model_call_count_by_role": metric_hooks.role_counts,
                },
            )
            set_native_agent_run_trace_status(
                root_span,
                native_agent_run_id=run_id,
                run_status=terminal_status.value,
                model_call_count=model_call_count,
                image_call_count=image_call_count,
                speech_call_count=speech_call_count,
                video_call_count=video_call_count,
                error_code=None,
            )
        except Exception as exc:
            store.fail_run(exc)
            if "metric_hooks" in locals():
                set_span_result(
                    root_span,
                    {
                        "execution_attempt": execution_attempt,
                        "attempt_model_call_count": metric_hooks.started_count,
                        "attempt_model_call_completed_count": metric_hooks.completed_count,
                        "attempt_model_call_count_by_role": metric_hooks.role_counts,
                    },
                )
            with SessionLocal() as db:
                run = db.get(NativeAgentRun, run_id)
                model_call_count = run.model_call_count if run is not None else 0
                image_call_count = run.image_call_count if run is not None else 0
                speech_call_count = run.speech_call_count if run is not None else 0
                video_call_count = run.video_call_count if run is not None else 0
            set_native_agent_run_trace_status(
                root_span,
                native_agent_run_id=run_id,
                run_status=AgentRunStatus.failed.value,
                model_call_count=model_call_count,
                image_call_count=image_call_count,
                speech_call_count=speech_call_count,
                video_call_count=video_call_count,
                error_code=type(exc).__name__,
            )
        finally:
            await client.close()
