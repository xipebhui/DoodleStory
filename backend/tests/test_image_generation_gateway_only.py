import unittest
from unittest.mock import patch

from app.services.image_generation import (
    ImageProviderConfigError,
    ImageProviderResponseError,
    build_image_gateway_generation_payload,
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
                    reference_urls=["https://cdn.example.com/reference.png"],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                )

        gateway_request.assert_called_once_with(
            prompt="画一只猫",
            reference_urls=["https://cdn.example.com/reference.png"],
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
                    reference_urls=[],
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
                reference_urls=[],
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
            reference_urls=[
                "https://cdn.example.com/template.png",
                "https://cdn.example.com/person.png",
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

    def test_gateway_payload_rejects_non_public_reference_url(self) -> None:
        with self.assertRaisesRegex(ImageProviderConfigError, "HTTP\\(S\\) URL"):
            build_image_gateway_generation_payload(
                prompt="画一张连续漫画分镜",
                reference_urls=["data:image/png;base64,abc"],
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
            )


if __name__ == "__main__":
    unittest.main()
