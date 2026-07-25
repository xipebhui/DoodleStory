from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import logging
import re
import time
from typing import Any, Literal, Protocol

from agents import Agent, ModelSettings, RunConfig, Runner
from agents.model_settings import ModelRetrySettings
from agents.models.openai_provider import OpenAIProvider
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import Settings, get_settings
from app.schemas.agent import ComicPlan
from app.schemas.agent_skill import AgentSkillAuthoringSuggestion
from app.services.agent_observability import agent_span, set_span_result, set_span_status
from app.services.agent_skill_runtime import BASE_AGENT_INSTRUCTIONS, RuntimeSkill, skill_model_instructions


logger = logging.getLogger(__name__)
API_SHAPE = "responses"
MAX_SAFE_ERROR_CHARS = 500
_current_agent_run_id: ContextVar[str | None] = ContextVar(
    "current_agent_run_id",
    default=None,
)


class AgentSkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["selected", "none", "ask_user"]
    skill_version_id: str | None = None
    user_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_outcome(self) -> "AgentSkillSelection":
        if self.outcome == "selected" and not self.skill_version_id:
            raise ValueError("selected 必须包含 skill_version_id")
        if self.outcome != "selected":
            self.skill_version_id = None
        if self.outcome == "ask_user" and not (self.user_message or "").strip():
            raise ValueError("ask_user 必须包含用户可见问题")
        return self


@dataclass(frozen=True)
class AgentProviderConfig:
    name: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class AgentModelRoute:
    provider: str
    model: str
    api_shape: str
    attempt: int
    fallback_from: str | None = None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class AgentModelFailure:
    code: str
    safe_message: str
    retryable: bool
    status_code: int | None
    internal_error_ref: str


@dataclass(frozen=True)
class AgentModelResult:
    final_output: str
    usage: dict[str, int]
    provider_request_id: str | None
    raw_result: Any
    route: AgentModelRoute
    structured_output: Any | None = None


class AgentModelRoutingError(RuntimeError):
    def __init__(self, failure: AgentModelFailure):
        super().__init__(failure.safe_message)
        self.failure = failure


class AgentModelAttemptObserver(Protocol):
    async def attempt_started(self, route: AgentModelRoute) -> str | None: ...

    async def attempt_succeeded(
        self,
        route: AgentModelRoute,
        result: AgentModelResult,
        latency_ms: int,
    ) -> None: ...

    async def attempt_failed(
        self,
        route: AgentModelRoute,
        failure: AgentModelFailure,
        latency_ms: int,
    ) -> None: ...


def redact_agent_error(text: str, secrets: tuple[str, ...] | list[str] = ()) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;\"'}]+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", redacted)
    return redacted[:MAX_SAFE_ERROR_CHARS]


