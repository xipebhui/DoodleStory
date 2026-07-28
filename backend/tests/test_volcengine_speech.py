import base64
import json
import unittest
from unittest.mock import patch

import requests

from app.core.config import Settings
from app.services.volcengine_speech import (
    VolcengineSpeechClient,
    VolcengineSpeechError,
    speech_rate_for_speed,
)


class FakeResponse:
    def __init__(
        self,
        frames: list[dict[str, object]],
        *,
        status_code: int = 200,
    ) -> None:
        encoded = "".join(
            json.dumps(frame, ensure_ascii=False, separators=(",", ":"))
            for frame in frames
        ).encode("utf-8")
        self._chunks = [
            encoded[:7],
            encoded[7:19],
            encoded[19:],
        ]
        self.status_code = status_code
        self.headers = {"X-Tt-Logid": "provider-log-id"}
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.request: dict[str, object] | None = None

    def post(self, url: str, **kwargs):
        self.request = {"url": url, **kwargs}
        return self.response


def speech_settings() -> Settings:
    return Settings(
        doubao_voice_gen_appid="test-app-id",
        doubao_voice_gen_ak="test-access-token",
        doubao_voice_gen_sk="unused-secret",
        doubao_voice_gen_resource_id="seed-tts-2.0",
        doubao_voice_gen_model="seed-tts-2.0-standard",
        doubao_voice_gen_speaker="zh_female_xinlingjitang_uranus_bigtts",
        doubao_voice_gen_format="mp3",
        doubao_voice_gen_sample_rate=24000,
        doubao_voice_gen_speech_rate=0,
        doubao_voice_gen_loudness_rate=0,
    )


class VolcengineSpeechClientTests(unittest.TestCase):
    def test_supported_speed_maps_to_provider_speech_rate(self) -> None:
        self.assertEqual(
            [-50, -25, 0, 25, 50, 100],
            [
                speech_rate_for_speed(speed)
                for speed in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
            ],
        )
        with self.assertRaisesRegex(VolcengineSpeechError, "只支持"):
            speech_rate_for_speed(1.1)

    def test_generate_speech_uses_fixed_request_and_decodes_stream(self) -> None:
        first = b"first-audio-"
        second = b"second-audio"
        response = FakeResponse(
            [
                {
                    "code": 0,
                    "data": base64.b64encode(first).decode("ascii"),
                },
                {
                    "code": 0,
                    "data": base64.b64encode(second).decode("ascii"),
                },
                {"code": 20000000, "addition": {"duration": "1234"}},
            ]
        )
        session = FakeSession(response)

        generated = VolcengineSpeechClient(
            settings=speech_settings(),
            session=session,
        ).generate_speech(text="  固定语音测试。  ")

        self.assertEqual(first + second, generated.content)
        self.assertEqual("audio/mpeg", generated.content_type)
        self.assertEqual(24000, generated.sample_rate)
        self.assertEqual(1234, generated.duration_ms)
        self.assertEqual("provider-log-id", generated.provider_request_id)
        self.assertTrue(response.closed)
        assert session.request is not None
        headers = session.request["headers"]
        body = session.request["json"]
        self.assertEqual("test-app-id", headers["X-Api-App-Id"])
        self.assertEqual("test-access-token", headers["X-Api-Access-Key"])
        self.assertNotIn("unused-secret", headers.values())
        self.assertEqual("seed-tts-2.0", headers["X-Api-Resource-Id"])
        self.assertEqual("固定语音测试。", body["req_params"]["text"])
        self.assertEqual(
            "seed-tts-2.0-standard",
            body["req_params"]["model"],
        )
        self.assertEqual(
            "zh_female_xinlingjitang_uranus_bigtts",
            body["req_params"]["speaker"],
        )
        self.assertEqual(
            {
                "format": "mp3",
                "sample_rate": 24000,
                "speech_rate": 0,
                "loudness_rate": 0,
            },
            body["req_params"]["audio_params"],
        )

    def test_generate_speech_sends_selected_speed(self) -> None:
        response = FakeResponse(
            [
                {
                    "code": 0,
                    "data": base64.b64encode(b"audio").decode("ascii"),
                },
                {"code": 20000000, "duration": 1000},
            ]
        )
        session = FakeSession(response)
        VolcengineSpeechClient(
            settings=speech_settings(),
            session=session,
        ).generate_speech(text="测试", speed=1.5)
        assert session.request is not None
        self.assertEqual(
            50,
            session.request["json"]["req_params"]["audio_params"]["speech_rate"],
        )

    def test_generate_speech_requires_success_terminal_frame(self) -> None:
        response = FakeResponse(
            [
                {
                    "code": 0,
                    "data": base64.b64encode(b"partial").decode("ascii"),
                }
            ]
        )

        with self.assertRaisesRegex(
            VolcengineSpeechError,
            "没有返回成功终态",
        ):
            VolcengineSpeechClient(
                settings=speech_settings(),
                session=FakeSession(response),
            ).generate_speech(text="测试")

        self.assertTrue(response.closed)

    def test_generate_speech_probes_mp3_when_provider_omits_duration(
        self,
    ) -> None:
        response = FakeResponse(
            [
                {
                    "code": 0,
                    "data": base64.b64encode(b"mp3-content").decode("ascii"),
                },
                {"code": 20000000},
            ]
        )

        with patch(
            "app.services.volcengine_speech._probe_audio_duration_ms",
            return_value=2468,
        ) as probe:
            generated = VolcengineSpeechClient(
                settings=speech_settings(),
                session=FakeSession(response),
            ).generate_speech(text="测试")

        self.assertEqual(2468, generated.duration_ms)
        probe.assert_called_once_with(b"mp3-content", "mp3")

    def test_generate_speech_surfaces_provider_failure(self) -> None:
        response = FakeResponse(
            [{"code": 55000000, "message": "invalid speaker"}]
        )

        with self.assertRaisesRegex(
            VolcengineSpeechError,
            "code=55000000",
        ):
            VolcengineSpeechClient(
                settings=speech_settings(),
                session=FakeSession(response),
            ).generate_speech(text="测试")

        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
