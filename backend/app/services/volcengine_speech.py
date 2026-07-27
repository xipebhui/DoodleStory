from __future__ import annotations

import base64
import binascii
import codecs
from dataclasses import dataclass
import json
from typing import Any, Iterator
import uuid

import requests

from app.core.config import Settings, get_settings


class VolcengineSpeechError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedSpeech:
    content: bytes
    content_type: str
    response_format: str
    sample_rate: int
    provider_request_id: str
    duration_ms: int | None


def _duration_ms(frame: dict[str, Any]) -> int | None:
    candidates = [
        frame.get("duration"),
        (frame.get("addition") or {}).get("duration")
        if isinstance(frame.get("addition"), dict)
        else None,
    ]
    for value in candidates:
        try:
            parsed = int(float(str(value)))
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _json_frames(chunks: Iterator[bytes]) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    utf8_decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    for chunk in chunks:
        if not chunk:
            continue
        buffer += utf8_decoder.decode(chunk)
        while True:
            buffer = buffer.lstrip()
            if not buffer:
                break
            try:
                value, offset = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                break
            buffer = buffer[offset:]
            if not isinstance(value, dict):
                raise VolcengineSpeechError("火山语音接口返回的 frame 不是 JSON object")
            yield value
    buffer += utf8_decoder.decode(b"", final=True)
    if buffer.strip():
        raise VolcengineSpeechError("火山语音接口返回了无法解析的尾部数据")


class VolcengineSpeechClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session or requests.Session()

    def generate_speech(self, *, text: str) -> GeneratedSpeech:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise VolcengineSpeechError("语音合成文本不能为空")
        settings = self.settings
        app_id = settings.doubao_voice_gen_appid.strip()
        access_token = settings.doubao_voice_gen_ak.strip()
        if not app_id:
            raise VolcengineSpeechError("DOUBAO_VOICE_GEN_APPID 未配置")
        if not access_token:
            raise VolcengineSpeechError("DOUBAO_VOICE_GEN_AK 未配置")
        request_id = str(uuid.uuid4())
        try:
            response = self.session.post(
                settings.doubao_voice_gen_base_url.strip(),
                headers={
                    "X-Api-App-Id": app_id,
                    "X-Api-Access-Key": access_token,
                    "X-Api-Resource-Id": settings.doubao_voice_gen_resource_id.strip(),
                    "X-Api-Request-Id": request_id,
                    "Content-Type": "application/json",
                },
                json={
                    "user": {"uid": "doodlestory-native-agent"},
                    "req_params": {
                        "text": cleaned_text,
                        "speaker": settings.doubao_voice_gen_speaker.strip(),
                        "model": settings.doubao_voice_gen_model.strip(),
                        "audio_params": {
                            "format": settings.doubao_voice_gen_format.strip(),
                            "sample_rate": settings.doubao_voice_gen_sample_rate,
                            "speech_rate": settings.doubao_voice_gen_speech_rate,
                            "loudness_rate": settings.doubao_voice_gen_loudness_rate,
                        },
                    },
                },
                stream=True,
                timeout=(15, settings.doubao_voice_gen_timeout_seconds),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f"：HTTP {status_code}" if status_code is not None else ""
            raise VolcengineSpeechError(f"火山语音接口请求失败{suffix}") from exc

        audio_chunks: list[bytes] = []
        terminal_seen = False
        duration_ms: int | None = None
        try:
            for frame in _json_frames(response.iter_content(chunk_size=8192)):
                code = frame.get("code")
                if code == 0:
                    encoded = frame.get("data")
                    if isinstance(encoded, str) and encoded:
                        try:
                            audio_chunks.append(
                                base64.b64decode(encoded, validate=True)
                            )
                        except (ValueError, binascii.Error) as exc:
                            raise VolcengineSpeechError(
                                "火山语音接口返回了无效的 Base64 音频"
                            ) from exc
                    duration_ms = _duration_ms(frame) or duration_ms
                    continue
                if code == 20000000:
                    terminal_seen = True
                    duration_ms = _duration_ms(frame) or duration_ms
                    continue
                raise VolcengineSpeechError(
                    f"火山语音合成失败：code={code} "
                    f"message={str(frame.get('message') or '')[:300]}"
                )
        finally:
            response.close()
        content = b"".join(audio_chunks)
        if not terminal_seen:
            raise VolcengineSpeechError("火山语音接口没有返回成功终态")
        if not content:
            raise VolcengineSpeechError("火山语音接口成功结束但没有返回音频")
        response_format = settings.doubao_voice_gen_format.strip().lower()
        content_type = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "ogg_opus": "audio/ogg",
            "pcm": "audio/pcm",
        }.get(response_format, "application/octet-stream")
        return GeneratedSpeech(
            content=content,
            content_type=content_type,
            response_format=response_format,
            sample_rate=settings.doubao_voice_gen_sample_rate,
            provider_request_id=(
                response.headers.get("X-Tt-Logid", "").strip() or request_id
            ),
            duration_ms=duration_ms,
        )
