import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.image_generation import (
    ImageProviderConfigError,
    ImageProviderResponseError,
    request_xg_image,
)


class ImageGenerationGatewayOnlyTest(unittest.TestCase):
    def test_gateway_response_error_is_not_fallback(self) -> None:
        with patch(
            "app.services.image_generation.request_image_gateway_generation",
            side_effect=ImageProviderResponseError("gateway failed"),
        ) as gateway_request:
            with self.assertRaisesRegex(ImageProviderResponseError, "gateway failed"):
                request_xg_image(
                    prompt="画一只猫",
                    reference_paths=[Path("/tmp/reference.png")],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                )

        gateway_request.assert_called_once_with(
            prompt="画一只猫",
            reference_paths=[Path("/tmp/reference.png")],
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )

    def test_gateway_config_error_is_not_fallback(self) -> None:
        with patch(
            "app.services.image_generation.request_image_gateway_generation",
            side_effect=ImageProviderConfigError("IMAGE_GATEWAY_API_KEY 未配置"),
        ) as gateway_request:
            with self.assertRaisesRegex(ImageProviderConfigError, "IMAGE_GATEWAY_API_KEY"):
                request_xg_image(
                    prompt="画一只猫",
                    reference_paths=[],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                )

        gateway_request.assert_called_once()

    def test_gateway_success_returns_result_directly(self) -> None:
        with patch(
            "app.services.image_generation.request_image_gateway_generation",
            return_value=(b"\x89PNG\r\n\x1a\nimage", "image/png", "gateway-request"),
        ) as gateway_request:
            content, content_type, request_id = request_xg_image(
                prompt="画一只猫",
                reference_paths=[],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )

        self.assertEqual(b"\x89PNG\r\n\x1a\nimage", content)
        self.assertEqual("image/png", content_type)
        self.assertEqual("gateway-request", request_id)
        gateway_request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
