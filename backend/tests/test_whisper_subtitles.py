import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.whisper_subtitles import (
    SubtitleCue,
    WhisperSubtitleError,
    align_reference_subtitles,
    build_webvtt,
    generate_whisper_subtitles,
    validate_subtitle_cues,
)


def timed_segment(text: str, duration_seconds: float = 2.0):
    character_duration = duration_seconds / len(text)
    return SimpleNamespace(
        start=0.0,
        end=duration_seconds,
        text=text,
        words=[
            SimpleNamespace(
                start=index * character_duration,
                end=(index + 1) * character_duration,
                word=character,
            )
            for index, character in enumerate(text)
        ],
    )


class WhisperSubtitleTests(unittest.TestCase):
    def test_builds_valid_webvtt(self) -> None:
        cues = (
            SubtitleCue(start_ms=0, end_ms=1200, text="第一句"),
            SubtitleCue(start_ms=1500, end_ms=3210, text="第二句"),
        )
        validate_subtitle_cues(cues, duration_ms=4000)
        content = build_webvtt(cues).decode("utf-8")
        self.assertTrue(content.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:00.000 --> 00:00:01.200", content)
        self.assertIn("00:00:01.500 --> 00:00:03.210", content)

    def test_rejects_non_monotonic_or_overlong_cues(self) -> None:
        with self.assertRaisesRegex(WhisperSubtitleError, "不单调"):
            validate_subtitle_cues(
                (
                    SubtitleCue(0, 1000, "一"),
                    SubtitleCue(900, 1200, "二"),
                ),
                duration_ms=2000,
            )
        with self.assertRaisesRegex(WhisperSubtitleError, "超出"):
            validate_subtitle_cues(
                (SubtitleCue(0, 2100, "一"),),
                duration_ms=2000,
            )

    def test_aligns_misrecognized_chinese_back_to_reference_text(self) -> None:
        cues = align_reference_subtitles(
            reference_text="今天账户正常。",
            segments=(timed_segment("今天帐户正常"),),
            duration_ms=2000,
        )

        self.assertEqual("今天账户正常。", "".join(cue.text for cue in cues))
        self.assertEqual(1, len(cues))
        self.assertEqual(0, cues[0].start_ms)
        self.assertEqual(2000, cues[0].end_ms)

    def test_preserves_punctuation_when_max_length_break_precedes_it(self) -> None:
        reference = "一二三四五六七八九十一二三四五六七八。下一句。"
        recognized = reference.replace("。", "")
        cues = align_reference_subtitles(
            reference_text=reference,
            segments=(timed_segment(recognized, 4.0),),
            duration_ms=4000,
        )

        self.assertEqual(reference, "".join(cue.text for cue in cues))
        self.assertGreaterEqual(len(cues), 2)
        validate_subtitle_cues(cues, duration_ms=4000)

    def test_rejects_alignment_when_audio_differs_from_reference(self) -> None:
        with self.assertRaisesRegex(WhisperSubtitleError, "差异过大"):
            align_reference_subtitles(
                reference_text="这是完全不同的语音原文。",
                segments=(timed_segment("明天天气特别晴朗"),),
                duration_ms=2000,
            )

    def test_rejects_segments_without_word_timestamps(self) -> None:
        with self.assertRaisesRegex(WhisperSubtitleError, "词级时间戳"):
            align_reference_subtitles(
                reference_text="需要准确时间轴。",
                segments=(
                    SimpleNamespace(
                        start=0.0,
                        end=2.0,
                        text="需要准确时间轴",
                        words=None,
                    ),
                ),
                duration_ms=2000,
            )

    @patch("app.services.whisper_subtitles.load_whisper_model")
    def test_generation_requests_word_timestamps_and_persists_source_text(
        self,
        load_model,
    ) -> None:
        model = load_model.return_value
        model.transcribe.return_value = (
            iter((timed_segment("今天帐户正常"),)),
            SimpleNamespace(language="zh"),
        )
        settings = SimpleNamespace(
            local_whisper_model="tiny",
            local_whisper_device="cpu",
            local_whisper_compute_type="int8",
        )

        generated = generate_whisper_subtitles(
            audio_path=Path("/tmp/reference.mp3"),
            duration_ms=2000,
            reference_text="今天账户正常。",
            settings=settings,
        )

        model.transcribe.assert_called_once_with(
            "/tmp/reference.mp3",
            vad_filter=True,
            language="zh",
            word_timestamps=True,
        )
        self.assertEqual("今天账户正常。", generated.text)
        self.assertEqual("tiny:source-aligned-v1", generated.model)
        self.assertIn("今天账户正常。", generated.content.decode("utf-8"))
