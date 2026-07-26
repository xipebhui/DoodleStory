from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import database
from app.models.entities import AgentRun, AgentSkill, AgentSkillVersion, User, new_id
from app.models.enums import AgentSkillStatus
from app.services.agent_skill_registry import DEFAULT_SKILL_ROOT, SkillRegistry
from app.services.agent_tool_runtime import create_default_tool_registry


SYSTEM_SKILL_SLUG = "idea-to-comic"
NATIVE_LOOP_SKILL_SLUG = "simple-image-story"
MAX_SKILL_INSTRUCTIONS_BYTES = 64 * 1024
TOOL_PRESENTATION = {
    "generate_image": (
        "生成图片",
        "根据已批准方案生成图片或为已有 Panel 创建新版本。",
    ),
    "inspect_image": (
        "检查图片",
        "检查故事匹配、人物一致性、文字准确性和明显视觉问题。",
    ),
}


class AgentSkillManagementError(RuntimeError):
    pass


class AgentSkillNotFoundError(AgentSkillManagementError):
    pass


class AgentSkillForbiddenError(AgentSkillManagementError):
    pass


class AgentSkillConflictError(AgentSkillManagementError):
    pass


class AgentSkillValidationError(AgentSkillManagementError):
    pass


@dataclass(frozen=True)
class SkillPage:
    items: list[AgentSkill]
    total: int


@dataclass(frozen=True)
class SkillVersionPage:
    items: list[AgentSkillVersion]
    total: int


