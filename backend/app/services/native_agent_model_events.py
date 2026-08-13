from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any

from agents.models.fake_id import FAKE_RESPONSES_ID

if TYPE_CHECKING:
    from app.services.native_agent_model_routes import NativeAgentModelRouteSnapshot
    from app.services.native_agent_persistence import NativeAgentStore


class NativeModelEventAdapterError(RuntimeError):
    """Raised when SDK model events cannot be mapped without ambiguity."""


@dataclass
class _FunctionCallState:
    output_index: int
    item_id: str
    tool_call_id: str
    name: str
    pending_arguments: str = ""
    all_arguments: str = ""
    completed_arguments: str | None = None
    last_flush_at: float = field(default_factory=time.monotonic)


@dataclass
class _ModelCallState:
    model_call_id: str
    ordinal: int
    started_at: float
    provider_response_id: str | None
    converted_message_count: int | None
    text_delta_buffer: str = ""
    last_text_flush_at: float = field(default_factory=time.monotonic)
    functions: dict[int, _FunctionCallState] = field(default_factory=dict)
    sdk_item_indexes: dict[str, int] = field(default_factory=dict)


class NativeModelEventAdapter:
    def __init__(
        self,
        *,
        run_id: str,
        execution_attempt: int,
        route: NativeAgentModelRouteSnapshot,
        store: NativeAgentStore,
    ) -> None:
        self._run_id = run_id
        self._execution_attempt = execution_attempt
        self._route = route
        self._store = store
        self._ordinal = 0
        self._current: _ModelCallState | None = None
        self._pending_converted_message_count: int | None = None

    def record_converted_message_count(self, count: int) -> None:
        if count < 0:
            raise NativeModelEventAdapterError("转换后消息数量不能为负数")
        if (
            self._current is not None
            or self._pending_converted_message_count is not None
        ):
            raise NativeModelEventAdapterError("模型消息预检与前一调用发生重叠")
        self._pending_converted_message_count = count
        self._store.append_event(
            "model.request.preflight",
            {
                "model_route": self._route.route,
                "model_provider": self._route.provider,
                "model_api_shape": self._route.api_shape,
                "converted_message_count": count,
            },
        )

    @staticmethod
    def _safe_provider_response_id(value: object) -> str | None:
        candidate = str(value or "").strip()
        if not candidate or candidate == FAKE_RESPONSES_ID:
            return None
        return candidate

    @classmethod
    def _item_provider_response_id(cls, item: object) -> str | None:
        provider_data = getattr(item, "provider_data", None)
        if not isinstance(provider_data, dict):
            return None
        return cls._safe_provider_response_id(provider_data.get("response_id"))

    def _require_current(self) -> _ModelCallState:
        if self._current is None:
            raise NativeModelEventAdapterError("模型事件缺少 response.created")
        return self._current

    def _register_provider_response_id(
        self,
        state: _ModelCallState,
        candidate: str | None,
    ) -> None:
        if candidate is None:
            return
        if (
            state.provider_response_id is not None
            and state.provider_response_id != candidate
        ):
            raise NativeModelEventAdapterError(
                "同一模型调用出现互相冲突的 Provider response ID"
            )
        if state.provider_response_id is None:
            state.provider_response_id = candidate
            self._store.set_model_step_provider_response_id(
                state.model_call_id,
                provider_response_id=candidate,
            )

    def _scan_response_provider_ids(
        self,
        state: _ModelCallState,
        response: object,
    ) -> None:
        self._register_provider_response_id(
            state,
            self._safe_provider_response_id(getattr(response, "id", None)),
        )
        for item in getattr(response, "output", None) or []:
            self._register_provider_response_id(
                state,
                self._item_provider_response_id(item),
            )

    def _flush_text(self, state: _ModelCallState) -> None:
        if not state.text_delta_buffer:
            return
        self._store.append_response_text_delta(
            state.model_call_id,
            state.text_delta_buffer,
        )
        state.text_delta_buffer = ""
        state.last_text_flush_at = time.monotonic()

    def _flush_arguments(
        self,
        state: _ModelCallState,
        function: _FunctionCallState,
    ) -> None:
        if not function.pending_arguments:
            return
        self._store.append_function_call_arguments_delta(
            response_id=state.model_call_id,
            item_id=function.item_id,
            tool_call_id=function.tool_call_id,
            name=function.name,
            delta=function.pending_arguments,
        )
        function.pending_arguments = ""
        function.last_flush_at = time.monotonic()

    def _resolve_output_index(self, raw_event: object) -> int:
        raw_index = getattr(raw_event, "output_index", None)
        if raw_index is not None:
            return int(raw_index)
        state = self._require_current()
        sdk_item_id = str(getattr(raw_event, "item_id", "") or "")
        if sdk_item_id and sdk_item_id in state.sdk_item_indexes:
            return state.sdk_item_indexes[sdk_item_id]
        raise NativeModelEventAdapterError(
            "Function Call 事件缺少可解析的 output index"
        )

    def _complete_function(
        self,
        state: _ModelCallState,
        function: _FunctionCallState,
        *,
        arguments: str,
    ) -> None:
        self._flush_arguments(state, function)
        if function.all_arguments != arguments:
            raise NativeModelEventAdapterError(
                "Function Call 累计参数与完成参数不一致"
            )
        if function.completed_arguments is not None:
            if function.completed_arguments != arguments:
                raise NativeModelEventAdapterError(
                    "Function Call 收到互相冲突的完成参数"
                )
            return
        self._store.complete_function_call_arguments(
            response_id=state.model_call_id,
            item_id=function.item_id,
            tool_call_id=function.tool_call_id,
            name=function.name,
            arguments=arguments,
        )
        function.completed_arguments = arguments

    def _start_model_call(self, raw_event: object) -> None:
        if self._current is not None:
            raise NativeModelEventAdapterError("前一模型调用尚未完成")
        self._ordinal += 1
        model_call_id = (
            f"native:{self._run_id}:attempt:{self._execution_attempt}:"
            f"call:{self._ordinal}"
        )
        response = raw_event.response
        provider_response_id = self._safe_provider_response_id(
            getattr(response, "id", None)
        )
        state = _ModelCallState(
            model_call_id=model_call_id,
            ordinal=self._ordinal,
            started_at=time.perf_counter(),
            provider_response_id=provider_response_id,
            converted_message_count=self._pending_converted_message_count,
        )
        self._pending_converted_message_count = None
        self._store.start_model_step(
            model_call_id=model_call_id,
            model_provider=self._route.provider,
            model_api_shape=self._route.api_shape,
            model_name=self._route.model,
            provider_response_id=provider_response_id,
            execution_attempt=self._execution_attempt,
            model_call_ordinal=self._ordinal,
            converted_message_count=state.converted_message_count,
        )
        self._current = state

    def handle(self, raw_event: object) -> None:
        raw_type = str(getattr(raw_event, "type", "") or "")
        if raw_type == "response.created":
            self._start_model_call(raw_event)
            return

        state = self._require_current()
        if raw_type == "response.output_text.delta":
            state.text_delta_buffer += str(raw_event.delta)
            now = time.monotonic()
            if (
                len(state.text_delta_buffer) >= 80
                or now - state.last_text_flush_at >= 0.25
            ):
                self._flush_text(state)
            return

        if raw_type == "response.output_item.added":
            item = raw_event.item
            self._register_provider_response_id(
                state,
                self._item_provider_response_id(item),
            )
            if getattr(item, "type", "") != "function_call":
                return
            output_index = int(raw_event.output_index)
            if output_index in state.functions:
                raise NativeModelEventAdapterError(
                    "同一模型调用出现重复 Function Call output index"
                )
            tool_call_id = str(getattr(item, "call_id", "") or "").strip()
            name = str(getattr(item, "name", "") or "").strip()
            if not tool_call_id or not name:
                raise NativeModelEventAdapterError(
                    "Function Call 缺少真实 call ID 或工具名称"
                )
            item_id = f"{state.model_call_id}:output:{output_index}"
            function = _FunctionCallState(
                output_index=output_index,
                item_id=item_id,
                tool_call_id=tool_call_id,
                name=name,
            )
            state.functions[output_index] = function
            sdk_item_id = str(getattr(item, "id", "") or "")
            if sdk_item_id and sdk_item_id != FAKE_RESPONSES_ID:
                if sdk_item_id in state.sdk_item_indexes:
                    raise NativeModelEventAdapterError(
                        "同一模型调用出现重复 SDK Item ID"
                    )
                state.sdk_item_indexes[sdk_item_id] = output_index
            self._store.start_function_call(
                response_id=state.model_call_id,
                item_id=item_id,
                tool_call_id=tool_call_id,
                name=name,
                output_index=output_index,
            )
            return

        if raw_type == "response.function_call_arguments.delta":
            output_index = self._resolve_output_index(raw_event)
            function = state.functions.get(output_index)
            if function is None:
                raise NativeModelEventAdapterError(
                    "Function Call 参数事件没有对应的开始事件"
                )
            delta = str(raw_event.delta)
            function.pending_arguments += delta
            function.all_arguments += delta
            now = time.monotonic()
            if (
                len(function.pending_arguments) >= 80
                or now - function.last_flush_at >= 0.25
            ):
                self._flush_arguments(state, function)
            return

        if raw_type == "response.function_call_arguments.done":
            output_index = self._resolve_output_index(raw_event)
            function = state.functions.get(output_index)
            if function is None:
                raise NativeModelEventAdapterError(
                    "Function Call 完成事件没有对应的开始事件"
                )
            self._complete_function(
                state,
                function,
                arguments=str(raw_event.arguments),
            )
            return

        if raw_type == "response.output_item.done":
            item = raw_event.item
            self._register_provider_response_id(
                state,
                self._item_provider_response_id(item),
            )
            if getattr(item, "type", "") != "function_call":
                return
            output_index = int(raw_event.output_index)
            function = state.functions.get(output_index)
            if function is None:
                raise NativeModelEventAdapterError(
                    "Function Call Item 完成事件没有对应的开始事件"
                )
            if str(getattr(item, "call_id", "") or "") != function.tool_call_id:
                raise NativeModelEventAdapterError(
                    "Function Call Item 的 call ID 在流中发生变化"
                )
            self._complete_function(
                state,
                function,
                arguments=str(getattr(item, "arguments", "") or ""),
            )
            return

        if raw_type == "response.completed":
            self._flush_text(state)
            for function in state.functions.values():
                self._flush_arguments(state, function)
                if function.completed_arguments is None:
                    raise NativeModelEventAdapterError(
                        "模型调用完成前仍有 Function Call 参数未完成"
                    )
            response = raw_event.response
            self._scan_response_provider_ids(state, response)
            usage = getattr(response, "usage", None)
            usage_payload = (
                usage.model_dump(mode="json")
                if usage is not None and hasattr(usage, "model_dump")
                else None
            )
            latency_ms = round((time.perf_counter() - state.started_at) * 1000)
            self._store.complete_model_step(
                state.model_call_id,
                provider_response_id=state.provider_response_id,
                usage=usage_payload,
                latency_ms=latency_ms,
            )
            self._current = None

    def finish(self) -> None:
        if self._current is not None:
            raise NativeModelEventAdapterError(
                "模型事件流结束时仍有未完成的模型调用"
            )
        if self._pending_converted_message_count is not None:
            raise NativeModelEventAdapterError(
                "模型消息预检后没有收到 response.created"
            )
