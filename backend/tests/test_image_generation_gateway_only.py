import unittest
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services.image_generation import (
    ImageReference,
    ImageAspectRatioMismatchError,
    ImageProviderConfigError,
    ImageProviderResponseError,
    build_image_gateway_generation_payload,
    build_grokcli_image_command,
    build_xgapi_edit_payload,
    build_xgapi_generation_payload,
    generate_xg_image,
    grokcli_reference_urls,
    parse_grokcli_image_output,
    request_grokcli_image,
    request_xg_image,
)


def image_provider_settings(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        image_provider=provider,
        image_gateway_api_key="qy-key",
        image_gateway_base_url="https://qy.example.com/v1",
        xg_api_key="xg-key",
        xg_base_url="https://api.xgapi.top",
        xg_image_quality="1k",
        grokcli_executable="grokcli",
        grokcli_home="/tmp/test-grokcli-home",
        grokcli_image_model="grok-imagine-image-quality",
        grokcli_image_edit_model="grok-imagine-image",
        grokcli_image_resolution="2k",
        grokcli_timeout_seconds=300,
        grokcli_request_max_attempts=2,
        grokcli_retry_backoff_seconds=0,
        xg_request_max_attempts=1,
        image_provider_timeout_retry_attempts=0,
        xg_request_retry_backoff_seconds=0,
        image_provider_debug_log_raw_io=False,
        image_provider_debug_log_raw_max_chars=20000,
    )


class FakeResponse:
    status_code = 200
    content = b'{"data":[{"url":"https://cdn.example.com/out.png"}]}'
    text = '{"data":[{"url":"https://cdn.example.com/out.png"}]}'
    headers = {"content-type": "application/json", "x-request-id": "xg-request"}

    def json(self) -> dict[str, object]:
        return {"data": [{"url": "https://cdn.example.com/out.png"}]}


class FakeSession:
    def __init__(self) -> None:
        self.trust_env = False

    def post(self, endpoint: str, **kwargs):
        FakeSession.calls.append((endpoint, kwargs))
        return FakeResponse()


FakeSession.calls = []


def png_bytes(width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color="white").save(output, format="PNG")
    return output.getvalue()


def jpeg_bytes(width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color="white").save(output, format="JPEG")
    return output.getvalue()


