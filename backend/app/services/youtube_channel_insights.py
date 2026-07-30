from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
import requests

from app.services.social_content_import import social_content_import_base_url


YOUTUBE_CHANNEL_INSIGHTS_TIMEOUT_SECONDS = 180
YoutubeCommentOrder = Literal["relevance", "time"]


class YoutubeChannelInsightsError(RuntimeError):
    pass


class YoutubeInsightImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    width: int | None
    height: int | None
    file_path: Path
    content_type: str
    byte_size: int = Field(gt=0)


class YoutubeInsightComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    author: str
    text: str
    like_count: int = Field(ge=0)
    reply_count: int = Field(ge=0)
    published_at: str
    updated_at: str


class YoutubeInsightVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: str
    title: str
    description: str
    tags: list[str]
    published_at: str
    duration: str
    definition: str
    caption_available: bool
    privacy_status: str
    view_count: int = Field(ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    thumbnail: YoutubeInsightImage
    comments: list[YoutubeInsightComment]


class YoutubeInsightChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: str
    title: str
    handle: str | None
    description: str
    country: str | None
    created_at: str
    subscriber_count: int | None = Field(default=None, ge=0)
    hidden_subscriber_count: bool
    view_count: int = Field(ge=0)
    video_count: int = Field(ge=0)
    privacy_status: str
    made_for_kids: bool | None
    keywords: str | None
    topic_categories: list[str]
    avatar: YoutubeInsightImage


class YoutubeChannelInsightsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: str
    output_dir: Path
    request: dict[str, object]
    channel: YoutubeInsightChannel
    videos: list[YoutubeInsightVideo]


def _validate_downloaded_image(
    image: YoutubeInsightImage,
    *,
    output_dir: Path,
) -> None:
    resolved = image.file_path.expanduser().resolve()
    try:
        resolved.relative_to(output_dir)
    except ValueError as exc:
        raise YoutubeChannelInsightsError(
            "YouTube Import 服务返回的图片不在任务输出目录内"
        ) from exc
    if not resolved.is_file():
        raise YoutubeChannelInsightsError(
            "YouTube Import 服务返回的图片文件不存在"
        )


def fetch_youtube_channel_insights(
    channel: str,
    *,
    video_limit: int = 1,
    comments_per_video: int = 2,
    comment_order: YoutubeCommentOrder = "relevance",
) -> YoutubeChannelInsightsResult:
    try:
        response = requests.post(
            f"{social_content_import_base_url()}/api/v1/youtube/channel-insights",
            json={
                "channel": channel,
                "video_limit": video_limit,
                "comments_per_video": comments_per_video,
                "comment_order": comment_order,
            },
            timeout=YOUTUBE_CHANNEL_INSIGHTS_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise YoutubeChannelInsightsError(
            "多平台素材导入服务的 YouTube 接口不可用"
        ) from exc
    if response.status_code in {400, 502}:
        try:
            payload = response.json()
            detail = payload.get("detail") if isinstance(payload, dict) else None
        except ValueError:
            detail = response.text
        raise YoutubeChannelInsightsError(
            f"YouTube 频道读取失败：{detail or f'HTTP {response.status_code}'}"
        )
    if response.status_code != 200:
        raise YoutubeChannelInsightsError(
            f"多平台素材导入服务的 YouTube 接口返回异常：HTTP {response.status_code}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise YoutubeChannelInsightsError(
            "多平台素材导入服务的 YouTube 响应不是合法 JSON"
        ) from exc
    try:
        result = YoutubeChannelInsightsResult.model_validate(payload)
    except ValidationError as exc:
        raise YoutubeChannelInsightsError(
            "多平台素材导入服务的 YouTube 响应结构不合法"
        ) from exc

    output_dir = result.output_dir.expanduser().resolve()
    _validate_downloaded_image(result.channel.avatar, output_dir=output_dir)
    for video in result.videos:
        _validate_downloaded_image(video.thumbnail, output_dir=output_dir)
    return result
