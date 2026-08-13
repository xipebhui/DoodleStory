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
from app.models.enums import AgentSkillStatus, UserRole
from app.services.agent_skill_registry import DEFAULT_SKILL_ROOT, SkillRegistry
from app.services.agent_tool_runtime import create_default_tool_registry


SYSTEM_SKILL_SLUG = "idea-to-comic"
NATIVE_LOOP_SKILL_SLUG = "simple-image-story"
ARTICLE_TEAM_SKILL_SLUG = "article-creation-team"
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
    "generate_speech": (
        "生成语音",
        "把文本按六档可控倍速合成为固定火山引擎音色的音频，并保存到当前 Agent Run。",
    ),
    "generate_subtitles": (
        "生成字幕",
        "使用本地 OpenAI Whisper 为当前 Run 音频生成带时间轴的 WebVTT 字幕资产。",
    ),
    "generate_video_clip": (
        "生成 AI 视频短镜头",
        "使用 Grok Imagine 文生视频或当前会话单图生视频，保存为可播放 MP4。",
    ),
    "render_story_video": (
        "渲染故事视频",
        "用固定 Remotion 模板把图片、旁白、整段字幕和可选 BGM 渲染为竖屏 MP4。",
    ),
    "publish_youtube_video": (
        "发布 YouTube 视频",
        "提交界面中已明确选择并确认的频道与视频，立即返回异步发布任务。",
    ),
    "capture_wechat_article": (
        "微信公众号文章",
        "微信公众号 · 抓取文章正文、图片引用和来源元数据，并保存为可追踪素材。",
    ),
    "inspect_youtube_channel": (
        "读取 YouTube 频道",
        "YouTube · 读取频道与近期视频统计、标题、描述和评论，并下载头像与视频封面。",
    ),
    "get_account_creation_context": (
        "读取账号创作上下文",
        "根据账号别名、频道名或 Handle 读取本地账号定位、目标受众、阶段目标、AI 定义、运营备注、对标账号和近期视频。",
    ),
    "write_article": (
        "文案写作子 Agent",
        "把当前文案任务交给同一 Skill 中的 Writer 角色，返回并保存完整草稿。",
    ),
    "review_article": (
        "文案审稿子 Agent",
        "把用户要求和完整草稿交给同一 Skill 中的 Reviewer 角色，返回并保存审稿意见。",
    ),
    "submit_final_article": (
        "提交最终文案",
        "保存最终文案并暂停当前 Run，等待用户批准或提出修改意见。",
    ),
}
NATIVE_ONLY_TOOL_CATALOG = (
    {
        "name": "generate_speech",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "generate_subtitles",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "generate_video_clip",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "render_story_video",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "publish_youtube_video",
        "has_side_effects": True,
        "may_wait": False,
    },
    {
        "name": "capture_wechat_article",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "inspect_youtube_channel",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "get_account_creation_context",
        "has_side_effects": False,
        "may_wait": False,
    },
    {
        "name": "write_article",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "review_article",
        "has_side_effects": True,
        "may_wait": True,
    },
    {
        "name": "submit_final_article",
        "has_side_effects": True,
        "may_wait": True,
    },
)


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
    catalog = [
        *create_default_tool_registry().catalog(),
        *NATIVE_ONLY_TOOL_CATALOG,
    ]
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


def load_manageable_skill(
    db: Session,
    *,
    skill_id: str,
    user: User,
) -> AgentSkill:
    skill = load_visible_skill(db, skill_id=skill_id, user_id=user.id)
    if skill.owner_user_id == user.id:
        return skill
    if skill.owner_user_id is None and user.role == UserRole.admin:
        return skill
    raise AgentSkillForbiddenError("只有管理员可以改变系统 Skill 状态")


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


def archive_skill(
    db: Session,
    *,
    skill: AgentSkill,
    user: User,
) -> AgentSkill:
    if skill.owner_user_id != user.id and not (
        skill.owner_user_id is None and user.role == UserRole.admin
    ):
        raise AgentSkillForbiddenError("没有权限 Disable 这个 Skill")
    if skill.status != AgentSkillStatus.archived:
        skill.status = AgentSkillStatus.archived
        skill.archived_at = datetime.utcnow()
        db.commit()
        db.refresh(skill)
    return skill


def restore_skill(
    db: Session,
    *,
    skill: AgentSkill,
    user: User,
) -> AgentSkill:
    if skill.owner_user_id != user.id and not (
        skill.owner_user_id is None and user.role == UserRole.admin
    ):
        raise AgentSkillForbiddenError("没有权限 Enable 这个 Skill")
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


def seed_article_team_system_skill(
    db: Session,
    *,
    skill_root: Path = DEFAULT_SKILL_ROOT,
) -> AgentSkill:
    existing = db.scalar(
        select(AgentSkill).where(
            AgentSkill.owner_user_id.is_(None),
            AgentSkill.slug == ARTICLE_TEAM_SKILL_SLUG,
        )
    )
    if existing is not None:
        return existing
    package = SkillRegistry(skill_root).load(ARTICLE_TEAM_SKILL_SLUG)
    instructions = _runtime_skill_body(package.instructions)
    tool_names = validate_tool_names(
        ["write_article", "review_article", "submit_final_article"]
    )
    skill = AgentSkill(
        owner_user_id=None,
        slug=ARTICLE_TEAM_SKILL_SLUG,
        name="文案创作团队",
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
        seed_article_team_system_skill(db)
