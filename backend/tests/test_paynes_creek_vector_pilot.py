import hashlib
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.run_paynes_creek_vector_pilot import (
    EXPECTED_DRAFT_SHA256,
    EXPECTED_NARRATION_SHA256,
    FPS,
    PROJECT_ROOT,
    allocate_scene_frames,
    build_manifest,
    load_draft,
    narration_text,
    scene_midpoint_frames,
    stream_duration_ms,
    validate_video_probe,
)


class PaynesCreekVectorPilotTests(unittest.TestCase):
    def test_source_draft_and_narration_are_locked(self) -> None:
        draft_path = PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-production-draft.json"
        draft = load_draft()
        self.assertEqual(EXPECTED_DRAFT_SHA256, hashlib.sha256(draft_path.read_bytes()).hexdigest())
        narration = narration_text(draft)
        self.assertEqual(EXPECTED_NARRATION_SHA256, hashlib.sha256(narration.encode("utf-8")).hexdigest())
        self.assertEqual(12, len(draft["scenes"]))
        self.assertIn("依据遗迹和类比做的重建", narration)
        self.assertIn("仍然未知", narration)

    def test_frame_allocation_is_exact_and_deterministic(self) -> None:
        weights = [34, 42, 44, 43, 48, 51, 44, 44, 46, 43, 46, 51]
        frames = allocate_scene_frames(4021, weights)
        self.assertEqual(4021, sum(frames))
        self.assertTrue(all(frame >= FPS for frame in frames))
        self.assertEqual(frames, allocate_scene_frames(4021, weights))

    def test_manifest_has_12_scenes_and_matches_audio_frames(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "narration.mp3"
            audio.write_bytes(b"mp3")
            manifest = build_manifest(
                draft=load_draft(),
                audio_path=audio,
                audio_duration_ms=134_017,
                audio_sha256="a" * 64,
            )
        self.assertEqual("paynes-creek-vector-v1", manifest["templateId"])
        self.assertEqual([f"S{index:02d}" for index in range(1, 13)], [scene["id"] for scene in manifest["scenes"]])
        self.assertEqual(math.ceil(134.017 * FPS), manifest["totalFrames"])
        self.assertEqual(manifest["totalFrames"], sum(scene["durationInFrames"] for scene in manifest["scenes"]))
        self.assertEqual(12, len(scene_midpoint_frames(manifest)))
        self.assertFalse(manifest["publicationAuthorized"])
        self.assertFalse(manifest["bgm"])

    def test_video_validation_uses_video_stream_not_aac_padded_container_duration(self) -> None:
        probe = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "pix_fmt": "yuv420p",
                    "r_frame_rate": "30/1",
                    "duration": "115.733333",
                    "nb_frames": "3472",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "115.776000"},
        }
        checks = validate_video_probe(
            probe,
            source_audio_duration_ms=115_704,
            expected_total_frames=3472,
        )
        self.assertTrue(checks["video_stream_duration_within_one_frame_of_source_audio"])
        self.assertEqual(115_733, stream_duration_ms(probe["streams"][0]))


if __name__ == "__main__":
    unittest.main()
