from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from app.core.config import get_settings

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class SiliconFlowVoiceError(RuntimeError):
    pass


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text.strip()
        message = f"SiliconFlow 语音接口请求失败：HTTP {response.status_code}"
        if body:
            message = f"{message} {body[:500]}"
        raise SiliconFlowVoiceError(message) from exc


def _parse_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SiliconFlowVoiceError(f"SiliconFlow 语音接口返回非 JSON：{response.text[:500]}") from exc
    if not isinstance(payload, dict):
        raise SiliconFlowVoiceError("SiliconFlow 语音接口返回结构不是 JSON object")
    return payload


class SiliconFlowVoiceClient:
    def __init__(self, *, api_base: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_base = (api_base or settings.siliconflow_base_url).strip().rstrip("/")
        self.api_key = (api_key or settings.siliconflow_api_key).strip()
        if not self.api_base:
            raise SiliconFlowVoiceError("SiliconFlow base URL 未配置")
        if not self.api_key:
            raise SiliconFlowVoiceError("SiliconFlow API key 未配置")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _url(self, path: str) -> str:
        return f"{self.api_base}{path}"

    def upload_reference_voice(
        self,
        *,
        file_path: Path,
        model: str,
        custom_name: str,
        text: str,
        timeout: int,
    ) -> str:
        if not text.strip():
            raise SiliconFlowVoiceError("参考音频缺少参考文本，无法注册声音")
        if not file_path.exists() or file_path.stat().st_size <= 0:
            raise SiliconFlowVoiceError("参考音频本地文件不存在或为空")
        with file_path.open("rb") as handle:
            response = self.session.post(
                self._url("/uploads/audio/voice"),
                data={"model": model, "customName": custom_name, "text": text},
                files={"file": (file_path.name, handle, "audio/mpeg")},
                timeout=(15, timeout),
            )
        _raise_for_status(response)
        payload = _parse_json(response)
        voice_uri = str(payload.get("uri") or "").strip()
        if not voice_uri:
            raise SiliconFlowVoiceError(f"SiliconFlow 声音注册成功但未返回 uri：{payload}")
        return voice_uri

    def generate_speech(
        self,
        *,
        text: str,
        voice_uri: str,
        model: str,
        response_format: str,
        sample_rate: int,
        speed: float,
        gain: float,
        timeout: int,
    ) -> tuple[bytes, str]:
        if not text.strip():
            raise SiliconFlowVoiceError("旁白文本为空，无法生成音频")
        if not voice_uri.strip():
            raise SiliconFlowVoiceError("声音 voice uri 为空，无法生成音频")
        response = self.session.post(
            self._url("/audio/speech"),
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "input": text,
                "voice": voice_uri,
                "response_format": response_format,
                "sample_rate": sample_rate,
                "speed": speed,
                "gain": gain,
                "stream": False,
            },
            timeout=(15, timeout),
        )
        _raise_for_status(response)
        if not response.content:
            raise SiliconFlowVoiceError("SiliconFlow 音频生成返回空内容")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        return response.content, content_type or "audio/mpeg"
