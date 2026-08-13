from __future__ import annotations

from collections.abc import Collection

from app.services.native_agent_model_routes import (
    SILICONFLOW_CHAT_ROUTE,
    NativeAgentModelRouteSnapshot,
)


SILICONFLOW_S03_TOOL_PROFILE = frozenset(
    {"generate_image", "inspect_image"}
)


class NativeAgentRouteCapabilityError(RuntimeError):
    """Raised when a route is selected outside its approved capability profile."""


def validate_native_agent_route_capability(
    route: NativeAgentModelRouteSnapshot,
    *,
    selected_tool_names: Collection[str],
    style_id: str | None,
    creation_channel_id: str | None,
    youtube_channel_id: str | None,
    youtube_publishable_video_id: str | None,
    has_youtube_publish_confirmation: bool,
) -> None:
    if route.route != SILICONFLOW_CHAT_ROUTE:
        return
    if set(selected_tool_names) != SILICONFLOW_S03_TOOL_PROFILE:
        raise NativeAgentRouteCapabilityError(
            "SiliconFlow Chat 仅允许 generate_image + inspect_image 的 S03 Tool Profile"
        )
    if style_id is None:
        raise NativeAgentRouteCapabilityError(
            "SiliconFlow Chat S03 Run 必须选择可用 Style"
        )
    if any(
        value is not None
        for value in (
            creation_channel_id,
            youtube_channel_id,
            youtube_publishable_video_id,
        )
    ) or has_youtube_publish_confirmation:
        raise NativeAgentRouteCapabilityError(
            "SiliconFlow Chat S03 Run 不允许携带创作账号或 YouTube 发布上下文"
        )
