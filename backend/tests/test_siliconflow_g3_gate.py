import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agents.models.fake_id import FAKE_RESPONSES_ID
import httpx
from openai import AsyncOpenAI
from sqlalchemy import create_engine

from app.core.config import Settings
from app.core.database import Base
from app.services.native_agent_chat import SiliconFlowBoundedChatProvider
from app.services.native_agent_g3_gate import (
    G3ClientBinding,
    LOCKED_PROBE_INPUT,
    LOCKED_PROBE_OUTPUT,
    create_probe_run,
    evaluate_z1,
    evaluate_z2,
    evaluate_z3,
    evaluate_z4,
    security_scan,
    initialize_probe_tables,
    make_session_factory,
    run_z1,
    run_z2_stage_a,
    run_z2_stage_b,
    sqlite_url,
    validate_report,
    z3_input_items,
    z4_input_items,
)


def model_step(
    call_id: str,
    provider_id: str,
    *,
    message_count: int,
) -> dict[str, object]:
    return {
        "step_id": f"step-{call_id}",
        "model_call_id": call_id,
        "provider_response_id": provider_id,
        "converted_message_count": message_count,
        "latency_ms": 10,
        "status": "succeeded",
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        "execution_attempt": 1,
        "model_call_ordinal": 1,
    }


