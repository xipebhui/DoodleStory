from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents.exceptions import UserError
from agents.models.chatcmpl_converter import Converter
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI


SILICONFLOW_CHAT_MESSAGE_LIMIT = 10
ChatMessageCountObserver = Callable[[int], None]


class NativeAgentChatError(RuntimeError):
    """Base error for the bounded Native Agent Chat route."""


class NativeAgentChatMessageLimitError(NativeAgentChatError):
    """Raised before HTTP when converted Chat messages exceed the route limit."""


class SiliconFlowBoundedChatModel(OpenAIChatCompletionsModel):
    def __init__(
        self,
        *,
        model: str,
        openai_client: AsyncOpenAI,
        message_count_observer: ChatMessageCountObserver,
    ) -> None:
        super().__init__(
            model=model,
            openai_client=openai_client,
            strict_feature_validation=True,
            buffer_streamed_tool_calls=False,
        )
        self._message_count_observer = message_count_observer

    def converted_message_count(
        self,
        *,
        system_instructions: str | None,
        input_items: Any,
    ) -> int:
        converted = Converter.items_to_messages(
            input_items,
            model=self.model,
            base_url=str(self._client.base_url),
            should_replay_reasoning_content=self.should_replay_reasoning_content,
            strict_feature_validation=True,
        )
        return len(converted) + (1 if system_instructions else 0)

    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: Any,
        model_settings: Any,
        tools: Any,
        output_schema: Any,
        handoffs: Any,
        span: Any,
        tracing: Any,
        stream: bool = False,
        prompt: Any = None,
    ) -> Any:
        count = self.converted_message_count(
            system_instructions=system_instructions,
            input_items=input,
        )
        self._message_count_observer(count)
        if count > SILICONFLOW_CHAT_MESSAGE_LIMIT:
            raise NativeAgentChatMessageLimitError(
                "SiliconFlow Chat 转换后消息数量超过 10 条；"
                "拒绝截断、摘要或删除上下文"
            )
        return await super()._fetch_response(
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            span,
            tracing,
            stream=stream,
            prompt=prompt,
        )


class SiliconFlowBoundedChatProvider(OpenAIProvider):
    def __init__(
        self,
        *,
        openai_client: AsyncOpenAI,
        expected_model: str,
        message_count_observer: ChatMessageCountObserver,
    ) -> None:
        super().__init__(
            openai_client=openai_client,
            use_responses=False,
            strict_feature_validation=True,
            buffer_streamed_tool_calls=False,
        )
        self._expected_model = expected_model
        self._message_count_observer = message_count_observer

    def get_model(
        self,
        model_name: str | None,
    ) -> SiliconFlowBoundedChatModel:
        if model_name != self._expected_model:
            raise UserError(
                "SiliconFlow Chat Provider 只接受 Run 中固定的显式模型"
            )
        return SiliconFlowBoundedChatModel(
            model=self._expected_model,
            openai_client=self._get_client(),
            message_count_observer=self._message_count_observer,
        )
