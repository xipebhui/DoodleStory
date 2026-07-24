from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AgentMessage,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    UserCharacter,
)
from app.models.enums import StyleStatus
from app.schemas.agent import AgentResourceKind, AgentResourceRef


class AgentResourceRoute(StrEnum):
    discussion = "discussion"
    create_comic = "create_comic"
    continue_task = "continue_task"


class AgentResourceResolutionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ResolvedAgentResources:
    refs: list[AgentResourceRef]
    route: AgentResourceRoute
    model_context: dict[str, object]
    style: Style | None
    characters: list[UserCharacter]
    task: GenerationTask | None
    panel: TaskPanel | None
    image_version: GeneratedImage | None


def parse_agent_resource_refs(raw: str | None) -> list[AgentResourceRef]:
    if raw is None:
        return []
    try:
        value = json.loads(raw)
        if not isinstance(value, list):
            raise TypeError
        return [AgentResourceRef.model_validate(item) for item in value]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AgentResourceResolutionError("Agent 消息资源引用数据损坏") from exc


def resource_context_from_saved_refs(refs: list[AgentResourceRef]) -> dict[str, object]:
    """Replay the immutable, user-safe snapshot captured when the turn was accepted.

    Sprint 114 style refs predate ``safe_summary`` but already contain a canonical
    database ID and display name. Those two controlled fields are sufficient for
    a minimal historical style snapshot; all Sprint 115 refs must carry the full
    safe summary produced by ``AgentResourceResolver``.
    """

    context: dict[str, object] = {}
    characters: list[dict[str, object]] = []
    for ref in refs:
        summary = ref.safe_summary
        if summary is None:
            if ref.kind != AgentResourceKind.style or not ref.display_name:
                raise AgentResourceResolutionError("历史消息缺少可安全重放的资源摘要")
            summary = {"id": ref.id, "name": ref.display_name}
        if ref.kind == AgentResourceKind.character:
            characters.append(summary)
        else:
            context[ref.kind.value] = summary
    if characters:
        context["characters"] = characters
    return context