class SiliconFlowG3GateTests(unittest.TestCase):
    @staticmethod
    def _mock_binding(handler, observer) -> G3ClientBinding:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = AsyncOpenAI(
            api_key="offline-g3",
            base_url="https://siliconflow.invalid/v1",
            max_retries=0,
            http_client=http_client,
        )
        provider = SiliconFlowBoundedChatProvider(
            openai_client=client,
            expected_model="deepseek-ai/DeepSeek-V3.2",
            message_count_observer=observer,
        )
        return G3ClientBinding(client, http_client, provider)

    def test_z1_exercises_real_sdk_stream_adapter_with_mock_http(self) -> None:
        async def run() -> dict[str, object]:
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = Path(temp_dir) / "g3.db"
                engine = create_engine(sqlite_url(db_path))
                Base.metadata.create_all(engine)
                initialize_probe_tables(db_path)
                session_factory = make_session_factory(db_path)
                run_id = create_probe_run(session_factory, case_id="z1-mock")

                def handler(_request: httpx.Request) -> httpx.Response:
                    lines = [
                        {
                            "id": "chatcmpl-g3-z1",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": "deepseek-ai/DeepSeek-V3.2",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": "G3-"},
                                    "finish_reason": None,
                                }
                            ],
                        },
                        {
                            "id": "chatcmpl-g3-z1",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": "deepseek-ai/DeepSeek-V3.2",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": "TEXT-OK"},
                                    "finish_reason": "stop",
                                }
                            ],
                        },
                        {
                            "id": "chatcmpl-g3-z1",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": "deepseek-ai/DeepSeek-V3.2",
                            "choices": [],
                            "usage": {
                                "prompt_tokens": 4,
                                "completion_tokens": 2,
                                "total_tokens": 6,
                            },
                        },
                    ]
                    body = "".join(
                        f"data: {json.dumps(line)}\n\n" for line in lines
                    ) + "data: [DONE]\n\n"
                    return httpx.Response(
                        200,
                        content=body.encode("utf-8"),
                        headers={"content-type": "text/event-stream"},
                    )

                def fake_binding(**kwargs) -> G3ClientBinding:
                    return self._mock_binding(
                        handler,
                        kwargs["message_count_observer"],
                    )

                with patch(
                    "app.services.native_agent_g3_gate.make_client_binding",
                    side_effect=fake_binding,
                ):
                    summary = await run_z1(db_path, run_id=run_id)
                session_factory.kw["bind"].dispose()
                engine.dispose()
                return summary

        import asyncio

        summary = asyncio.run(run())
        self.assertEqual("G3-TEXT-OK", summary["final_output"])
        self.assertEqual("chatcmpl-g3-z1", summary["model_steps"][0]["provider_response_id"])
        self.assertEqual(6, summary["model_steps"][0]["usage"]["total_tokens"])

    def test_z2_persists_tool_output_and_resumes_without_reexecution(self) -> None:
        def sse_response(lines: list[dict[str, object]]) -> httpx.Response:
            body = "".join(
                f"data: {json.dumps(line)}\n\n" for line in lines
            ) + "data: [DONE]\n\n"
            return httpx.Response(
                200,
                content=body.encode("utf-8"),
                headers={"content-type": "text/event-stream"},
            )

        def stage_a_handler(_request: httpx.Request) -> httpx.Response:
            common = {
                "id": "chatcmpl-g3-z2a",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "deepseek-ai/DeepSeek-V3.2",
            }
            return sse_response(
                [
                    {
                        **common,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call-g3-echo",
                                            "type": "function",
                                            "function": {
                                                "name": "echo_probe",
                                                "arguments": '{"probe_id":"g3-echo-01",',
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        **common,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "function": {
                                                "arguments": '"value":"PAYNES-CREEK-G3"}',
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                    },
                    {
                        **common,
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 8,
                            "completion_tokens": 4,
                            "total_tokens": 12,
                        },
                    },
                ]
            )

        def stage_b_handler(_request: httpx.Request) -> httpx.Response:
            return sse_response(
                [
                    {
                        "id": "chatcmpl-g3-z2b",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": "deepseek-ai/DeepSeek-V3.2",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": "G3-TOOL-OK PAYNES-CREEK-G3",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-g3-z2b",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": "deepseek-ai/DeepSeek-V3.2",
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 12,
                            "completion_tokens": 4,
                            "total_tokens": 16,
                        },
                    },
                ]
            )

        async def run() -> tuple[dict[str, object], dict[str, object]]:
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = Path(temp_dir) / "g3.db"
                engine = create_engine(sqlite_url(db_path))
                Base.metadata.create_all(engine)
                initialize_probe_tables(db_path)
                session_factory = make_session_factory(db_path)
                run_id = create_probe_run(
                    session_factory,
                    case_id="z2-mock",
                    tool_names=["echo_probe"],
                )

                def stage_a_binding(**kwargs) -> G3ClientBinding:
                    return self._mock_binding(
                        stage_a_handler,
                        kwargs["message_count_observer"],
                    )

                with patch(
                    "app.services.native_agent_g3_gate.make_client_binding",
                    side_effect=stage_a_binding,
                ):
                    stage_a = await run_z2_stage_a(db_path, run_id=run_id)

                def stage_b_binding(**kwargs) -> G3ClientBinding:
                    return self._mock_binding(
                        stage_b_handler,
                        kwargs["message_count_observer"],
                    )

                with patch(
                    "app.services.native_agent_g3_gate.make_client_binding",
                    side_effect=stage_b_binding,
                ):
                    stage_b = await run_z2_stage_b(db_path, run_id=run_id)
                session_factory.kw["bind"].dispose()
                engine.dispose()
                return stage_a, stage_b

        import asyncio

        stage_a, stage_b = asyncio.run(run())
        self.assertEqual(2, len(stage_b["all_model_steps"]))
        self.assertEqual(1, len(stage_b["tool_steps"]))
        self.assertEqual("call-g3-echo", stage_b["tool_steps"][0]["tool_call_id"])
        self.assertIn("PAYNES-CREEK-G3", stage_b["final_output"])

    def test_fixed_message_inputs_have_expected_counts(self) -> None:
        self.assertEqual(9, len(z3_input_items()))
        self.assertEqual(10, len(z4_input_items()))

    def test_z1_and_z3_require_provider_identity_usage_and_markers(self) -> None:
        z1 = {
            "model_steps": [model_step("call-z1", "chatcmpl-z1", message_count=2)],
            "event_counts": {
                "response.output_text.delta": 1,
                "response.completed": 1,
            },
            "final_output": "G3-TEXT-OK",
        }
        self.assertTrue(evaluate_z1(z1, 1))
        z1["model_steps"][0]["provider_response_id"] = FAKE_RESPONSES_ID
        self.assertFalse(evaluate_z1(z1, 1))

        z3 = {
            "model_steps": [model_step("call-z3", "chatcmpl-z3", message_count=10)],
            "event_counts": {"response.completed": 1},
            "final_output": "G3-MSG10-OK",
        }
        self.assertTrue(evaluate_z3(z3, 1))
        z3["model_steps"][0]["converted_message_count"] = 9
        self.assertFalse(evaluate_z3(z3, 1))

    def test_z2_requires_distinct_processes_stable_tool_and_one_execution(self) -> None:
        arguments = json.dumps(LOCKED_PROBE_INPUT, separators=(",", ":"))
        z2a = {
            "process_fingerprint": "process-a",
            "model_steps": [model_step("call-a", "chatcmpl-a", message_count=2)],
            "function_events": [
                {
                    "type": "response.function_call.arguments.delta",
                    "payload": {
                        "delta": arguments,
                        "tool_call_id": "tool-1",
                    },
                },
                {
                    "type": "response.function_call.arguments.done",
                    "payload": {
                        "arguments": arguments,
                        "tool_call_id": "tool-1",
                    },
                },
            ],
            "final_output": json.dumps(LOCKED_PROBE_OUTPUT),
        }
        z2b = {
            "process_fingerprint": "process-b",
            "model_steps": [model_step("call-b", "chatcmpl-b", message_count=5)],
            "tool_steps": [
                {
                    "name": "echo_probe",
                    "status": "succeeded",
                    "tool_call_id": "tool-1",
                    "input": LOCKED_PROBE_INPUT,
                    "output": {"output": LOCKED_PROBE_OUTPUT},
                }
            ],
            "final_output": "G3-TOOL-OK PAYNES-CREEK-G3",
        }
        self.assertTrue(evaluate_z2(z2a, z2b, 2))
        z2b["tool_steps"].append(dict(z2b["tool_steps"][0]))
        self.assertFalse(evaluate_z2(z2a, z2b, 2))

    def test_z4_accepts_documented_provider_boundary_outcomes_only(self) -> None:
        accepted = {
            "converted_message_count": 11,
            "production_wrapper_decision": "rejected_before_http",
            "provider_outcome": "accepted",
            "provider_response_id": "chatcmpl-z4",
            "terminal_event_count": 1,
            "usage": {"total_tokens": 2},
            "nonempty_text_observed": True,
        }
        self.assertTrue(evaluate_z4(accepted, 1))
        accepted["provider_response_id"] = FAKE_RESPONSES_ID
        self.assertFalse(evaluate_z4(accepted, 1))

        rejected = {
            "converted_message_count": 11,
            "production_wrapper_decision": "rejected_before_http",
            "provider_outcome": "rejected_documented",
            "error": {
                "http_status": 400,
                "provider_request_or_trace_id": "request-z4",
            },
        }
        self.assertTrue(evaluate_z4(rejected, 1))
        rejected["error"]["provider_request_or_trace_id"] = None
        self.assertFalse(evaluate_z4(rejected, 1))

    def test_report_validation_enforces_budget_and_security(self) -> None:
        report = {
            "record_kind": "siliconflow_native_agent_zero_media_gate",
            "gate_decision": {"status": "pass_for_s03_single_image_review"},
            "aggregate_observations": {"provider_request_count": 5},
            "security_review": {"status": "pass"},
        }
        self.assertEqual([], validate_report(report))
        report["aggregate_observations"]["provider_request_count"] = 6
        self.assertEqual(["provider_request_budget"], validate_report(report))

    def test_security_scan_checks_values_without_rejecting_allowlist_keys(self) -> None:
        settings = Settings(
            session_secret="test-session-secret-123",
            siliconflow_api_key="g3-secret-api-key",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "g3.db"
            db_path.write_bytes(b"probe")
            clean = security_scan(
                {"authorization_header_absent": True, "marker": "G3-TEXT-OK"},
                settings=settings,
                database_path=db_path,
            )
            self.assertEqual("pass", clean["status"])
            leaked = security_scan(
                {"value": "g3-secret-api-key"},
                settings=settings,
                database_path=db_path,
            )
            self.assertEqual("fail", leaked["status"])


if __name__ == "__main__":
    unittest.main()
