from __future__ import annotations

from typing import Any

import requests

from app.core.config import Settings, get_settings


class YoutubePublisherError(RuntimeError):
    pass


class YoutubePublisherClient:
    def __init__(
        self,
        settings: Settings | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session or requests.Session()
        self.base_url = self.settings.ytb_publish_url.strip().rstrip("/")
        self.api_key = self.settings.ytb_publish_api_key.strip()
        if not self.base_url or not self.api_key:
            raise YoutubePublisherError("YouTube 发布服务配置不完整")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        headers["x-api-key"] = self.api_key
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.settings.ytb_publish_timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise YoutubePublisherError(f"YouTube 发布服务请求失败：{exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise YoutubePublisherError(
                f"YouTube 发布服务返回了无效 JSON（HTTP {response.status_code}）"
            ) from exc
        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise YoutubePublisherError(
                f"YouTube 发布服务返回 HTTP {response.status_code}：{message or '未知错误'}"
            )
        if not isinstance(payload, dict):
            raise YoutubePublisherError("YouTube 发布服务返回结构不正确")
        return payload

    def list_channels(self) -> list[dict[str, Any]]:
        payload = self._request(
            "POST",
            "/api/youtube/channel/v1/list",
            json={"where": None, "order": [["channel_id", "asc"]], "limit": 100},
        )
        datas = payload.get("datas")
        if not isinstance(datas, list):
            raise YoutubePublisherError("频道列表缺少 datas")
        return [item for item in datas if isinstance(item, dict)]

    def channel_analytics(self, channel_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/youtube/channel/v1/analytics/latest",
            params={"channel_id": channel_id},
        )

    def channel_videos(self, channel_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor: object | None = None
        for _page in range(100):
            body: dict[str, Any] = {
                "where": {"one": {"channel_id": {"=": channel_id}}},
                "order": [["uploaded_at", "desc"]],
                "limit": 100,
            }
            if cursor is not None:
                body["cursor"] = cursor
            payload = self._request(
                "POST",
                "/api/youtube/video/v1/list",
                json=body,
            )
            datas = payload.get("datas")
            if not isinstance(datas, list):
                raise YoutubePublisherError("已发布视频列表缺少 datas")
            for item in datas:
                if not isinstance(item, dict) or item.get("channel_id") != channel_id:
                    raise YoutubePublisherError("已发布视频响应包含其他频道数据")
                rows.append(item)
            cursor = payload.get("next")
            if cursor is None:
                return rows
        raise YoutubePublisherError("已发布视频分页超过 100 页，已停止同步")

