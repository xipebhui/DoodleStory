from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.run_paynes_creek_grok_ai_short import (
    SCENE_IDS,
    allocate_scene_frames,
    build_render_manifest,
    load_plan,
)


class PaynesCreekGrokAiShortTests(unittest.TestCase):
    def test_plan_has_exact_selected_scene_order(self) -> None:
        plan = load_plan()
        self.assertEqual(tuple(scene["id"] for scene in plan["scenes"]), SCENE_IDS)
        self.assertFalse(plan["publication_authorized"])
        self.assertFalse(plan["bgm"])

    def test_allocates_every_frame_and_keeps_four_second_minimum(self) -> None:
        frames = allocate_scene_frames(1500, [42, 36, 47, 48, 52])
        self.assertEqual(sum(frames), 1500)
        self.assertTrue(all(frame >= 120 for frame in frames))

    def test_build_manifest_binds_playback_rate_to_real_duration(self) -> None:
        plan = load_plan()
        with tempfile.TemporaryDirectory() as temporary_dir:
            audio_path = Path(temporary_dir) / "narration.mp3"
            audio_path.write_bytes(b"audio")
            resolved_scenes = [
                {
                    **scene,
                    "video_path_resolved": Path(temporary_dir) / f"{scene['id']}.mp4",
                }
                for scene in plan["scenes"]
            ]
            manifest = build_render_manifest(
                plan=plan,
                resolved_scenes=resolved_scenes,
                audio_path=audio_path,
                audio_duration_ms=48000,
                audio_sha256="a" * 64,
            )
        self.assertEqual(manifest["totalFrames"], 1440)
        self.assertEqual(sum(scene["durationInFrames"] for scene in manifest["scenes"]), 1440)
        for scene in manifest["scenes"]:
            expected = scene["videoDurationMs"] / (
                (scene["durationInFrames"] / 30) * 1000
            )
            self.assertAlmostEqual(scene["playbackRate"], expected)
            self.assertGreaterEqual(scene["playbackRate"], 0.65)
            self.assertLessEqual(scene["playbackRate"], 1.35)


if __name__ == "__main__":
    unittest.main()

