import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.image_generation import (
    ImageProviderConfigError,
    ImageProviderResponseError,
    build_xg_fallback_edit_data,
    build_xg_fallback_generation_payload,
    request_xg_image,
    xg_edit_image_field_name,
)


class ImageGenerationXgFallbackTest(unittest.TestCase):
    def test_gateway_response_error_falls_back_to_xg(self) -> None:
        with (
            patch(
                "app.services.image_generation.request_image_gateway_generation",
                side_effect=ImageProviderResponseError("gateway failed"),
            ) as gateway_request,
            patch(
                "app.services.image_generation.request_xg_fallback_image",
                return_value=(b"\x89PNG\r\n\x1a\nimage", "image/png", "xg-request"),
            ) as xg_request,
        ):
            content, content_type, request_id = request_xg_image(
                prompt="画一只猫",
                reference_paths=[Path("/tmp/reference.png")],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        self.assertEqual(b"\x89PNG\r\n\x1a\nimage", content)
        self.assertEqual("image/png", content_type)
        self.assertEqual("xg-request", request_id)
        gateway_request.assert_called_once()
        xg_request.assert_called_once_with(
            prompt="画一只猫",
            reference_paths=[Path("/tmp/reference.png")],
            aspect_ratio="3:4",
        )

    def test_gateway_config_error_does_not_fallback(self) -> None:
        with (
            patch(
                "app.services.image_generation.request_image_gateway_generation",
                side_effect=ImageProviderConfigError("IMAGE_GATEWAY_API_KEY 未配置"),
            ),
            patch("app.services.image_generation.request_xg_fallback_image") as xg_request,
        ):
            with self.assertRaises(ImageProviderConfigError):
                request_xg_image(
                    prompt="画一只猫",
                    reference_paths=[],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                )

        xg_request.assert_not_called()

    def test_xg_generation_payload_uses_url_response_format(self) -> None:
        with patch("app.services.image_generation.xg_fallback_model_name", return_value="gemini-3.1-flash-image-preview"):
            payload = build_xg_fallback_generation_payload(prompt="画一只猫", aspect_ratio="1:1")

        self.assertEqual(
            {
                "model": "gemini-3.1-flash-image-preview",
                "prompt": "画一只猫",
                "aspect_ratio": "1:1",
                "quality": "1k",
                "response_format": "url",
            },
            payload,
        )

    def test_xg_edit_uses_repeated_image_field_for_multiple_images(self) -> None:
        with patch("app.services.image_generation.xg_fallback_model_name", return_value="gemini-3.1-flash-image-preview"):
            data = build_xg_fallback_edit_data(prompt="改成漫画", aspect_ratio="3:4")

        self.assertEqual("gemini-3.1-flash-image-preview", data["model"])
        self.assertEqual("url", data["response_format"])
        self.assertEqual("image", xg_edit_image_field_name(1))
        self.assertEqual("image", xg_edit_image_field_name(2))


if __name__ == "__main__":
    unittest.main()
