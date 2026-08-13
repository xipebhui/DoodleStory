import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from scripts.run_paynes_creek_s03_g4 import (
    EXPECTED_PROMPT_SHA256,
    PROJECT_ROOT,
    build_user_content,
    canonical_prompt,
    create_pan_probe,
    inspection_sha256,
    inspection_request_from_tool_payload,
    load_inspection,
    load_prompt,
)


class PaynesCreekG4GateTests(unittest.TestCase):
    def test_canonical_prompt_hash_is_locked(self) -> None:
        prompt = canonical_prompt()
        self.assertEqual(
            EXPECTED_PROMPT_SHA256,
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
        self.assertFalse(prompt.endswith("\n"))

    def test_user_content_contains_exact_prompt_and_gate_request(self) -> None:
        prompt = canonical_prompt()
        content = build_user_content(prompt)
        self.assertIn(f"<locked_generate_image_prompt>\n{prompt}\n", content)
        self.assertIn('"historical_mechanism_alignment"', content)
        self.assertIn('"pan_right_crop_safety"', content)
        self.assertIn("provider 必须为 qy", content)

    def test_attempt_03_positive_prompt_hash_is_locked(self) -> None:
        path = PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-s03-attempt-03-prompt.txt"
        prompt = load_prompt(path)
        self.assertEqual(
            "ecf5820ca7912cb5a5ba955abc17a4fa6575937f547a1c8b3bb3ffe9bb70195e",
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
        self.assertIn("exactly those five grouped elements and nothing else", prompt)
        self.assertNotIn("faucet", prompt.lower())
        self.assertNotIn("valve", prompt.lower())

    def test_attempt_04_silent_frame_inputs_are_locked(self) -> None:
        prompt_path = PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-s03-attempt-04-prompt.txt"
        inspection_path = (
            PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-s03-attempt-04-inspection.json"
        )
        prompt = load_prompt(prompt_path)
        inspection = load_inspection(inspection_path)
        self.assertEqual(
            "7405efec3ac5522cb256239d0a901abdc7f6db05a2c8063ccba440c7d5984634",
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            "78f4f7007590109a45190a3588742b828d5ffbf961ce16f6b89eeec95d49f55f",
            inspection_sha256(inspection),
        )
        content = build_user_content(prompt, inspection)
        self.assertIn("lower 42 percent", content)
        self.assertIn("no in-image annotation", content)
        self.assertNotIn("amber dashed reconstruction contours", content)

    def test_inspection_request_is_extracted_from_real_tool_payload(self) -> None:
        inspection = load_inspection(
            PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-s03-attempt-04-inspection.json"
        )
        payload = {
            "tool": "inspect_image",
            "tool_call_id": "call-1",
            "image_id": "image-1",
            **inspection,
        }
        self.assertEqual(inspection, inspection_request_from_tool_payload(payload))
        self.assertEqual(
            inspection_sha256(inspection),
            inspection_sha256(inspection_request_from_tool_payload(payload)),
        )

    def test_pan_probe_creates_both_endpoints_and_contact_sheet(self) -> None:
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            Image.new("RGB", (1600, 900), "#2B7A78").save(source)
            paths = create_pan_probe(source, root / "probe")
            for path in paths.values():
                self.assertTrue((Path.cwd() / path).exists())
            with Image.open(Path.cwd() / paths["contact_sheet"]) as contact:
                self.assertEqual((1920, 540), contact.size)


if __name__ == "__main__":
    unittest.main()
