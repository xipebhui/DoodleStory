import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services.image_generation import (
    ImageReference,
    ImageAspectRatioMismatchError,
    ImageProviderConfigError,
    ImageProviderResponseError,
    build_image_gateway_generation_payload,
    build_xgapi_edit_payload,
    build_xgapi_generation_payload,
    generate_xg_image,
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


class ImageGenerationGatewayOnlyTest(unittest.TestCase):
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
