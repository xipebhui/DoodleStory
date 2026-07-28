import unittest

from app.services.whisper_subtitles import (
    SubtitleCue,
    WhisperSubtitleError,
    build_webvtt,
    validate_subtitle_cues,
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
