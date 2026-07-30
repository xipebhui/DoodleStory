from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal
from app.models.entities import (
    NativeAgentConversation,
    NativeAgentRun,
    User,
    YoutubeChannel,
    YoutubeChannelBenchmark,
    YoutubeUploadedVideo,
)
from app.models.enums import UserRole


MAX_ACCOUNT_NAME_CHARS = 120
MAX_ACCOUNT_CANDIDATES = 5
MAX_BENCHMARKS = 10
MAX_RECENT_VIDEOS = 10
MAX_VIDEO_DESCRIPTION_CHARS = 2000
MAX_VIDEO_TAGS = 20


class AccountCreationContextError(RuntimeError):
    pass


class AccountCreationContextForbidden(AccountCreationContextError):
    pass


class AccountCreationContextDataError(AccountCreationContextError):
    pass


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def _normalized_handle(value: str | None) -> str:
    return _normalized(value).removeprefix("@")


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _candidate(channel: YoutubeChannel) -> dict[str, str | None]:
    return {
        "account_id": channel.id,
        "alias": channel.alias,
        "title": channel.title,
        "handle": channel.handle,
        "remote_channel_id": channel.channel_id,
        "remote_status": channel.remote_status,
    }


def _like_fragment(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _parse_video_tags(video: YoutubeUploadedVideo) -> list[str]:
    try:
        raw_tags = json.loads(video.tags_json)
    except json.JSONDecodeError as exc:
        raise AccountCreationContextDataError(
            f"账号历史视频 {video.id} 的 tags_json 不是合法 JSON"
        ) from exc
    if not isinstance(raw_tags, list) or not all(
        isinstance(tag, str) for tag in raw_tags
    ):
        raise AccountCreationContextDataError(
            f"账号历史视频 {video.id} 的 tags_json 必须是字符串数组"
        )
    return raw_tags[:MAX_VIDEO_TAGS]


def _video_payload(video: YoutubeUploadedVideo) -> dict[str, Any]:
    description = video.description or ""
    return {
        "video_id": video.id,
        "youtube_video_id": video.youtube_video_id,
        "title": video.title,
        "description": description[:MAX_VIDEO_DESCRIPTION_CHARS],
        "description_truncated": len(description) > MAX_VIDEO_DESCRIPTION_CHARS,
        "tags": _parse_video_tags(video),
        "visibility": video.visibility,
        "views": video.views,
        "likes": video.likes,
        "uploaded_at": _isoformat(video.uploaded_at),
        "remote_last_sync_at": _isoformat(video.remote_last_sync_at),
    }


def _resolved_payload(
    db: Session,
    *,
    channel: YoutubeChannel,
    query: str,
    matched_by: str,
) -> dict[str, Any]:
    benchmarks = db.scalars(
        select(YoutubeChannelBenchmark)
        .where(YoutubeChannelBenchmark.channel_id == channel.id)
        .order_by(
            YoutubeChannelBenchmark.updated_at.desc(),
            YoutubeChannelBenchmark.id,
        )
        .limit(MAX_BENCHMARKS)
    ).all()
    videos = db.scalars(
        select(YoutubeUploadedVideo)
        .where(YoutubeUploadedVideo.channel_id == channel.id)
        .order_by(
            YoutubeUploadedVideo.uploaded_at.desc(),
            YoutubeUploadedVideo.id,
        )
        .limit(MAX_RECENT_VIDEOS)
    ).all()
    strategy = {
        "account_positioning": channel.account_positioning,
        "target_audience": channel.target_audience,
        "stage_goal": channel.stage_goal,
        "ai_definition": channel.ai_definition,
        "operation_notes": channel.operation_notes,
    }
    missing_strategy_fields = [
        field_name
        for field_name, value in strategy.items()
        if not (value or "").strip()
    ]
    return {
        "status": "resolved",
        "query": query,
        "matched_by": matched_by,
        "account": _candidate(channel),
        "content_strategy": strategy,
        "channel_metrics": {
            "total_subscribers": channel.total_subscribers,
            "total_views": channel.total_views,
            "total_watch_time_hours": channel.total_watch_time_hours,
            "total_videos": channel.total_videos,
            "remote_last_sync_at": _isoformat(channel.remote_last_sync_at),
            "last_sync_success_at": _isoformat(channel.last_sync_success_at),
        },
        "benchmarks": [
            {
                "benchmark_id": benchmark.id,
                "platform": benchmark.platform,
                "name": benchmark.name,
                "platform_account_id": benchmark.platform_account_id,
                "profile_url": benchmark.profile_url,
                "notes": benchmark.notes,
            }
            for benchmark in benchmarks
        ],
        "recent_videos": [_video_payload(video) for video in videos],
        "data_quality": {
            "strategy_complete": not missing_strategy_fields,
            "missing_strategy_fields": missing_strategy_fields,
            "benchmark_count_returned": len(benchmarks),
            "recent_video_count_returned": len(videos),
            "has_reference_scripts": False,
        },
    }


def build_account_creation_context_snapshot(
    db: Session,
    *,
    channel: YoutubeChannel,
) -> dict[str, Any]:
    """Build the authoritative context for an explicitly selected account."""
    return _resolved_payload(
        db,
        channel=channel,
        query=channel.alias or channel.title,
        matched_by="selected_account_id",
    )


def get_account_creation_context(
    account_name: str,
    *,
    run_id: str,
    session_factory: sessionmaker = SessionLocal,
) -> dict[str, Any]:
    query = account_name.strip()
    if not query:
        raise AccountCreationContextError("账号名称不能为空")
    if len(query) > MAX_ACCOUNT_NAME_CHARS:
        raise AccountCreationContextError(
            f"账号名称不能超过 {MAX_ACCOUNT_NAME_CHARS} 字符"
        )

    normalized_name = _normalized(query)
    normalized_handle = _normalized_handle(query)
    with session_factory() as db:
        owner_role = db.scalar(
            select(User.role)
            .join(
                NativeAgentConversation,
                NativeAgentConversation.owner_user_id == User.id,
            )
            .join(
                NativeAgentRun,
                NativeAgentRun.conversation_id == NativeAgentConversation.id,
            )
            .where(NativeAgentRun.id == run_id)
        )
        if owner_role is None:
            raise AccountCreationContextError("Native Agent Run 不存在")
        if owner_role != UserRole.admin:
            raise AccountCreationContextForbidden(
                "只有管理员 Agent Run 可以读取平台账号创作上下文"
            )

        exact_match_queries = (
            (
                "alias",
                func.lower(YoutubeChannel.alias) == normalized_name,
            ),
            (
                "handle",
                or_(
                    func.lower(YoutubeChannel.handle) == normalized_name,
                    func.lower(YoutubeChannel.handle) == normalized_handle,
                    func.lower(YoutubeChannel.handle)
                    == f"@{normalized_handle}",
                ),
            ),
            (
                "title",
                func.lower(YoutubeChannel.title) == normalized_name,
            ),
            (
                "remote_channel_id",
                func.lower(YoutubeChannel.channel_id) == normalized_name,
            ),
        )
        for matched_by, condition in exact_match_queries:
            exact_channels = db.scalars(
                select(YoutubeChannel)
                .where(condition)
                .order_by(
                    YoutubeChannel.updated_at.desc(),
                    YoutubeChannel.id,
                )
                .limit(MAX_ACCOUNT_CANDIDATES + 1)
            ).all()
            if len(exact_channels) == 1:
                return _resolved_payload(
                    db,
                    channel=exact_channels[0],
                    query=query,
                    matched_by=matched_by,
                )
            if exact_channels:
                return {
                    "status": "needs_confirmation",
                    "reason": "multiple_exact_matches",
                    "query": query,
                    "candidates": [
                        _candidate(channel)
                        for channel in exact_channels[:MAX_ACCOUNT_CANDIDATES]
                    ],
                }

        escaped_name = _like_fragment(query)
        escaped_handle = _like_fragment(query.removeprefix("@"))
        fuzzy_conditions = [
            YoutubeChannel.alias.ilike(f"%{escaped_name}%", escape="\\"),
            YoutubeChannel.title.ilike(f"%{escaped_name}%", escape="\\"),
            YoutubeChannel.channel_id.ilike(
                f"%{escaped_name}%", escape="\\"
            ),
        ]
        if escaped_handle:
            fuzzy_conditions.append(
                YoutubeChannel.handle.ilike(
                    f"%{escaped_handle}%", escape="\\"
                )
            )
        fuzzy_channels = db.scalars(
            select(YoutubeChannel)
            .where(or_(*fuzzy_conditions))
            .order_by(YoutubeChannel.updated_at.desc(), YoutubeChannel.id)
            .limit(MAX_ACCOUNT_CANDIDATES)
        ).all()
        if fuzzy_channels:
            return {
                "status": "needs_confirmation",
                "reason": "partial_matches_only",
                "query": query,
                "candidates": [
                    _candidate(channel) for channel in fuzzy_channels
                ],
            }
        return {
            "status": "not_found",
            "query": query,
            "candidates": [],
        }