def _status_code(exc: Exception) -> int | None:
    value = getattr(exc, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def classify_agent_model_error(
    exc: Exception,
    *,
    secrets: tuple[str, ...] | list[str] = (),
) -> AgentModelFailure:
    status_code = _status_code(exc)
    raw = redact_agent_error(str(exc), secrets)
    lowered = raw.lower()
    permanent_markers = (
        "invalid_request",
        "invalid request",
        "model_not_found",
        "model not found",
        "unsupported",
        "not support",
        "does not support",
        "no available channel",
        "no channel",
        "无可用渠道",
        "不支持",
        "content policy",
        "content_policy",
        "safety policy",
        "safety violation",
        "schema validation",
        "tool schema",
    )
    temporary_markers = (
        "temporary",
        "temporarily",
        "timeout",
        "timed out",
        "overload",
        "unavailable",
        "upstream",
        "gateway",
        "rate limit",
        "busy",
        "try again",
        "connection reset",
        "connection refused",
    )
    stream_interruption_markers = (
        "stream disconnected before completion",
        "stream closed before",
        "response stream disconnected",
    )
    internal_ref = f"{type(exc).__name__}:{status_code or 'none'}"

    if status_code in {408, 500, 502, 503, 504} and any(
        marker in lowered for marker in stream_interruption_markers
    ):
        return AgentModelFailure(
            code="AgentModelTemporaryError",
            safe_message="模型响应流暂时中断，请稍后重试",
            retryable=True,
            status_code=status_code,
            internal_error_ref=internal_ref,
        )
    if any(marker in lowered for marker in permanent_markers):
        return AgentModelFailure(
            code="AgentModelPermanentError",
            safe_message="模型请求无法执行，请检查模型能力、请求内容或服务配置",
            retryable=False,
            status_code=status_code,
            internal_error_ref=internal_ref,
        )
    if status_code in {400, 401, 403, 404, 422}:
        return AgentModelFailure(
            code="AgentModelPermanentError",
            safe_message="模型请求无法执行，请检查模型能力、请求内容或服务配置",
            retryable=False,
            status_code=status_code,
            internal_error_ref=internal_ref,
        )
    if isinstance(exc, (APIConnectionError, APITimeoutError, ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return AgentModelFailure(
            code="AgentModelTemporaryError",
            safe_message="模型服务暂时不可用，请稍后重试",
            retryable=True,
            status_code=status_code,
            internal_error_ref=internal_ref,
        )
    if status_code in {408, 409, 429}:
        return AgentModelFailure(
            code="AgentModelTemporaryError",
            safe_message="模型服务暂时不可用，请稍后重试",
            retryable=True,
            status_code=status_code,
            internal_error_ref=internal_ref,
        )
    if status_code in {500, 502, 503, 504} and any(marker in lowered for marker in temporary_markers):
        return AgentModelFailure(
            code="AgentModelTemporaryError",
            safe_message="模型服务暂时不可用，请稍后重试",
            retryable=True,
            status_code=status_code,
            internal_error_ref=internal_ref,
        )
    return AgentModelFailure(
        code="AgentModelPermanentError",
        safe_message="模型请求失败，且错误不满足安全重试条件",
        retryable=False,
        status_code=status_code,
        internal_error_ref=internal_ref,
    )


def summarize_agent_usage(raw_responses: list[Any]) -> dict[str, int]:
    summary = {"requests": len(raw_responses), "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for response in raw_responses:
        usage = getattr(response, "usage", None)
        if usage is None:
            continue
        summary["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
        summary["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
        summary["total_tokens"] += int(getattr(usage, "total_tokens", 0) or 0)
    return summary


def extract_agent_provider_request_id(raw_responses: list[Any]) -> str | None:
    identifiers = [
        getattr(response, "request_id", None) or getattr(response, "response_id", None)
        for response in raw_responses
    ]
    return next((str(value) for value in reversed(identifiers) if value), None)


class AgentModelRouter:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model = self.settings.agent_model.strip()
        self.primary = AgentProviderConfig(
            name="huomiao",
            base_url=self.settings.text_fallback_openai_base_url,
            api_key=self.settings.text_fallback_api_key.strip(),
        )
        self.fallback = AgentProviderConfig(
            name="lio",
            base_url=self.settings.lio_openai_base_url,
            api_key=self.settings.lio_api_key.strip(),
        )
        self._validate_config()

    def _validate_config(self) -> None:
        missing: list[str] = []
        if not self.model:
            missing.append("AGENT_MODEL")
        for provider in (self.primary, self.fallback):
            if not provider.base_url:
                missing.append(f"{provider.name}.base_url")
            if not provider.api_key:
                missing.append(f"{provider.name}.api_key")
        if missing:
            raise ValueError(f"Agent Provider 配置缺失: {', '.join(missing)}")

    def _provider(self, config: AgentProviderConfig) -> OpenAIProvider:
        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=0,
            timeout=self.settings.agent_request_timeout_seconds,
        )
        return OpenAIProvider(openai_client=client, use_responses=True)

    async def _invoke(self, config: AgentProviderConfig, route: AgentModelRoute, input_items: list[dict[str, Any]]) -> AgentModelResult:
        agent = Agent(
            name="DoodleStoryContentAgent",
            instructions=BASE_AGENT_INSTRUCTIONS,
            model=self.model,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
                store=False,
            ),
        )
        provider = self._provider(config)
        try:
            result = await Runner.run(
                agent,
                input_items,
                run_config=RunConfig(
                    model_provider=provider,
                    tracing_disabled=True,
                    workflow_name="DoodleStory Agent Turn",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        final_output = str(result.final_output or "").strip()
        if not final_output:
            raise ValueError("Agent model returned an empty final response")
        raw_responses = list(result.raw_responses)
        return AgentModelResult(
            final_output=final_output,
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=extract_agent_provider_request_id(raw_responses),
            raw_result=result,
            route=route,
        )

    async def _invoke_skill_plan(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        style_context: dict[str, object],
        skill: RuntimeSkill,
    ) -> AgentModelResult:
        agent = Agent(
            name="DoodleStoryContentAgent",
            instructions=(
                f"{skill_model_instructions(skill)}\n\n"
                "Runtime 当前要求输出一个等待用户确认的 ComicPlan control action。"
                "schema_version 固定为 1；style_ref_id 和 aspect_ratio 必须逐字使用已鉴权风格快照；"
                "estimated_image_credits 必须等于 panels 数量；未获确认前不得声称图片已经生成。"
                "严格输出 ComicPlan schema，不输出解释或隐藏推理。\n"
                f"已鉴权风格快照：{style_context}"
            ),
            model=self.model,
            output_type=ComicPlan,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
                store=False,
            ),
        )
        provider = self._provider(config)
        try:
            result = await Runner.run(
                agent,
                input_items,
                run_config=RunConfig(
                    model_provider=provider,
                    tracing_disabled=True,
                    workflow_name="DoodleStory Skill Control Action",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        plan = ComicPlan.model_validate(result.final_output)
        raw_responses = list(result.raw_responses)
        return AgentModelResult(
            final_output=plan.model_dump_json(),
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=extract_agent_provider_request_id(raw_responses),
            raw_result=result,
            route=route,
            structured_output=plan,
        )

    async def _invoke_skill_final(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        skill: RuntimeSkill,
    ) -> AgentModelResult:
        agent = Agent(
            name="DoodleStoryContentAgent",
            instructions=(
                f"{skill_model_instructions(skill)}\n\n"
                "应用上下文已经包含已批准方案和真实 Tool Output。"
                "只根据这些真实状态给用户一句简洁结果说明：全部成功时说明漫画已完成；存在失败时明确指出"
                "失败的格数与可见原因，绝不能把失败说成成功。不要输出内部思维过程，"
                "不要声称进行了没有真实 Tool Output 的检查或重试。"
            ),
            model=self.model,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
                store=False,
            ),
        )
        provider = self._provider(config)
        try:
            result = await Runner.run(
                agent,
                input_items,
                run_config=RunConfig(
                    model_provider=provider,
                    tracing_disabled=True,
                    workflow_name="DoodleStory Skill Result",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        final_output = str(result.final_output or "").strip()
        if not final_output:
            raise ValueError("Agent model returned an empty comic result response")
        raw_responses = list(result.raw_responses)
        return AgentModelResult(
            final_output=final_output,
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=extract_agent_provider_request_id(raw_responses),
            raw_result=result,
            route=route,
        )

    async def _invoke_skill_text(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        skill: RuntimeSkill,
    ) -> AgentModelResult:
        agent = Agent(
            name="DoodleStoryContentAgent",
            instructions=skill_model_instructions(skill),
            model=self.model,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
                store=False,
            ),
        )
        provider = self._provider(config)
        try:
            result = await Runner.run(
                agent,
                input_items,
                run_config=RunConfig(
                    model_provider=provider,
                    tracing_disabled=True,
                    workflow_name="DoodleStory Skill Text",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        final_output = str(result.final_output or "").strip()
        if not final_output:
            raise ValueError("Agent model returned an empty Skill response")
        raw_responses = list(result.raw_responses)
        return AgentModelResult(
            final_output=final_output,
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=extract_agent_provider_request_id(raw_responses),
            raw_result=result,
            route=route,
        )

    async def _invoke_skill_selection(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        catalog: list[dict[str, object]],
    ) -> AgentModelResult:
        agent = Agent(
            name="DoodleStorySkillSelector",
            instructions=(
                f"{BASE_AGENT_INSTRUCTIONS}\n\n"
                "只根据用户目标、已鉴权资源摘要和以下可用 Skill catalog 决定是否需要一个 Skill。"
                "只可返回 catalog 中原样的 skill_version_id。明确匹配一个时 selected；"
                "普通讨论或无需专业方法时 none；多个候选无法可靠区分时 ask_user，并给出简短问题。"
                "不得加载正文、调用 Tool 或随机选择。\n"
                f"Catalog={catalog}"
            ),
            model=self.model,
            output_type=AgentSkillSelection,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
                store=False,
            ),
        )
        provider = self._provider(config)
        try:
            result = await Runner.run(
                agent,
                input_items,
                run_config=RunConfig(
                    model_provider=provider,
                    tracing_disabled=True,
                    workflow_name="DoodleStory Skill Selection",
                ),
                max_turns=1,
            )
        finally:
            await provider._client.close()
        selection = AgentSkillSelection.model_validate(result.final_output)
        raw_responses = list(result.raw_responses)
        return AgentModelResult(
            final_output=selection.model_dump_json(),
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=extract_agent_provider_request_id(raw_responses),
            raw_result=result,
            route=route,
            structured_output=selection,
        )

    async def _invoke_skill_authoring(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
    ) -> AgentModelResult:
        agent = Agent(
            name="SkillAuthoringAgent",
            instructions=(
                "你帮助用户把自然语言创作目标整理为 DoodleStory Skill 草稿建议。"
                "Skill 是纯文本创作方法，不是代码、JSON、YAML、工作流 DSL 或 Provider 配置。"
                "建议正文必须使用中文 Markdown，并清楚包含目标、输入、方法、用户确认、"
                "质量门槛和完成条件。只能建议输入中 selected_tool_names 已明确列出的 Tool，"
                "不得增加 Tool、脚本、MCP、Webhook、URL、模型、API key 或数据库标识。"
                "current_instructions 存在时保留其中有效意图并进行优化。"
                "notes 只写用户可见的简短注意事项，不展示隐藏推理。"
            ),
            model=self.model,
            output_type=AgentSkillAuthoringSuggestion,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
                store=False,
            ),
        )
        provider = self._provider(config)
        try:
            result = await Runner.run(
                agent,
                input_items,
                run_config=RunConfig(
                    model_provider=provider,
                    tracing_disabled=True,
                    workflow_name="DoodleStory Skill Authoring",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        suggestion = AgentSkillAuthoringSuggestion.model_validate(result.final_output)
        raw_responses = list(result.raw_responses)
        return AgentModelResult(
            final_output=suggestion.model_dump_json(),
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=extract_agent_provider_request_id(raw_responses),
            raw_result=result,
            route=route,
            structured_output=suggestion,
        )

    async def _run_specialized_attempt(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
        invoke,
    ) -> tuple[AgentModelResult | None, AgentModelFailure | None]:
        return await self._execute_attempt(
            config=config,
            route=route,
            input_items=input_items,
            observer=observer,
            invoke=invoke,
        )

    async def _run_specialized(
        self,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
        invoke,
    ) -> AgentModelResult:
        last_failure: AgentModelFailure | None = None
        primary_attempts = 1 + self.settings.agent_primary_retry_attempts
        for attempt in range(1, primary_attempts + 1):
            route = AgentModelRoute(
                provider=self.primary.name,
                model=self.model,
                api_shape=API_SHAPE,
                attempt=attempt,
            )
            result, failure = await self._run_specialized_attempt(
                self.primary, route, input_items, observer, invoke
            )
            if result is not None:
                return result
            assert failure is not None
            last_failure = failure
            if not failure.retryable:
                raise AgentModelRoutingError(failure)
            if attempt < primary_attempts and self.settings.agent_retry_backoff_seconds:
                await asyncio.sleep(self.settings.agent_retry_backoff_seconds)
        assert last_failure is not None
        fallback_route = AgentModelRoute(
            provider=self.fallback.name,
            model=self.model,
            api_shape=API_SHAPE,
            attempt=1,
            fallback_from=self.primary.name,
            fallback_reason=last_failure.code,
        )
        result, failure = await self._run_specialized_attempt(
            self.fallback, fallback_route, input_items, observer, invoke
        )
        if result is not None:
            return result
        assert failure is not None
        raise AgentModelRoutingError(failure)

    async def run_skill_plan(
        self,
        input_items: list[dict[str, Any]],
        style_context: dict[str, object],
        skill: RuntimeSkill,
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        async def invoke(config, route, items):
            return await self._invoke_skill_plan(config, route, items, style_context, skill)

        return await self._run_specialized(input_items, observer, invoke)

    async def run_skill_final(
        self,
        input_items: list[dict[str, Any]],
        skill: RuntimeSkill,
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        async def invoke(config, route, items):
            return await self._invoke_skill_final(config, route, items, skill)

        return await self._run_specialized(input_items, observer, invoke)

    async def run_with_skill(
        self,
        input_items: list[dict[str, Any]],
        skill: RuntimeSkill,
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        async def invoke(config, route, items):
            return await self._invoke_skill_text(config, route, items, skill)

        return await self._run_specialized(input_items, observer, invoke)

    async def run_skill_selection(
        self,
        input_items: list[dict[str, Any]],
        catalog: list[dict[str, object]],
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        async def invoke(config, route, items):
            return await self._invoke_skill_selection(config, route, items, catalog)

        return await self._run_specialized(input_items, observer, invoke)

    async def run_skill_authoring(
        self,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        return await self._run_specialized(
            input_items,
            observer,
            self._invoke_skill_authoring,
        )

    async def _run_attempt(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
    ) -> tuple[AgentModelResult | None, AgentModelFailure | None]:
        return await self._execute_attempt(
            config=config,
            route=route,
            input_items=input_items,
            observer=observer,
            invoke=self._invoke,
        )

    async def _execute_attempt(
        self,
        *,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
        invoke,
    ) -> tuple[AgentModelResult | None, AgentModelFailure | None]:
        run_id = getattr(observer, "run_id", None)
        with agent_span(
            "agent.model_call",
            agent_run_id=run_id,
            span_type="CHAT_MODEL",
            attributes={
                "provider": route.provider,
                "model": route.model,
                "api_shape": route.api_shape,
                "attempt": route.attempt,
                "fallback_from": route.fallback_from,
                "fallback_reason": route.fallback_reason,
            },
        ) as span:
            step_id = await observer.attempt_started(route)
            set_span_result(span, {"agent_step_id": step_id})
            started = time.perf_counter()
            try:
                run_token = _current_agent_run_id.set(run_id)
                try:
                    result = await invoke(config, route, input_items)
                finally:
                    _current_agent_run_id.reset(run_token)
            except Exception as exc:  # noqa: BLE001
                failure = classify_agent_model_error(
                    exc,
                    secrets=(self.primary.api_key, self.fallback.api_key),
                )
                latency_ms = round((time.perf_counter() - started) * 1000)
                await observer.attempt_failed(route, failure, latency_ms)
                set_span_result(
                    span,
                    {
                        "latency_ms": latency_ms,
                        "result_status": "failed",
                        "error_code": failure.code,
                        "error_summary": failure.safe_message,
                    },
                )
                set_span_status(span, "ERROR", agent_run_id=run_id)
                logger.warning(
                    "agent_model_attempt_failed provider=%s model=%s api_shape=%s attempt=%s "
                    "retryable=%s status_code=%s error_code=%s internal_error_ref=%s",
                    route.provider,
                    route.model,
                    route.api_shape,
                    route.attempt,
                    failure.retryable,
                    failure.status_code,
                    failure.code,
                    failure.internal_error_ref,
                )
                return None, failure
            latency_ms = round((time.perf_counter() - started) * 1000)
            await observer.attempt_succeeded(route, result, latency_ms)
            set_span_result(
                span,
                {
                    "latency_ms": latency_ms,
                    "result_status": "succeeded",
                    "provider_request_id": result.provider_request_id,
                    **result.usage,
                },
            )
            set_span_status(span, "OK", agent_run_id=run_id)
            return result, None

    async def run(
        self,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        last_failure: AgentModelFailure | None = None
        primary_attempts = 1 + self.settings.agent_primary_retry_attempts
        for attempt in range(1, primary_attempts + 1):
            route = AgentModelRoute(
                provider=self.primary.name,
                model=self.model,
                api_shape=API_SHAPE,
                attempt=attempt,
            )
            result, failure = await self._run_attempt(self.primary, route, input_items, observer)
            if result is not None:
                return result
            assert failure is not None
            last_failure = failure
            if not failure.retryable:
                raise AgentModelRoutingError(failure)
            if attempt < primary_attempts and self.settings.agent_retry_backoff_seconds:
                await asyncio.sleep(self.settings.agent_retry_backoff_seconds)

        assert last_failure is not None
        fallback_route = AgentModelRoute(
            provider=self.fallback.name,
            model=self.model,
            api_shape=API_SHAPE,
            attempt=1,
            fallback_from=self.primary.name,
            fallback_reason=last_failure.code,
        )
        result, failure = await self._run_attempt(self.fallback, fallback_route, input_items, observer)
        if result is not None:
            return result
        assert failure is not None
        raise AgentModelRoutingError(failure)
