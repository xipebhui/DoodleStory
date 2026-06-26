from __future__ import annotations

import time
from urllib.parse import urljoin

import requests

from app.core.config import get_settings


class ComicVideoServiceError(RuntimeError):
    pass


class ComicVideoServiceClient:
    def __init__(self, *, api_base: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_base = (api_base or settings.comic_video_service_base_url).strip().rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.comic_video_service_api_key).strip()
        if not self.api_base:
            raise ComicVideoServiceError("comic-video-studio 服务地址未配置")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    def _url(self, path: str) -> str:
        return f"{self.api_base}{path}"

    @staticmethod
    def _json(response: requests.Response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ComicVideoServiceError(f"comic-video-studio 返回非 JSON：{response.text[:500]}") from exc
        if not isinstance(payload, dict):
            raise ComicVideoServiceError("comic-video-studio 返回结构不是 JSON object")
        return payload

    def submit_episode(self, *, episode: dict, output_name: str, speed: float) -> str:
        response = self.session.post(
            self._url("/api/v1/jobs"),
            json={
                "episode": episode,
                "output_name": output_name,
                "priority": "normal",
                "speed": speed,
                "use_video_audio": False,
            },
            timeout=(15, 60),
        )
        if response.status_code >= 400:
            raise ComicVideoServiceError(f"comic-video-studio 创建任务失败：HTTP {response.status_code} {response.text[:500]}")
        payload = self._json(response)
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise ComicVideoServiceError(f"comic-video-studio 创建任务成功但未返回 job_id：{payload}")
        return job_id

    def poll_job(self, job_id: str, *, timeout_seconds: int, interval_seconds: float) -> dict:
        deadline = time.monotonic() + timeout_seconds
        last_payload: dict | None = None
        while True:
            response = self.session.get(self._url(f"/api/v1/jobs/{job_id}"), timeout=(15, 60))
            if response.status_code >= 400:
                raise ComicVideoServiceError(f"comic-video-studio 查询任务失败：HTTP {response.status_code} {response.text[:500]}")
            payload = self._json(response)
            last_payload = payload
            status = str(payload.get("status") or "").strip()
            if status == "succeeded":
                return payload
            if status in {"failed", "cancelled"}:
                error = payload.get("error") or payload.get("message") or payload.get("error_code") or "未知错误"
                raise ComicVideoServiceError(f"comic-video-studio 任务失败：status={status} error={error}")
            if time.monotonic() >= deadline:
                raise ComicVideoServiceError(f"comic-video-studio 任务超时：job_id={job_id} last_status={status}")
            time.sleep(interval_seconds)

        raise ComicVideoServiceError(f"comic-video-studio 任务未完成：{last_payload}")

    def download_output(self, output_url: str) -> bytes:
        if not output_url:
            raise ComicVideoServiceError("comic-video-studio 任务成功但未返回 output_url")
        url = output_url if output_url.startswith(("http://", "https://")) else urljoin(f"{self.api_base}/", output_url.lstrip("/"))
        response = self.session.get(url, timeout=(15, 300), stream=True)
        if response.status_code >= 400:
            raise ComicVideoServiceError(f"comic-video-studio 下载视频失败：HTTP {response.status_code} {response.text[:500]}")
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                chunks.append(chunk)
        content = b"".join(chunks)
        if not content:
            raise ComicVideoServiceError("comic-video-studio 下载视频返回空内容")
        return content
