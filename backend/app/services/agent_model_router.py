from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
import time
from typing import Any, Protocol

from agents import Agent, ModelSettings, RunConfig, Runner
from agents.model_settings import ModelRetrySettings
from agents.models.openai_provider import OpenAIProvider
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

from app.core.config import Settings, get_settings
from app.schemas.agent import ComicPlan


logger = logging.getLogger(__name__)
API_SHAPE = "responses"
MAX_SAFE_ERROR_CHARS = 500


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
    async def attempt_started(self, route: AgentModelRoute) -> None: ...

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
            name="ComicDirectorAgent",
            instructions=(
                "你是 DoodleStory 的漫画导演 Agent。本阶段只理解用户意图并提供清晰的文本回答。"
                "不要调用工具，不要声称已经生成图片、任务、分镜或其他资源；当用户要求执行这些能力时，"
                "明确说明当前回合只能讨论和整理创作需求。不要输出内部思维过程。"
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
        request_ids = [
            response.request_id
            for response in raw_responses
            if getattr(response, "request_id", None)
        ]
        return AgentModelResult(
            final_output=final_output,
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=request_ids[-1] if request_ids else None,
            raw_result=result,
            route=route,
        )

    async def _invoke_comic_plan(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        style_context: dict[str, object],
    ) -> AgentModelResult:
        agent = Agent(
            name="ComicDirectorAgent",
            instructions=(
                "你是 DoodleStory 的漫画导演。根据用户 Idea 和已鉴权风格，直接规划一部固定两格的连续漫画。"
                "两格必须共享同一事件、人物状态和视觉语境：panel-1 建立动作或矛盾，panel-2 给出紧接着的推进、"
                "反应或结果，不能是两个互不相关的插画。image_prompt 是将直接交给图片模型的最终单图指令，"
                "必须完整但简洁，明确主体、动作、表情、场景、构图、光线、风格和需要准确绘制的文字；"
                "不要解释计划，不要输出内部思维过程，不要提及旧 Pipeline。严格输出 ComicPlan schema。\n"
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
                    workflow_name="DoodleStory ComicPlan",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        plan = ComicPlan.model_validate(result.final_output)
        raw_responses = list(result.raw_responses)
        request_ids = [
            response.request_id
            for response in raw_responses
            if getattr(response, "request_id", None)
        ]
        return AgentModelResult(
            final_output=plan.model_dump_json(),
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=request_ids[-1] if request_ids else None,
            raw_result=result,
            route=route,
            structured_output=plan,
        )

    async def _invoke_comic_final(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
    ) -> AgentModelResult:
        agent = Agent(
            name="ComicDirectorAgent",
            instructions=(
                "你是 DoodleStory 的漫画导演。应用上下文已经包含本轮 ComicPlan 和两次 generate_image Tool Output。"
                "只根据这些真实状态给用户一句简洁结果说明：全部成功时说明两格漫画已完成；存在失败时明确指出"
                "失败的格数与可见原因，绝不能把失败说成成功。不要输出内部思维过程，不要声称进行了图片检查或重试。"
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
                    workflow_name="DoodleStory Comic Result",
                ),
                max_turns=2,
            )
        finally:
            await provider._client.close()
        final_output = str(result.final_output or "").strip()
        if not final_output:
            raise ValueError("Agent model returned an empty comic result response")
        raw_responses = list(result.raw_responses)
        request_ids = [
            response.request_id
            for response in raw_responses
            if getattr(response, "request_id", None)
        ]
        return AgentModelResult(
            final_output=final_output,
            usage=summarize_agent_usage(raw_responses),
            provider_request_id=request_ids[-1] if request_ids else None,
            raw_result=result,
            route=route,
        )

    async def _run_specialized_attempt(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
        invoke,
    ) -> tuple[AgentModelResult | None, AgentModelFailure | None]:
        await observer.attempt_started(route)
        started = time.perf_counter()
        try:
            result = await invoke(config, route, input_items)
        except Exception as exc:  # noqa: BLE001
            failure = classify_agent_model_error(
                exc,
                secrets=(self.primary.api_key, self.fallback.api_key),
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            await observer.attempt_failed(route, failure, latency_ms)
            return None, failure
        latency_ms = round((time.perf_counter() - started) * 1000)
        await observer.attempt_succeeded(route, result, latency_ms)
        return result, None

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

    async def run_comic_plan(
        self,
        input_items: list[dict[str, Any]],
        style_context: dict[str, object],
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        async def invoke(config, route, items):
            return await self._invoke_comic_plan(config, route, items, style_context)

        return await self._run_specialized(input_items, observer, invoke)

    async def run_comic_final(
        self,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
    ) -> AgentModelResult:
        return await self._run_specialized(input_items, observer, self._invoke_comic_final)

    async def _run_attempt(
        self,
        config: AgentProviderConfig,
        route: AgentModelRoute,
        input_items: list[dict[str, Any]],
        observer: AgentModelAttemptObserver,
    ) -> tuple[AgentModelResult | None, AgentModelFailure | None]:
        await observer.attempt_started(route)
        started = time.perf_counter()
        try:
            result = await self._invoke(config, route, input_items)
        except Exception as exc:  # noqa: BLE001
            failure = classify_agent_model_error(
                exc,
                secrets=(self.primary.api_key, self.fallback.api_key),
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            await observer.attempt_failed(route, failure, latency_ms)
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
