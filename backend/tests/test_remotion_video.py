import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.core.config import Settings
from app.services.remotion_video import (
    REMOTION_TEMPLATE_ID,
    RemotionScene,
    RemotionVideoError,
    render_remotion_video,
)


class RemotionVideoTests(unittest.TestCase):
    def test_render_builds_fixed_template_manifest_and_reads_mp4(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "remotion"
            project.mkdir()
            (project / "node_modules").mkdir()
            (project / "render.mjs").write_text("", encoding="utf-8")
            image = root / "panel.png"
            audio = root / "narration.mp3"
            image.write_bytes(b"png")
            audio.write_bytes(b"mp3")

            def fake_run(command, **kwargs):
                input_path = Path(command[command.index("--input") + 1])
                output_path = Path(command[command.index("--output") + 1])
                manifest = json.loads(input_path.read_text(encoding="utf-8"))
                self.assertEqual(REMOTION_TEMPLATE_ID, manifest["templateId"])
                self.assertEqual("zoom_in", manifest["scenes"][0]["motion"])
                self.assertEqual(1840, manifest["scenes"][0]["durationMs"])
                output_path.write_bytes(b"rendered-mp4")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(
                        {
                            "status": "succeeded",
                            "templateId": REMOTION_TEMPLATE_ID,
                            "rendererVersion": "4.0.499",
                            "durationInFrames": 56,
                            "fps": 30,
                            "width": 1080,
                            "height": 1920,
                        }
                    ),
                    stderr="",
                )

            with patch(
                "app.services.remotion_video.subprocess.run",
                side_effect=fake_run,
            ):
                result = render_remotion_video(
                    scenes=[
                        RemotionScene(
                            scene_id="001",
                            image_path=image,
                            audio_path=audio,
                            subtitle="这是第一段字幕。",
                            duration_ms=1840,
                            motion_preset="zoom_in",
                        )
                    ],
                    bgm_path=None,
                    settings=Settings(
                        remotion_project_dir=project,
                        remotion_node_executable="node",
                    ),
                )

        self.assertEqual(b"rendered-mp4", result.content)
        self.assertEqual("video/mp4", result.content_type)
        self.assertEqual("4.0.499", result.renderer_version)
        self.assertEqual(56, result.duration_in_frames)

    def test_render_rejects_unknown_motion_without_running_node(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "panel.png"
            audio = root / "narration.mp3"
            image.write_bytes(b"png")
            audio.write_bytes(b"mp3")
            with self.assertRaisesRegex(
                RemotionVideoError,
                "Motion 不受支持",
            ):
                render_remotion_video(
                    scenes=[
                        RemotionScene(
                            scene_id="001",
                            image_path=image,
                            audio_path=audio,
                            subtitle="字幕",
                            duration_ms=1000,
                            motion_preset="spin",
                        )
                    ],
                    bgm_path=None,
                    settings=Settings(remotion_project_dir=root),
                )

    def test_render_surfaces_node_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "remotion"
            project.mkdir()
            (project / "node_modules").mkdir()
            (project / "render.mjs").write_text("", encoding="utf-8")
            image = root / "panel.png"
            audio = root / "narration.mp3"
            image.write_bytes(b"png")
            audio.write_bytes(b"mp3")
            with patch(
                "app.services.remotion_video.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    ["node"],
                    1,
                    stdout="",
                    stderr="browser unavailable",
                ),
            ):
                with self.assertRaisesRegex(
                    RemotionVideoError,
                    "browser unavailable",
                ):
                    render_remotion_video(
                        scenes=[
                            RemotionScene(
                                scene_id="001",
                                image_path=image,
                                audio_path=audio,
                                subtitle="字幕",
                                duration_ms=1000,
                                motion_preset="static",
                            )
                        ],
                        bgm_path=None,
                        settings=Settings(remotion_project_dir=project),
                    )