class AgentResourceResolver:
    MAX_CHARACTERS = 3

    @staticmethod
    def _validate_combination(refs: list[AgentResourceRef]) -> None:
        keys = [(ref.kind, ref.id) for ref in refs]
        if len(set(keys)) != len(keys):
            raise AgentResourceResolutionError("同一个资源不能重复引用")
        grouped = {
            kind: [ref for ref in refs if ref.kind == kind]
            for kind in AgentResourceKind
        }
        if len(grouped[AgentResourceKind.style]) > 1:
            raise AgentResourceResolutionError("每条消息最多引用一个风格")
        if len(grouped[AgentResourceKind.character]) > AgentResourceResolver.MAX_CHARACTERS:
            raise AgentResourceResolutionError("每条消息最多引用 3 个角色")
        if len(grouped[AgentResourceKind.task]) > 1:
            raise AgentResourceResolutionError("每条消息最多引用一个任务")
        if len(grouped[AgentResourceKind.panel]) > 1:
            raise AgentResourceResolutionError("每条消息最多引用一个 Panel")
        if len(grouped[AgentResourceKind.image_version]) > 1:
            raise AgentResourceResolutionError("每条消息最多引用一个图片版本")
        has_task = bool(grouped[AgentResourceKind.task])
        has_panel = bool(grouped[AgentResourceKind.panel])
        has_image = bool(grouped[AgentResourceKind.image_version])
        if has_panel and not has_task:
            raise AgentResourceResolutionError("引用 Panel 时必须同时引用所属任务")
        if has_image and not has_panel:
            raise AgentResourceResolutionError("引用图片版本时必须同时引用所属 Panel 和任务")

    def resolve(
        self,
        db: Session,
        *,
        owner_user_id: str,
        refs: list[AgentResourceRef],
    ) -> ResolvedAgentResources:
        self._validate_combination(refs)
        ids_by_kind = {
            kind: [ref.id for ref in refs if ref.kind == kind]
            for kind in AgentResourceKind
        }

        styles = db.scalars(
            select(Style).where(
                Style.id.in_(ids_by_kind[AgentResourceKind.style]),
                Style.deleted_at.is_(None),
                Style.status == StyleStatus.active,
            )
        ).all() if ids_by_kind[AgentResourceKind.style] else []
        characters = db.scalars(
            select(UserCharacter).where(
                UserCharacter.id.in_(ids_by_kind[AgentResourceKind.character]),
                UserCharacter.owner_user_id == owner_user_id,
                UserCharacter.deleted_at.is_(None),
            )
        ).all() if ids_by_kind[AgentResourceKind.character] else []
        tasks = db.scalars(
            select(GenerationTask).where(
                GenerationTask.id.in_(ids_by_kind[AgentResourceKind.task]),
                GenerationTask.owner_user_id == owner_user_id,
            )
        ).all() if ids_by_kind[AgentResourceKind.task] else []
        panels = db.scalars(
            select(TaskPanel)
            .join(GenerationTask, GenerationTask.id == TaskPanel.task_id)
            .where(
                TaskPanel.id.in_(ids_by_kind[AgentResourceKind.panel]),
                GenerationTask.owner_user_id == owner_user_id,
            )
        ).all() if ids_by_kind[AgentResourceKind.panel] else []
        images = db.scalars(
            select(GeneratedImage)
            .join(GenerationTask, GenerationTask.id == GeneratedImage.task_id)
            .where(
                GeneratedImage.id.in_(ids_by_kind[AgentResourceKind.image_version]),
                GenerationTask.owner_user_id == owner_user_id,
                GeneratedImage.panel_id.is_not(None),
            )
        ).all() if ids_by_kind[AgentResourceKind.image_version] else []

        found = {
            AgentResourceKind.style: {item.id: item for item in styles},
            AgentResourceKind.character: {item.id: item for item in characters},
            AgentResourceKind.task: {item.id: item for item in tasks},
            AgentResourceKind.panel: {item.id: item for item in panels},
            AgentResourceKind.image_version: {item.id: item for item in images},
        }
        for ref in refs:
            if ref.id not in found[ref.kind]:
                raise AgentResourceResolutionError(
                    f"引用的{self._kind_label(ref.kind)}不存在、不可用或不属于当前用户",
                    status_code=403,
                )

        style = styles[0] if styles else None
        task = tasks[0] if tasks else None
        panel = panels[0] if panels else None
        image_version = images[0] if images else None
        if style is not None and task is None and not style.image_model_name.strip():
            raise AgentResourceResolutionError(
                "所选风格尚未绑定生图模型，不能用于创建新任务"
            )
        if panel is not None and (task is None or panel.task_id != task.id):
            raise AgentResourceResolutionError("所选 Panel 不属于引用的任务")
        if image_version is not None and (
            task is None
            or panel is None
            or image_version.panel_id != panel.id
            or image_version.task_id != task.id
        ):
            raise AgentResourceResolutionError("所选图片版本不属于引用的 Panel")

        panel_counts = {
            task_id: count
            for task_id, count in db.execute(
                select(TaskPanel.task_id, func.count(TaskPanel.id))
                .where(TaskPanel.task_id.in_([item.id for item in tasks]))
                .group_by(TaskPanel.task_id)
            ).all()
        } if tasks else {}
        summaries: dict[tuple[AgentResourceKind, str], tuple[str, dict[str, object]]] = {}
        for item in styles:
            summaries[(AgentResourceKind.style, item.id)] = (
                item.name,
                {
                    "id": item.id,
                    "name": item.name,
                    "status": item.status.value,
                    "aspect_ratio": item.aspect_ratio,
                },
            )
        for item in characters:
            summaries[(AgentResourceKind.character, item.id)] = (
                item.name,
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "reference_asset_id": item.reference_asset_id,
                },
            )
        for item in tasks:
            summaries[(AgentResourceKind.task, item.id)] = (
                item.display_title,
                {
                    "id": item.id,
                    "title": item.display_title,
                    "status": item.status.value,
                    "style_name": item.style_name_snapshot,
                    "panel_count": int(panel_counts.get(item.id, 0)),
                },
            )
        for item in panels:
            summaries[(AgentResourceKind.panel, item.id)] = (
                f"Panel {item.panel_order}",
                {
                    "id": item.id,
                    "task_id": item.task_id,
                    "panel_order": item.panel_order,
                    "story_beat": item.original_text_segment,
                    "visual_goal": item.text_layout,
                },
            )
        for item in images:
            panel_order = panel.panel_order if panel is not None else None
            summaries[(AgentResourceKind.image_version, item.id)] = (
                f"Panel {panel_order} · v{item.generation_number}",
                {
                    "id": item.id,
                    "panel_id": item.panel_id,
                    "generation_number": item.generation_number,
                    "status": item.status.value,
                    "is_current": item.is_current,
                    "asset_id": item.asset_id,
                },
            )

        canonical_refs = [
            ref.model_copy(
                update={
                    "display_name": summaries[(ref.kind, ref.id)][0],
                    "safe_summary": summaries[(ref.kind, ref.id)][1],
                }
            )
            for ref in refs
        ]
        model_context = resource_context_from_saved_refs(canonical_refs)
        if task is not None:
            route = AgentResourceRoute.continue_task
        elif style is not None:
            route = AgentResourceRoute.create_comic
        else:
            route = AgentResourceRoute.discussion
        return ResolvedAgentResources(
            refs=canonical_refs,
            route=route,
            model_context=model_context,
            style=style,
            characters=[
                found[AgentResourceKind.character][ref.id]
                for ref in refs
                if ref.kind == AgentResourceKind.character
            ],
            task=task,
            panel=panel,
            image_version=image_version,
        )

    @staticmethod
    def from_message(
        db: Session,
        *,
        owner_user_id: str,
        message: AgentMessage,
    ) -> ResolvedAgentResources:
        return AgentResourceResolver().resolve(
            db,
            owner_user_id=owner_user_id,
            refs=parse_agent_resource_refs(message.resource_refs_json),
        )

    @staticmethod
    def _kind_label(kind: AgentResourceKind) -> str:
        return {
            AgentResourceKind.style: "风格",
            AgentResourceKind.character: "角色",
            AgentResourceKind.task: "任务",
            AgentResourceKind.panel: "Panel",
            AgentResourceKind.image_version: "图片版本",
        }[kind]