class ImageGenerationGatewayOnlyTest(unittest.TestCase):
    def test_explicit_grok_provider_routes_only_to_grokcli(self) -> None:
        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("qy"),
        ), patch(
            "app.services.image_generation.request_grokcli_image",
            return_value=(b"jpeg", "image/jpeg", None),
        ) as grok_request, patch(
            "app.services.image_generation.request_image_gateway_generation"
        ) as gateway_request:
            result = request_xg_image(
                prompt="用 Grok 画一只猫",
                references=[],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
                image_provider="grok",
            )

        self.assertEqual((b"jpeg", "image/jpeg", None), result)
        grok_request.assert_called_once_with(
            prompt="用 Grok 画一只猫",
            references=[],
            aspect_ratio="3:4",
        )
        gateway_request.assert_not_called()

    def test_grokcli_generation_command_uses_quality_model_and_requested_ratio(self) -> None:
        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("grok"),
        ):
            command = build_grokcli_image_command(
                prompt="画一只猫",
                references=[],
                aspect_ratio="3:4",
            )

        self.assertEqual("grokcli", command[0])
        self.assertEqual("image", command[1])
        self.assertIn("grok-imagine-image-quality", command)
        self.assertEqual("3:4", command[command.index("--aspect") + 1])
        self.assertEqual("2k", command[command.index("--resolution") + 1])

    def test_grokcli_edit_command_keeps_up_to_three_public_references(self) -> None:
        references = [
            ImageReference(url="https://cdn.example.com/one.png"),
            ImageReference(url="https://cdn.example.com/two.jpg"),
        ]
        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("grok"),
        ):
            command = build_grokcli_image_command(
                prompt="保持角色一致",
                references=references,
                aspect_ratio="9:16",
            )

        self.assertEqual("image-edit", command[1])
        self.assertIn("grok-imagine-image", command)
        self.assertEqual(2, command.count("--image"))
        self.assertEqual(
            ["https://cdn.example.com/one.png", "https://cdn.example.com/two.jpg"],
            [command[index + 1] for index, value in enumerate(command) if value == "--image"],
        )

    def test_grokcli_rejects_too_many_or_non_public_references(self) -> None:
        with self.assertRaisesRegex(ImageProviderConfigError, "最多支持 3 张"):
            grokcli_reference_urls(
                [ImageReference(url=f"https://cdn.example.com/{index}.png") for index in range(4)]
            )
        with self.assertRaisesRegex(ImageProviderConfigError, "HTTP\\(S\\) URL"):
            grokcli_reference_urls([ImageReference(url="data:image/png;base64,abc")])

    def test_grokcli_output_detects_real_jpeg_despite_png_suffix(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary_dir:
            output_root = Path(temporary_dir) / "output"
            output_root.mkdir()
            image_path = output_root / "result.png"
            image_path.write_bytes(jpeg_bytes(3, 4))
            content, content_type = parse_grokcli_image_output(
                json.dumps({"paths": [str(image_path)]}),
                output_root,
            )

        self.assertTrue(content.startswith(b"\xff\xd8\xff"))
        self.assertEqual("image/jpeg", content_type)

    def test_grokcli_retries_network_exit_code_then_reads_output(self) -> None:
        calls = 0

        def fake_run(command, **kwargs):
            nonlocal calls
            del command
            calls += 1
            if calls == 1:
                return SimpleNamespace(returncode=6, stdout="", stderr="network failed")
            output_root = Path(kwargs["env"]["GROKCLI_OUTPUT_DIR"])
            output_root.mkdir(parents=True)
            image_path = output_root / "result.png"
            image_path.write_bytes(png_bytes(3, 4))
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"paths": [str(image_path)]}),
                stderr="",
            )

        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("grok"),
        ), patch("app.services.image_generation.subprocess.run", side_effect=fake_run):
            content, content_type, request_id = request_grokcli_image(
                prompt="画一只猫",
                references=[],
                aspect_ratio="3:4",
            )

        self.assertEqual(2, calls)
        self.assertEqual("image/png", content_type)
        self.assertIsNone(request_id)
        self.assertTrue(content.startswith(b"\x89PNG"))

    def test_gateway_response_error_is_not_fallback(self) -> None:
        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("qy"),
        ), patch(
            "app.services.image_generation.request_image_gateway_generation",
            side_effect=ImageProviderResponseError("gateway failed"),
        ) as gateway_request:
            with self.assertRaisesRegex(ImageProviderResponseError, "gateway failed"):
                request_xg_image(
                    prompt="画一只猫",
                    references=[ImageReference(url="https://cdn.example.com/reference.png")],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                )

        gateway_request.assert_called_once_with(
            prompt="画一只猫",
            references=[ImageReference(url="https://cdn.example.com/reference.png")],
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )

    def test_gateway_config_error_is_not_fallback(self) -> None:
        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("qy"),
        ), patch(
            "app.services.image_generation.request_image_gateway_generation",
            side_effect=ImageProviderConfigError("IMAGE_GATEWAY_API_KEY 未配置"),
        ) as gateway_request:
            with self.assertRaisesRegex(ImageProviderConfigError, "IMAGE_GATEWAY_API_KEY"):
                request_xg_image(
                    prompt="画一只猫",
                    references=[],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                )

        gateway_request.assert_called_once()

    def test_gateway_success_returns_result_directly(self) -> None:
        with patch(
            "app.services.image_generation.get_settings",
            return_value=image_provider_settings("qy"),
        ), patch(
            "app.services.image_generation.request_image_gateway_generation",
            return_value=(b"\x89PNG\r\n\x1a\nimage", "image/png", "gateway-request"),
        ) as gateway_request:
            content, content_type, request_id = request_xg_image(
                prompt="画一只猫",
                references=[],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        self.assertEqual(b"\x89PNG\r\n\x1a\nimage", content)
        self.assertEqual("image/png", content_type)
        self.assertEqual("gateway-request", request_id)
        gateway_request.assert_called_once()

    def test_gateway_payload_uses_qy_public_url_reference_fields(self) -> None:
        payload, reference_info = build_image_gateway_generation_payload(
            prompt="画一张连续漫画分镜",
            references=[
                ImageReference(url="https://cdn.example.com/template.png"),
                ImageReference(url="https://cdn.example.com/person.png"),
            ],
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )

        self.assertEqual("https://cdn.example.com/template.png", payload["image"])
        self.assertEqual("https://cdn.example.com/person.png", payload["image2"])
        self.assertNotIn("images", payload)
        self.assertNotIn("image3", payload)
        self.assertFalse(any(isinstance(value, str) and value.startswith("data:image") for value in payload.values()))
        self.assertEqual(2, len(reference_info))

    def test_gateway_payload_keeps_four_gpt_image_references_and_truncates_extra(self) -> None:
        payload, reference_info = build_image_gateway_generation_payload(
            prompt="画一张连续漫画分镜",
            references=[
                ImageReference(url=f"https://cdn.example.com/reference-{index}.png")
                for index in range(1, 6)
            ],
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )

        self.assertEqual("https://cdn.example.com/reference-1.png", payload["image"])
        self.assertEqual("https://cdn.example.com/reference-2.png", payload["image2"])
        self.assertEqual("https://cdn.example.com/reference-3.png", payload["image3"])
        self.assertEqual("https://cdn.example.com/reference-4.png", payload["image4"])
        self.assertNotIn("image5", payload)
        self.assertEqual(4, len(reference_info))

    def test_gateway_payload_omits_unverified_image_size_for_three_by_four(self) -> None:
        payload, _reference_info = build_image_gateway_generation_payload(
            prompt="画一张 3:4 漫画页",
            references=[],
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )

        self.assertNotIn("size", payload)
        self.assertNotEqual("864x1152", payload.get("size"))
        self.assertNotIn("aspect_ratio", payload)

    def test_gateway_payload_keeps_verified_image_size_for_nine_by_sixteen(self) -> None:
        payload, _reference_info = build_image_gateway_generation_payload(
            prompt="画一张 9:16 漫画页",
            references=[],
            image_model_name="gpt-image-2",
            aspect_ratio="9:16",
        )

        self.assertEqual("1024x1792", payload["size"])

    def test_gateway_payload_rejects_non_public_reference_url(self) -> None:
        with self.assertRaisesRegex(ImageProviderConfigError, "HTTP\\(S\\) URL"):
            build_image_gateway_generation_payload(
                prompt="画一张连续漫画分镜",
                references=[ImageReference(url="data:image/png;base64,abc")],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

    def test_xgapi_generation_payload_uses_task_style_model(self) -> None:
        with patch("app.services.image_generation.get_settings", return_value=image_provider_settings("xgapi")):
            payload = build_xgapi_generation_payload(
                prompt="画一张连续漫画分镜",
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        self.assertEqual("gpt-image-2", payload["model"])
        self.assertEqual("3:4", payload["aspect_ratio"])
        self.assertEqual("high", payload["quality"])
        self.assertEqual("url", payload["response_format"])

    def test_xgapi_generation_payload_rejects_empty_style_model(self) -> None:
        with patch("app.services.image_generation.get_settings", return_value=image_provider_settings("xgapi")):
            with self.assertRaisesRegex(ImageProviderConfigError, "生图模型未配置"):
                build_xgapi_generation_payload(
                    prompt="画一张连续漫画分镜",
                    image_model_name="",
                    aspect_ratio="3:4",
                )

    def test_xgapi_reference_images_use_multipart_files(self) -> None:
        FakeSession.calls = []
        with patch("app.services.image_generation.get_settings", return_value=image_provider_settings("xgapi")), patch(
            "app.services.image_generation.requests.Session",
            side_effect=FakeSession,
        ), patch(
            "app.services.image_generation.download_generated_image",
            side_effect=[
                (b"\x89PNG\r\n\x1a\nfirst", "image/png"),
                (b"\xff\xd8\xffsecond", "image/jpeg"),
            ],
        ), patch(
            "app.services.image_generation.read_image_gateway_generation_result",
            return_value=(b"\x89PNG\r\n\x1a\nimage", "image/png", "xg-request"),
        ):
            content, content_type, request_id = request_xg_image(
                prompt="画一张连续漫画分镜",
                references=[
                    ImageReference(url="https://cdn.example.com/first.png"),
                    ImageReference(url="https://cdn.example.com/second.png"),
                ],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        self.assertEqual(b"\x89PNG\r\n\x1a\nimage", content)
        self.assertEqual("image/png", content_type)
        self.assertEqual("xg-request", request_id)
        endpoint, kwargs = FakeSession.calls[0]
        self.assertEqual("https://api.xgapi.top/v1/images/edits", endpoint)
        self.assertEqual("gpt-image-2", kwargs["data"]["model"])
        self.assertEqual("high", kwargs["data"]["quality"])
        self.assertEqual("url", kwargs["data"]["response_format"])
        self.assertNotIn("Content-Type", kwargs["headers"])
        self.assertNotIn("json", kwargs)
        self.assertEqual(["image", "image"], [item[0] for item in kwargs["files"]])
        self.assertEqual("reference-1.png", kwargs["files"][0][1][0])
        self.assertEqual("reference-2.jpg", kwargs["files"][1][1][0])

    def test_xgapi_edit_payload_translates_generation_quality_to_edit_quality(self) -> None:
        with patch("app.services.image_generation.get_settings", return_value=image_provider_settings("xgapi")):
            payload = build_xgapi_edit_payload(
                prompt="画一张连续漫画分镜",
                reference_urls=["https://cdn.example.com/reference.png"],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        self.assertEqual("gpt-image-2", payload["model"])
        self.assertEqual("3:4", payload["aspect_ratio"])
        self.assertEqual("high", payload["quality"])
        self.assertNotIn("image", payload)

    def test_xgapi_without_reference_uses_generation_json(self) -> None:
        FakeSession.calls = []
        with patch("app.services.image_generation.get_settings", return_value=image_provider_settings("xgapi")), patch(
            "app.services.image_generation.requests.Session",
            side_effect=FakeSession,
        ), patch(
            "app.services.image_generation.read_image_gateway_generation_result",
            return_value=(b"\x89PNG\r\n\x1a\nimage", "image/png", "xg-request"),
        ):
            request_xg_image(
                prompt="画一只猫",
                references=[],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        endpoint, kwargs = FakeSession.calls[0]
        self.assertEqual("https://api.xgapi.top/v1/images/generations", endpoint)
        self.assertEqual("gpt-image-2", kwargs["json"]["model"])
        self.assertEqual("high", kwargs["json"]["quality"])
        self.assertNotIn("files", kwargs)

    def test_generate_xg_image_rejects_mismatched_result_aspect_ratio_before_save(self) -> None:
        with patch(
            "app.services.image_generation.request_xg_image",
            return_value=(png_bytes(1024, 1792), "image/png", "request-1"),
        ), patch("app.services.image_generation.save_bytes") as save:
            with self.assertRaisesRegex(ImageAspectRatioMismatchError, "目标 3:4，实际 1024:1792"):
                generate_xg_image(
                    prompt="画一张 3:4 漫画页",
                    references=[],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                    validate_result_aspect_ratio=True,
                )

        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
