from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.run_paynes_creek_grok_ai_short import (
    DEFAULT_PLAN_PATH,
    PROJECT_ROOT,
    SCENE_IDS,
    allocate_caption_frames,
    allocate_scene_frames,
    build_render_manifest,
    load_plan,
    narration_text,
    output_names,
)


class PaynesCreekGrokAiShortTests(unittest.TestCase):
    def test_plan_has_exact_selected_scene_order(self) -> None:
        plan = load_plan()
        self.assertEqual(tuple(scene["id"] for scene in plan["scenes"]), SCENE_IDS)
        self.assertFalse(plan["publication_authorized"])
        self.assertFalse(plan["bgm"])
        self.assertEqual(plan["locale"], "zh-CN")
        self.assertEqual(plan["timing_mode"], "weighted")

    def test_english_plan_reuses_exact_selected_media(self) -> None:
        chinese = load_plan()
        english_path = (
            PROJECT_ROOT
            / "docs/strategy/youtube/paynes-creek-grok-ai-short-en-v2.json"
        )
        english = load_plan(english_path)
        self.assertEqual(english["locale"], "en-US")
        self.assertEqual(
            [scene["video_sha256"] for scene in english["scenes"]],
            [scene["video_sha256"] for scene in chinese["scenes"]],
        )
        self.assertEqual(english["attempt_accounting"]["grok_video_calls"], 0)
        self.assertTrue(
            all(
                not any("\u4e00" <= character <= "\u9fff" for character in scene["narration"])
                for scene in english["scenes"]
            )
        )
        self.assertEqual(
            output_names(english)["video"],
            "paynes-creek-grok-ai-short-en-v2-yuv420p.mp4",
        )
        narration = narration_text(english)
        self.assertTrue(narration.startswith("How did salt produced on the Maya coast"))
        self.assertNotIn("How did salt made", narration)
        self.assertIn("route. Workers", narration)
        self.assertNotIn("route.Workers", narration)

    def test_retention_plan_freezes_hook_phrase_captions_and_media(self) -> None:
        classic = load_plan(
            PROJECT_ROOT
            / "docs/strategy/youtube/paynes-creek-grok-ai-short-en-v2.json"
        )
        retention_path = (
            PROJECT_ROOT
            / "docs/strategy/youtube/paynes-creek-grok-ai-short-en-v5.json"
        )
        retention = load_plan(retention_path)
        self.assertEqual(retention["edit_mode"], "retention")
        self.assertEqual(
            [scene["video_sha256"] for scene in retention["scenes"]],
            [scene["video_sha256"] for scene in classic["scenes"]],
        )
        self.assertEqual(retention["attempt_accounting"]["grok_video_calls"], 0)
        self.assertEqual(retention["attempt_accounting"]["music_calls"], 0)
        self.assertEqual(retention["tts"]["speed"], 1.08)
        self.assertEqual(retention["timing_mode"], "source_aligned")
        self.assertEqual(retention["narration_source"]["source_attempt"], "paynes-creek-grok-ai-short-en-v4")
        self.assertEqual(
            output_names(retention)["video"],
            "paynes-creek-grok-ai-short-en-v5-yuv420p.mp4",
        )
        self.assertTrue(retention["scenes"][0]["hook"]["headline"])
        for scene in retention["scenes"]:
            self.assertEqual(" ".join(scene["captions"]), scene["narration"])
        self.assertGreaterEqual(len(narration_text(retention).split()), 90)
        self.assertLessEqual(len(narration_text(retention).split()), 115)

    def test_allocates_every_frame_and_keeps_four_second_minimum(self) -> None:
        frames = allocate_scene_frames(1500, [42, 36, 47, 48, 52])
        self.assertEqual(sum(frames), 1500)
        self.assertTrue(all(frame >= 120 for frame in frames))
        caption_frames = allocate_caption_frames(241, ["one two", "three", "four five"])
        self.assertEqual(sum(caption_frames), 241)
        self.assertTrue(all(frame > 0 for frame in caption_frames))

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
                source_plan_path=DEFAULT_PLAN_PATH,
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
            self.assertEqual(scene["captions"][0]["startFrame"], 0)
            self.assertEqual(scene["captions"][-1]["endFrame"], scene["durationInFrames"])

    def test_source_aligned_retention_manifest_uses_frozen_frames(self) -> None:
        plan_path = (
            PROJECT_ROOT
            / "docs/strategy/youtube/paynes-creek-grok-ai-short-en-v5.json"
        )
        plan = load_plan(plan_path)
        with tempfile.TemporaryDirectory() as temporary_dir:
            audio_path = Path(temporary_dir) / "narration.mp3"
            audio_path.write_bytes(b"audio")
            manifest = build_render_manifest(
                plan=plan,
                resolved_scenes=[
                    {
                        **scene,
                        "video_path_resolved": Path(temporary_dir) / f"{scene['id']}.mp4",
                    }
                    for scene in plan["scenes"]
                ],
                audio_path=audio_path,
                audio_duration_ms=38988,
                audio_sha256="b" * 64,
                source_plan_path=plan_path,
            )
        self.assertEqual(manifest["editMode"], "retention")
        self.assertEqual(manifest["totalFrames"], 1170)
        for scene in manifest["scenes"]:
            self.assertGreaterEqual(scene["playbackRate"], 0.65)
            self.assertLessEqual(scene["playbackRate"], 1.45)
            self.assertEqual(
                " ".join(caption["text"] for caption in scene["captions"]),
                scene["narration"],
            )
        self.assertEqual(manifest["timingMode"], "source_aligned")
        self.assertEqual(manifest["maxPlaybackRate"], 1.45)


if __name__ == "__main__":
    unittest.main()
