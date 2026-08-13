import asyncio
import json
import unittest

import httpx
from agents import ModelSettings
from agents.models.interface import ModelTracing
from openai import AsyncOpenAI

from app.services.native_agent_chat import (
    NativeAgentChatMessageLimitError,
    SiliconFlowBoundedChatModel,
)


MODEL = "deepseek-ai/DeepSeek-V3.2"


class NativeAgentChatModelTests(unittest.TestCase):
    @staticmethod
    def _messages(count: int) -> list[dict[str, str]]:
        return [
            {"role": "user", "content": f"message-{index}"}
            for index in range(count)
        ]

    def test_ten_converted_messages_call_chat_with_bounded_parameters(self) -> None:
        requests: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-offline",
                    "object": "chat.completion",
                    "created": 1,
                    "model": MODEL,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        async def run() -> None:
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            client = AsyncOpenAI(
                api_key="offline-test",
                base_url="https://siliconflow.invalid/v1",
                max_retries=0,
                http_client=http_client,
            )
            observed: list[int] = []
            model = SiliconFlowBoundedChatModel(
                model=MODEL,
                openai_client=client,
                message_count_observer=observed.append,
            )
            await model._fetch_response(
                "system",
                self._messages(9),
                ModelSettings(
                    store=None,
                    parallel_tool_calls=None,
                    include_usage=None,
                    extra_body={"enable_thinking": False},
                ),
                [],
                None,
                [],
                None,
                ModelTracing.DISABLED,
                stream=False,
            )
            self.assertEqual([10], observed)
            await client.close()

        asyncio.run(run())
        self.assertEqual(1, len(requests))
        body = requests[0]
        self.assertEqual(MODEL, body["model"])
        self.assertEqual(False, body["enable_thinking"])
        self.assertNotIn("store", body)
        self.assertNotIn("parallel_tool_calls", body)
        self.assertNotIn("stream_options", body)

    def test_eleven_converted_messages_fail_before_client_call(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(500)

        async def run() -> None:
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            client = AsyncOpenAI(
                api_key="offline-test",
                base_url="https://siliconflow.invalid/v1",
                max_retries=0,
                http_client=http_client,
            )
            observed: list[int] = []
            model = SiliconFlowBoundedChatModel(
                model=MODEL,
                openai_client=client,
                message_count_observer=observed.append,
            )
            original = self._messages(10)
            with self.assertRaises(NativeAgentChatMessageLimitError):
                await model._fetch_response(
                    "system",
                    original,
                    ModelSettings(extra_body={"enable_thinking": False}),
                    [],
                    None,
                    [],
                    None,
                    ModelTracing.DISABLED,
                    stream=False,
                )
            self.assertEqual([11], observed)
            self.assertEqual(self._messages(10), original)
            await client.close()

        asyncio.run(run())
        self.assertEqual(0, calls)


if __name__ == "__main__":
    unittest.main()
