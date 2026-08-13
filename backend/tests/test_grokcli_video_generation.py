import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.core.config import Settings
from app.services.grok_video_generation import (
    GROKCLI_PINNED_VERSION,
    GrokVideoConfigError,
    GrokVideoGenerationError,
    _parse_grokcli_video_path,
    build_grokcli_video_command,
    request_grokcli_video,
)


class GrokcliVideoGenerationTests(unittest.TestCase):
    def settings(self, **overrides) -> Settings:
        values = {
            "grokcli_executable": "grokcli-test",
            "grokcli_home": "C:/grokcli-home",
            "grokcli_video_model": "grok-imagine-video-1.5",
            "grokcli_video_resolution": "720p",
            "grokcli_video_timeout_seconds": 660,
            "ffprobe_executable": "ffprobe-test",
        }
        values.update(overrides)
        return Settings(**values)

    def test_builds_t2v_and_i2v_commands_with_strict_arguments(self) -> None:
        settings = self.settings()
        t2v = build_grokcli_video_command(
            prompt=" cinematic creek ",
            image_path=None,
            duration_seconds=8,
            aspect_ratio="16:9",
            settings=settings,
        )
        self.assertEqual(["grokcli-test", "video", "cinematic creek"], t2v[:3])
        self.assertNotIn("--image", t2v)
        self.assertEqual("grok-imagine-video-1.5", t2v[t2v.index("--model") + 1])
        self.assertEqual("720p", t2v[t2v.index("--resolution") + 1])

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            source.write_bytes(b"png")
            i2v = build_grokcli_video_command(
                prompt="animate",
                image_path=source,
                duration_seconds=15,
                aspect_ratio="9:16",
                settings=settings,
            )
        self.assertEqual(str(source.resolve()), i2v[i2v.index("--image") + 1])
        self.assertEqual("15", i2v[i2v.index("--duration") + 1])

    def test_rejects_invalid_parameters_before_subprocess(self) -> None:
        cases = [
            ({"prompt": "", "duration_seconds": 8, "aspect_ratio": "16:9"}, "Prompt"),
            ({"prompt": "x", "duration_seconds": 0, "aspect_ratio": "16:9"}, "1–15"),
            ({"prompt": "x", "duration_seconds": 16, "aspect_ratio": "16:9"}, "1–15"),
            ({"prompt": "x", "duration_seconds": 8, "aspect_ratio": "auto"}, "画面比例"),
        ]
        for arguments, message in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(GrokVideoConfigError, message):
                    build_grokcli_video_command(
                        image_path=None,
                        settings=self.settings(),
                        **arguments,
                    )
        with self.assertRaisesRegex(GrokVideoConfigError, "源图片不存在"):
            build_grokcli_video_command(
                prompt="x",
                image_path=Path("missing.png"),
                duration_seconds=8,
                aspect_ratio="16:9",
                settings=self.settings(),
            )
        with self.assertRaisesRegex(GrokVideoConfigError, "480p"):
            build_grokcli_video_command(
                prompt="x",
                image_path=None,
                duration_seconds=8,
                aspect_ratio="16:9",
                settings=self.settings(grokcli_video_resolution="4k"),
            )

    def test_reads_unique_h264_mp4_and_ffprobe_metadata_without_retry(self) -> None:
        grok_calls = 0
        ffprobe_calls = 0

        def fake_run(command, **kwargs):
            nonlocal grok_calls, ffprobe_calls
            if command[0] == "grokcli-test":
                grok_calls += 1
                self.assertEqual("C:/grokcli-home", kwargs["env"]["GROKCLI_HOME"])
                output_root = Path(kwargs["env"]["GROKCLI_OUTPUT_DIR"])
                output_root.mkdir(parents=True)
                output_path = output_root / "paynes-creek.mp4"
                output_path.write_bytes(b"\x00\x00\x00\x18ftypisomvideo")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps({"path": str(output_path)}),
                    stderr="",
                )
            ffprobe_calls += 1
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "h264",
                                "width": 1280,
                                "height": 720,
                                "avg_frame_rate": "30/1",
                                "nb_read_frames": "240",
                                "duration": "8.0",
                            }
                        ],
                        "format": {
                            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                            "duration": "8.0",
                        },
                    }
                ),
                stderr="",
            )

        with patch(
            "app.services.grok_video_generation.subprocess.run",
            side_effect=fake_run,
        ):
            result = request_grokcli_video(
                prompt="Paynes Creek cinematic pan",
                image_path=None,
                duration_seconds=8,
                aspect_ratio="16:9",
                settings=self.settings(),
            )

        self.assertEqual(1, grok_calls)
        self.assertEqual(1, ffprobe_calls)
        self.assertEqual("video/mp4", result.content_type)
        self.assertEqual("text_to_video", result.mode)
        self.assertEqual(8000, result.duration_ms)
        self.assertEqual(240, result.duration_in_frames)
        self.assertEqual(30, result.fps)
        self.assertEqual(f"grokcli/{GROKCLI_PINNED_VERSION}", result.renderer_version)

    def test_does_not_retry_known_grokcli_failures(self) -> None:
        labels = {
            2: "参数配置错误",
            3: "OAuth 认证",
            4: "额度",
            5: "超时",
            6: "网络",
            10: "审核",
        }
        for exit_code, message in labels.items():
            with self.subTest(exit_code=exit_code):
                with patch(
                    "app.services.grok_video_generation.subprocess.run",
                    return_value=SimpleNamespace(
                        returncode=exit_code,
                        stdout="",
                        stderr="access_token=secret failure",
                    ),
                ) as run:
                    with self.assertRaisesRegex(RuntimeError, message) as error:
                        request_grokcli_video(
                            prompt="x",
                            image_path=None,
                            duration_seconds=8,
                            aspect_ratio="16:9",
                            settings=self.settings(),
                        )
                self.assertEqual(1, run.call_count)
                self.assertNotIn("secret", str(error.exception))

    def test_timeout_is_ambiguous_and_not_retried(self) -> None:
        with patch(
            "app.services.grok_video_generation.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["grokcli-test"], 675),
        ) as run:
            with self.assertRaisesRegex(
                GrokVideoGenerationError,
                "结果状态未知，禁止自动重试",
            ):
                request_grokcli_video(
                    prompt="x",
                    image_path=None,
                    duration_seconds=8,
                    aspect_ratio="16:9",
                    settings=self.settings(),
                )
        self.assertEqual(1, run.call_count)

    def test_rejects_output_path_escape_and_multiple_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "output"
            output_root.mkdir()
            outside = root / "outside.mp4"
            outside.write_bytes(b"video")
            with self.assertRaisesRegex(GrokVideoGenerationError, "输出目录之外"):
                _parse_grokcli_video_path(
                    json.dumps({"path": str(outside)}),
                    output_root,
                )
            first = output_root / "first.mp4"
            second = output_root / "second.mp4"
            first.write_bytes(b"video")
            second.write_bytes(b"video")
            with self.assertRaisesRegex(GrokVideoGenerationError, "只能包含一个"):
                _parse_grokcli_video_path(
                    json.dumps({"path": str(first)}),
                    output_root,
                )

    def test_rejects_non_mp4_before_ffprobe(self) -> None:
        def fake_run(command, **kwargs):
            output_root = Path(kwargs["env"]["GROKCLI_OUTPUT_DIR"])
            output_root.mkdir(parents=True)
            output_path = output_root / "fake.mp4"
            output_path.write_bytes(b"not-an-mp4-file")
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"path": str(output_path)}),
                stderr="",
            )

        with patch(
            "app.services.grok_video_generation.subprocess.run",
            side_effect=fake_run,
        ) as run:
            with self.assertRaisesRegex(GrokVideoGenerationError, "有效 MP4"):
                request_grokcli_video(
                    prompt="x",
                    image_path=None,
                    duration_seconds=8,
                    aspect_ratio="16:9",
                    settings=self.settings(),
                )
        self.assertEqual(1, run.call_count)


if __name__ == "__main__":
    unittest.main()
