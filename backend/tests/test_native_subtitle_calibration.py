import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.tool_context import ToolContext

from app.services import native_agent_loop
from app.services.native_agent_loop import build_generate_subtitles_tool
from app.services.native_agent_persistence import CompletedNativeSubtitle
from app.services.whisper_subtitles import GeneratedSubtitles, SubtitleCue


class _FakeSession:
    def __init__(self, audio) -> None:
        self.audio = audio

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback

    def scalar(self, statement):
        del statement
        return self.audio


class NativeSubtitleCalibrationTests(unittest.TestCase):
    def test_tool_passes_saved_speech_text_to_subtitle_generator(self) -> None:
        lifecycle: list[str] = []
        audio = SimpleNamespace(
            text="系统提交的准确语音原文。",
            duration_ms=2400,
            asset=SimpleNamespace(),
        )

        def subtitle_generator(**kwargs):
            self.assertEqual(
                "系统提交的准确语音原文。",
                kwargs["reference_text"],
            )
            self.assertEqual(2400, kwargs["duration_ms"])
            self.assertEqual(Path("/tmp/native-audio.mp3"), kwargs["audio_path"])
            return GeneratedSubtitles(
                content=b"WEBVTT\n",
                text=kwargs["reference_text"],
                language="zh",
                model="tiny:source-aligned-v1",
                duration_ms=2400,
                cues=(
                    SubtitleCue(
                        start_ms=0,
                        end_ms=2400,
                        text=kwargs["reference_text"],
                    ),
                ),
            )

        class FakeStore:
            def prepare_subtitle_tool(inner_self, *, tool_call_id, audio_id):
                self.assertEqual("subtitle-call-1", tool_call_id)
                self.assertEqual("audio-1", audio_id)
                lifecycle.append("prepared")
                return SimpleNamespace(id="subtitle-step-1")

            def start_tool(inner_self, step_id):
                self.assertEqual("subtitle-step-1", step_id)
                lifecycle.append("running")

            def complete_subtitle_tool(
                inner_self,
                step_id,
                *,
                audio_id,
                generated,
            ):
                self.assertEqual("subtitle-step-1", step_id)
                self.assertEqual("audio-1", audio_id)
                self.assertEqual(
                    "系统提交的准确语音原文。",
                    generated.text,
                )
                lifecycle.append("succeeded")
                return CompletedNativeSubtitle(
                    step_id=step_id,
                    subtitle_id="subtitle-1",
                    audio_id=audio_id,
                    asset_id="asset-1",
                    content_type="text/vtt",
                    byte_size=len(generated.content),
                    text=generated.text,
                    language=generated.language,
                    model=generated.model,
                    duration_ms=generated.duration_ms,
                    cues=(
                        {
                            "start_ms": 0,
                            "end_ms": 2400,
                            "text": generated.text,
                        },
                    ),
                )

            def fail_tool(inner_self, step_id, exc):
                raise AssertionError((step_id, exc))

        tool = build_generate_subtitles_tool(
            "run-1",
            settings=native_agent_loop.Settings(),
            subtitle_generator=subtitle_generator,
            store=FakeStore(),
        )
        context = ToolContext(
            context=None,
            tool_name="generate_subtitles",
            tool_call_id="subtitle-call-1",
            tool_arguments='{"audio_id":"audio-1"}',
        )
        with (
            patch(
                "app.services.native_agent_loop.SessionLocal",
                return_value=_FakeSession(audio),
            ),
            patch(
                "app.services.native_agent_loop.materialize_asset_to_local",
                return_value=Path("/tmp/native-audio.mp3"),
            ),
        ):
            output = asyncio.run(
                tool.on_invoke_tool(
                    context,
                    json.dumps({"audio_id": "audio-1"}),
                )
            )

        self.assertEqual(["prepared", "running", "succeeded"], lifecycle)
        payload = json.loads(output[0].text)
        self.assertEqual("subtitle-1", payload["subtitle_id"])
        self.assertEqual("tiny:source-aligned-v1", payload["model"])
