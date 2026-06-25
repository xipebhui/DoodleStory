import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.models.enums import StorageBackend
from app.services.storage import (
    IMAGE_UPLOAD_MAX_BYTES,
    StoredFile,
    detect_verified_image_content_type,
    save_upload_file,
)


def image_bytes(format_name: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(buffer, format=format_name)
    return buffer.getvalue()


def upload_file(content: bytes, *, filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class StorageUploadTest(unittest.IsolatedAsyncioTestCase):
    def test_detect_verified_image_content_type_rejects_fake_image(self) -> None:
        with self.assertRaises(HTTPException) as context:
            detect_verified_image_content_type(b"not an image", "image/png")

        self.assertEqual(400, context.exception.status_code)
        self.assertEqual("上传文件不是有效图片", context.exception.detail)

    def test_detect_verified_image_content_type_rejects_mismatched_declared_type(self) -> None:
        with self.assertRaises(HTTPException) as context:
            detect_verified_image_content_type(image_bytes("JPEG"), "image/png")

        self.assertEqual(400, context.exception.status_code)
        self.assertEqual("图片内容与文件类型不一致", context.exception.detail)

    async def test_save_upload_file_rejects_oversized_image(self) -> None:
        file = upload_file(
            b"x" * (IMAGE_UPLOAD_MAX_BYTES + 1),
            filename="too-large.png",
            content_type="image/png",
        )

        with self.assertRaises(HTTPException) as context:
            await save_upload_file("style_reference", file)

        self.assertEqual(413, context.exception.status_code)
        self.assertEqual("图片不能超过 10MB", context.exception.detail)

    async def test_save_upload_file_uses_verified_content_suffix(self) -> None:
        stored = StoredFile(
            storage_backend=StorageBackend.local,
            storage_key="style_reference/test.jpg",
            byte_size=10,
            checksum_sha256="checksum",
        )
        file = upload_file(
            image_bytes("JPEG"),
            filename="misleading.png",
            content_type="image/jpeg",
        )

        with patch("app.services.storage.store_content", return_value=stored) as store_content:
            result = await save_upload_file("style_reference", file)

        self.assertEqual(stored, result)
        self.assertEqual(".jpg", store_content.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