def _json_array(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def parse_tool_names(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AgentSkillManagementError("Skill Tool 白名单数据损坏") from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AgentSkillManagementError("Skill Tool 白名单数据损坏")
    return value


def selectable_tool_catalog() -> list[dict[str, object]]:
    catalog = create_default_tool_registry().catalog()
    result: list[dict[str, object]] = []
    for item in catalog:
        name = str(item["name"])
        if name not in TOOL_PRESENTATION:
            continue
        display_name, description = TOOL_PRESENTATION[name]
        result.append(
            {
                "name": name,
                "display_name": display_name,
                "description": description,
                "has_side_effects": bool(item["has_side_effects"]),
                "may_wait": bool(item["may_wait"]),
            }
        )
    return sorted(result, key=lambda item: str(item["name"]))


def validate_tool_names(tool_names: list[str]) -> list[str]:
    allowed = {str(item["name"]) for item in selectable_tool_catalog()}
    normalized = sorted(set(tool_names))
    if len(tool_names) != len(normalized):
        raise AgentSkillValidationError("Tool 列表不能包含重复项")
    unknown = [name for name in normalized if name not in allowed]
    if unknown:
        raise AgentSkillValidationError(
            f"Skill 包含不可用 Tool: {', '.join(unknown)}"
        )
    if len(normalized) > len(allowed):
        raise AgentSkillValidationError("Skill Tool 数量超过 Runtime 上限")
    return normalized


def validate_skill_fields(
    *,
    name: str,
    description: str,
    instructions: str,
    tool_names: list[str],
) -> tuple[str, str, str, list[str]]:
    normalized_name = name.strip()
    normalized_description = description.strip()
    if not normalized_name or len(normalized_name) > 120:
        raise AgentSkillValidationError("Skill 名称必须为 1–120 字")
    if not normalized_description or len(normalized_description) > 500:
        raise AgentSkillValidationError("Skill 简介必须为 1–500 字")
    if not instructions.strip():
        raise AgentSkillValidationError("Skill 正文不能为空")
    if len(instructions.encode("utf-8")) > MAX_SKILL_INSTRUCTIONS_BYTES:
        raise AgentSkillValidationError("Skill 正文不能超过 64 KiB")
    normalized_tools = validate_tool_names(tool_names)
    return (
        normalized_name,
        normalized_description,
        instructions,
        normalized_tools,
    )


def validate_publishable_instructions(instructions: str) -> None:
    meaningful_lines = [
        line.strip()
        for line in instructions.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(instructions.strip()) < 40 or len(meaningful_lines) < 2:
        raise AgentSkillValidationError(
            "Skill 正文需要清楚说明目标和执行方法后才能发布"
        )


def compute_skill_content_hash(
    *,
    name: str,
    description: str,
    instructions: str,
    tool_names: list[str],
) -> str:
    canonical = json.dumps(
        {
            "description": description,
            "instructions": instructions,
            "name": name,
            "tool_names": sorted(tool_names),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def load_visible_skill(db: Session, *, skill_id: str, user_id: str) -> AgentSkill:
    skill = db.scalar(
        select(AgentSkill).where(
            AgentSkill.id == skill_id,
            or_(
                AgentSkill.owner_user_id == user_id,
                AgentSkill.owner_user_id.is_(None),
            ),
        )
    )
    if skill is None:
        raise AgentSkillNotFoundError("Skill 不存在")
    return skill


def load_owned_skill(db: Session, *, skill_id: str, user_id: str) -> AgentSkill:
    skill = db.scalar(
        select(AgentSkill).where(
            AgentSkill.id == skill_id,
            AgentSkill.owner_user_id == user_id,
        )
    )
    if skill is None:
        raise AgentSkillNotFoundError("Skill 不存在")
    return skill


def list_skills(
    db: Session,
    *,
    user_id: str,
    scope: str,
    status: AgentSkillStatus | None,
    query: str | None,
    page: int,
    page_size: int,
) -> SkillPage:
    if scope not in {"mine", "system"}:
        raise AgentSkillValidationError("scope 必须是 mine 或 system")
    filters = [
        (
            AgentSkill.owner_user_id == user_id
            if scope == "mine"
            else AgentSkill.owner_user_id.is_(None)
        )
    ]
    if status is not None:
        filters.append(AgentSkill.status == status)
    elif scope == "mine":
        filters.append(AgentSkill.status != AgentSkillStatus.archived)
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(
                AgentSkill.name.ilike(pattern),
                AgentSkill.description.ilike(pattern),
            )
        )
    total = int(
        db.scalar(select(func.count()).select_from(AgentSkill).where(*filters)) or 0
    )
    items = list(
        db.scalars(
            select(AgentSkill)
            .where(*filters)
            .order_by(AgentSkill.updated_at.desc(), AgentSkill.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return SkillPage(items=items, total=total)


def create_skill(
    db: Session,
    *,
    user: User,
    name: str,
    description: str,
    instructions: str,
    tool_names: list[str],
) -> AgentSkill:
    name, description, instructions, tool_names = validate_skill_fields(
        name=name,
        description=description,
        instructions=instructions,
        tool_names=tool_names,
    )
    skill_id = new_id()
    skill = AgentSkill(
        id=skill_id,
        owner_user_id=user.id,
        slug=f"skill-{skill_id[:12]}",
        name=name,
        description=description,
        draft_instructions=instructions,
        draft_tool_names_json=_json_array(tool_names),
        draft_revision=1,
        status=AgentSkillStatus.draft,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def update_skill_draft(
    db: Session,
    *,
    skill: AgentSkill,
    expected_draft_revision: int,
    name: str,
    description: str,
    instructions: str,
    tool_names: list[str],
) -> AgentSkill:
    if skill.status == AgentSkillStatus.archived:
        raise AgentSkillConflictError("已归档 Skill 不能编辑，请先恢复")
    if skill.owner_user_id is None:
        raise AgentSkillForbiddenError("系统 Skill 为只读")
    if skill.draft_revision != expected_draft_revision:
        raise AgentSkillConflictError(
            "草稿已在其他页面更新，请刷新后合并修改"
        )
    name, description, instructions, tool_names = validate_skill_fields(
        name=name,
        description=description,
        instructions=instructions,
        tool_names=tool_names,
    )
    skill.name = name
    skill.description = description
    skill.draft_instructions = instructions
    skill.draft_tool_names_json = _json_array(tool_names)
    skill.draft_revision += 1
    db.commit()
    db.refresh(skill)
    return skill


def publish_skill(
    db: Session,
    *,
    skill: AgentSkill,
    user: User,
    expected_draft_revision: int,
    idempotency_key: str,
) -> AgentSkillVersion:
    if skill.owner_user_id is None:
        raise AgentSkillForbiddenError("系统 Skill 不能由普通用户发布")
    if skill.status == AgentSkillStatus.archived:
        raise AgentSkillConflictError("已归档 Skill 不能发布，请先恢复")
    existing = db.scalar(
        select(AgentSkillVersion).where(
            AgentSkillVersion.skill_id == skill.id,
            AgentSkillVersion.publish_idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    if skill.draft_revision != expected_draft_revision:
        raise AgentSkillConflictError(
            "草稿已在其他页面更新，请刷新后再发布"
        )
    tool_names = validate_tool_names(parse_tool_names(skill.draft_tool_names_json))
    validate_publishable_instructions(skill.draft_instructions)
    next_version = int(
        db.scalar(
            select(func.max(AgentSkillVersion.version)).where(
                AgentSkillVersion.skill_id == skill.id
            )
        )
        or 0
    ) + 1
    version = AgentSkillVersion(
        skill_id=skill.id,
        version=next_version,
        name_snapshot=skill.name,
        description_snapshot=skill.description,
        instructions=skill.draft_instructions,
        tool_names_json=_json_array(tool_names),
        content_hash=compute_skill_content_hash(
            name=skill.name,
            description=skill.description,
            instructions=skill.draft_instructions,
            tool_names=tool_names,
        ),
        publish_idempotency_key=idempotency_key,
        published_by_user_id=user.id,
    )
    db.add(version)
    db.flush()
    skill.active_version_id = version.id
    skill.status = AgentSkillStatus.published
    skill.archived_at = None
    db.commit()
    db.refresh(version)
    return version


def list_skill_versions(
    db: Session,
    *,
    skill: AgentSkill,
    page: int,
    page_size: int,
) -> SkillVersionPage:
    total = int(
        db.scalar(
            select(func.count())
            .select_from(AgentSkillVersion)
            .where(AgentSkillVersion.skill_id == skill.id)
        )
        or 0
    )
    items = list(
        db.scalars(
            select(AgentSkillVersion)
            .where(AgentSkillVersion.skill_id == skill.id)
            .order_by(
                AgentSkillVersion.version.desc(),
                AgentSkillVersion.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return SkillVersionPage(items=items, total=total)


def load_skill_version(
    db: Session,
    *,
    skill: AgentSkill,
    version_id: str,
) -> AgentSkillVersion:
    version = db.scalar(
        select(AgentSkillVersion).where(
            AgentSkillVersion.id == version_id,
            AgentSkillVersion.skill_id == skill.id,
        )
    )
    if version is None:
        raise AgentSkillNotFoundError("Skill 版本不存在")
    return version


def activate_skill_version(
    db: Session,
    *,
    skill: AgentSkill,
    version: AgentSkillVersion,
) -> AgentSkill:
    if skill.owner_user_id is None:
        raise AgentSkillForbiddenError("系统 Skill 不能由普通用户切换版本")
    if skill.status == AgentSkillStatus.archived:
        raise AgentSkillConflictError("已归档 Skill 不能切换版本，请先恢复")
    if version.skill_id != skill.id:
        raise AgentSkillConflictError("Skill 版本归属不一致")
    skill.active_version_id = version.id
    skill.status = AgentSkillStatus.published
    db.commit()
    db.refresh(skill)
    return skill


def archive_skill(db: Session, *, skill: AgentSkill) -> AgentSkill:
    if skill.owner_user_id is None:
        raise AgentSkillForbiddenError("系统 Skill 不能归档")
    if skill.status != AgentSkillStatus.archived:
        skill.status = AgentSkillStatus.archived
        skill.archived_at = datetime.utcnow()
        db.commit()
        db.refresh(skill)
    return skill


def restore_skill(db: Session, *, skill: AgentSkill) -> AgentSkill:
    if skill.owner_user_id is None:
        raise AgentSkillForbiddenError("系统 Skill 不需要恢复")
    if skill.status == AgentSkillStatus.archived:
        skill.status = (
            AgentSkillStatus.published
            if skill.active_version_id is not None
            else AgentSkillStatus.draft
        )
        skill.archived_at = None
        db.commit()
        db.refresh(skill)
    return skill


def delete_unpublished_skill(db: Session, *, skill: AgentSkill) -> None:
    if skill.owner_user_id is None:
        raise AgentSkillForbiddenError("系统 Skill 不能删除")
    version_count = int(
        db.scalar(
            select(func.count())
            .select_from(AgentSkillVersion)
            .where(AgentSkillVersion.skill_id == skill.id)
        )
        or 0
    )
    run_count = int(
        db.scalar(
            select(func.count())
            .select_from(AgentRun)
            .join(
                AgentSkillVersion,
                AgentSkillVersion.id == AgentRun.skill_version_id,
            )
            .where(AgentSkillVersion.skill_id == skill.id)
        )
        or 0
    )
    if version_count or run_count:
        raise AgentSkillConflictError(
            "已发布或已被 Run 引用的 Skill 不能删除，请改用归档"
        )
    db.delete(skill)
    db.commit()


def clone_skill_version(
    db: Session,
    *,
    source_skill: AgentSkill,
    source_version: AgentSkillVersion,
    user: User,
) -> AgentSkill:
    if source_version.skill_id != source_skill.id:
        raise AgentSkillConflictError("Skill 版本归属不一致")
    return create_skill(
        db,
        user=user,
        name=f"{source_version.name_snapshot} 副本",
        description=source_version.description_snapshot,
        instructions=source_version.instructions,
        tool_names=parse_tool_names(source_version.tool_names_json),
    )


def _runtime_skill_body(raw: str) -> str:
    lines = raw.splitlines()
    if not lines or lines[0] != "---":
        raise AgentSkillValidationError("系统 Skill 文件缺少 frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise AgentSkillValidationError("系统 Skill frontmatter 未闭合") from exc
    body = "\n".join(lines[closing + 1 :]).strip()
    if not body:
        raise AgentSkillValidationError("系统 Skill 正文不能为空")
    return body


def seed_system_skills(db: Session, *, skill_root: Path = DEFAULT_SKILL_ROOT) -> AgentSkill:
    existing = db.scalar(
        select(AgentSkill).where(
            AgentSkill.owner_user_id.is_(None),
            AgentSkill.slug == SYSTEM_SKILL_SLUG,
        )
    )
    if existing is not None:
        return existing
    package = SkillRegistry(skill_root).load(SYSTEM_SKILL_SLUG)
    instructions = _runtime_skill_body(package.instructions)
    tool_names = validate_tool_names(["generate_image", "inspect_image"])
    skill = AgentSkill(
        owner_user_id=None,
        slug=SYSTEM_SKILL_SLUG,
        name="想法转漫画",
        description=package.description,
        draft_instructions=instructions,
        draft_tool_names_json=_json_array(tool_names),
        draft_revision=1,
        status=AgentSkillStatus.published,
    )
    db.add(skill)
    db.flush()
    version = AgentSkillVersion(
        skill_id=skill.id,
        version=1,
        name_snapshot=skill.name,
        description_snapshot=skill.description,
        instructions=instructions,
        tool_names_json=_json_array(tool_names),
        content_hash=compute_skill_content_hash(
            name=skill.name,
            description=skill.description,
            instructions=instructions,
            tool_names=tool_names,
        ),
        published_by_user_id=None,
    )
    db.add(version)
    db.flush()
    skill.active_version_id = version.id
    db.commit()
    db.refresh(skill)
    return skill


def seed_native_loop_system_skill(
    db: Session,
    *,
    skill_root: Path = DEFAULT_SKILL_ROOT,
) -> AgentSkill:
    existing = db.scalar(
        select(AgentSkill).where(
            AgentSkill.owner_user_id.is_(None),
            AgentSkill.slug == NATIVE_LOOP_SKILL_SLUG,
        )
    )
    if existing is not None:
        return existing
    package = SkillRegistry(skill_root).load(NATIVE_LOOP_SKILL_SLUG)
    instructions = _runtime_skill_body(package.instructions)
    tool_names = validate_tool_names(["generate_image"])
    skill = AgentSkill(
        owner_user_id=None,
        slug=NATIVE_LOOP_SKILL_SLUG,
        name="简单图片故事",
        description=package.description,
        draft_instructions=instructions,
        draft_tool_names_json=_json_array(tool_names),
        draft_revision=1,
        status=AgentSkillStatus.published,
    )
    db.add(skill)
    db.flush()
    version = AgentSkillVersion(
        skill_id=skill.id,
        version=1,
        name_snapshot=skill.name,
        description_snapshot=skill.description,
        instructions=instructions,
        tool_names_json=_json_array(tool_names),
        content_hash=compute_skill_content_hash(
            name=skill.name,
            description=skill.description,
            instructions=instructions,
            tool_names=tool_names,
        ),
        published_by_user_id=None,
    )
    db.add(version)
    db.flush()
    skill.active_version_id = version.id
    db.commit()
    db.refresh(skill)
    return skill


def initialize_system_agent_skills() -> None:
    with database.SessionLocal() as db:
        seed_system_skills(db)
        seed_native_loop_system_skill(db)
