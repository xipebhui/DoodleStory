from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from agents.models.interface import ModelProvider
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI

from app.core.config import Settings
from app.services.native_agent_chat import (
    ChatMessageCountObserver,
    SiliconFlowBoundedChatProvider,
)

if TYPE_CHECKING:
    from app.models.entities import NativeAgentRun


HUOMIAO_RESPONSES_ROUTE = "huomiao_responses"
HUOMIAO_PROVIDER = "huomiao"
RESPONSES_API_SHAPE = "responses"
SILICONFLOW_CHAT_ROUTE = "siliconflow_chat_v1"
SILICONFLOW_PROVIDER = "siliconflow"
CHAT_COMPLETIONS_API_SHAPE = "chat_completions"
SILICONFLOW_NATIVE_AGENT_MODEL = "deepseek-ai/DeepSeek-V3.2"


class NativeAgentModelRouteError(RuntimeError):
    """Base error for fail-closed Native Agent model routing."""


class NativeAgentModelRouteConfigError(NativeAgentModelRouteError):
    """Raised when the selected route cannot be created from deployment config."""


class NativeAgentModelRouteSnapshotError(NativeAgentModelRouteError):
    """Raised when persisted Run routing facts are unknown or contradictory."""


@dataclass(frozen=True)
class NativeAgentModelRouteSnapshot:
    route: str
    provider: str
    api_shape: str
    model: str


@dataclass(frozen=True)
class NativeAgentModelProviderBinding:
    snapshot: NativeAgentModelRouteSnapshot
    client: AsyncOpenAI
    provider: ModelProvider


def _validated_connection(
    *,
    api_key: str,
    base_url: str,
    api_key_name: str,
    base_url_name: str,
) -> tuple[str, str]:
    api_key = api_key.strip()
    if not api_key:
        raise NativeAgentModelRouteConfigError(
            f"Native Agent 路由配置缺失：{api_key_name}"
        )

    base_url = base_url.strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        parsed.port
    except ValueError as exc:
        raise NativeAgentModelRouteConfigError(
            f"Native Agent 路由配置无效：{base_url_name}"
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise NativeAgentModelRouteConfigError(
            f"Native Agent 路由配置无效：{base_url_name}"
        )
    return api_key, base_url


def _validated_huomiao_connection(settings: Settings) -> tuple[str, str]:
    return _validated_connection(
        api_key=settings.text_fallback_api_key,
        base_url=settings.text_fallback_openai_base_url,
        api_key_name="TEXT_FALLBACK_API_KEY",
        base_url_name="TEXT_FALLBACK_BASE_URL",
    )


def _validated_siliconflow_connection(settings: Settings) -> tuple[str, str]:
    return _validated_connection(
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url,
        api_key_name="SILICONFLOW_API_KEY",
        base_url_name="SILICONFLOW_BASE_URL",
    )


def resolve_default_native_agent_model_route(
    settings: Settings,
) -> NativeAgentModelRouteSnapshot:
    route = settings.native_agent_default_route.strip()
    if route != HUOMIAO_RESPONSES_ROUTE:
        raise NativeAgentModelRouteConfigError(
            "Native Agent 默认路由不受支持：NATIVE_AGENT_DEFAULT_ROUTE"
        )
    model = settings.native_agent_huomiao_model.strip()
    if not model:
        raise NativeAgentModelRouteConfigError(
            "Native Agent 路由配置缺失：NATIVE_AGENT_HUOMIAO_MODEL"
        )
    _validated_huomiao_connection(settings)
    return NativeAgentModelRouteSnapshot(
        route=HUOMIAO_RESPONSES_ROUTE,
        provider=HUOMIAO_PROVIDER,
        api_shape=RESPONSES_API_SHAPE,
        model=model,
    )


def resolve_native_agent_model_route(
    settings: Settings,
    *,
    requested_route: str | None,
) -> NativeAgentModelRouteSnapshot:
    if requested_route is None or requested_route == HUOMIAO_RESPONSES_ROUTE:
        return resolve_default_native_agent_model_route(settings)
    if requested_route != SILICONFLOW_CHAT_ROUTE:
        raise NativeAgentModelRouteConfigError(
            "Native Agent 显式模型路由不受支持"
        )
    model = settings.native_agent_siliconflow_model.strip()
    if model != SILICONFLOW_NATIVE_AGENT_MODEL:
        raise NativeAgentModelRouteConfigError(
            "NATIVE_AGENT_SILICONFLOW_MODEL 必须固定为 "
            f"{SILICONFLOW_NATIVE_AGENT_MODEL}"
        )
    _validated_siliconflow_connection(settings)
    return NativeAgentModelRouteSnapshot(
        route=SILICONFLOW_CHAT_ROUTE,
        provider=SILICONFLOW_PROVIDER,
        api_shape=CHAT_COMPLETIONS_API_SHAPE,
        model=model,
    )


def resolve_native_agent_run_model_provider(
    run: NativeAgentRun,
    *,
    settings: Settings,
    chat_message_count_observer: ChatMessageCountObserver | None = None,
) -> NativeAgentModelProviderBinding:
    snapshot = NativeAgentModelRouteSnapshot(
        route=run.model_route_snapshot.strip(),
        provider=run.model_provider_snapshot.strip(),
        api_shape=run.model_api_shape_snapshot.strip(),
        model=run.model_snapshot.strip(),
    )
    if not snapshot.model:
        raise NativeAgentModelRouteSnapshotError(
            "Native Agent Run 的模型快照为空"
        )
    route_tuple = (
        snapshot.route,
        snapshot.provider,
        snapshot.api_shape,
    )
    if route_tuple == (
        HUOMIAO_RESPONSES_ROUTE,
        HUOMIAO_PROVIDER,
        RESPONSES_API_SHAPE,
    ):
        api_key, base_url = _validated_huomiao_connection(settings)
        use_siliconflow_chat = False
    elif route_tuple == (
        SILICONFLOW_CHAT_ROUTE,
        SILICONFLOW_PROVIDER,
        CHAT_COMPLETIONS_API_SHAPE,
    ):
        if snapshot.model != SILICONFLOW_NATIVE_AGENT_MODEL:
            raise NativeAgentModelRouteSnapshotError(
                "SiliconFlow Native Agent Run 的模型快照不受支持"
            )
        if chat_message_count_observer is None:
            raise NativeAgentModelRouteSnapshotError(
                "SiliconFlow Chat 路由缺少消息预检观察器"
            )
        api_key, base_url = _validated_siliconflow_connection(settings)
        use_siliconflow_chat = True
    else:
        raise NativeAgentModelRouteSnapshotError(
            "Native Agent Run 的模型路由快照未知或互相矛盾"
        )
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
        timeout=settings.agent_request_timeout_seconds,
    )
    provider: ModelProvider
    if use_siliconflow_chat:
        if chat_message_count_observer is None:
            raise NativeAgentModelRouteSnapshotError(
                "SiliconFlow Chat 路由缺少消息预检观察器"
            )
        provider = SiliconFlowBoundedChatProvider(
            openai_client=client,
            expected_model=snapshot.model,
            message_count_observer=chat_message_count_observer,
        )
    else:
        provider = OpenAIProvider(openai_client=client, use_responses=True)
    return NativeAgentModelProviderBinding(
        snapshot=snapshot,
        client=client,
        provider=provider,
    )
