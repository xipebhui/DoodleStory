from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import AgentSkill, AgentSkillVersion, User
from app.models.enums import AgentSkillStatus
from app.schemas.agent_skill import (
    AgentSkillClone,
    AgentSkillAuthoringRequest,
    AgentSkillAuthoringSuggestion,
    AgentSkillCreate,
    AgentSkillDetail,
    AgentSkillDraftUpdate,
    AgentSkillListPage,
    AgentSkillPublish,
    AgentSkillSummary,
    AgentSkillToolRead,
    AgentSkillVersionDetail,
    AgentSkillVersionListPage,
    AgentSkillVersionSummary,
)
from app.schemas.common import ApiData
from app.services.agent_skill_management import (
    AgentSkillConflictError,
    AgentSkillForbiddenError,
    AgentSkillManagementError,
    AgentSkillNotFoundError,
    AgentSkillValidationError,
    activate_skill_version,
    archive_skill,
    clone_skill_version,
    create_skill,
    delete_unpublished_skill,
    list_skill_versions,
    list_skills,
    load_owned_skill,
    load_skill_version,
    load_visible_skill,
    parse_tool_names,
    publish_skill,
    restore_skill,
    selectable_tool_catalog,
    update_skill_draft,
    validate_tool_names,
)
from app.services.agent_model_router import (
    AgentModelFailure,
    AgentModelResult,
    AgentModelRoute,
    AgentModelRouter,
    AgentModelRoutingError,
)


router = APIRouter(prefix="/agent/skills", tags=["agent-skills"])


class SkillAuthoringObserver:
    run_id = None

    async def attempt_started(self, route: AgentModelRoute) -> None:
        del route
        return None

    async def attempt_succeeded(
        self,
        route: AgentModelRoute,
        result: AgentModelResult,
        latency_ms: int,
    ) -> None:
        del route, result, latency_ms

    async def attempt_failed(
        self,
        route: AgentModelRoute,
        failure: AgentModelFailure,
        latency_ms: int,
    ) -> None:
        del route, failure, latency_ms


def _raise_service_error(exc: AgentSkillManagementError) -> None:
    if isinstance(exc, AgentSkillNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, AgentSkillForbiddenError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, AgentSkillConflictError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(exc, AgentSkillValidationError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def _version_summary(
    version: AgentSkillVersion,
    *,
    active_version_id: str | None,
) -> AgentSkillVersionSummary:
    return AgentSkillVersionSummary(
        id=version.id,
        version=version.version,
        name=version.name_snapshot,
        description=version.description_snapshot,
        tool_names=parse_tool_names(version.tool_names_json),
        content_hash=version.content_hash,
        published_at=version.published_at,
        is_active=version.id == active_version_id,
    )


def _skill_summary(skill: AgentSkill) -> AgentSkillSummary:
    return AgentSkillSummary(
        id=skill.id,
        scope="system" if skill.owner_user_id is None else "mine",
        name=skill.name,
        description=skill.description,
        status=skill.status,
        tool_names=parse_tool_names(skill.draft_tool_names_json),
        draft_revision=skill.draft_revision,
        active_version=(
            _version_summary(
                skill.active_version,
                active_version_id=skill.active_version_id,
            )
            if skill.active_version is not None
            else None
        ),
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _skill_detail(skill: AgentSkill) -> AgentSkillDetail:
    summary = _skill_summary(skill)
    return AgentSkillDetail(
        **summary.model_dump(),
        instructions=skill.draft_instructions,
        archived_at=skill.archived_at,
        is_read_only=skill.owner_user_id is None,
    )


@router.get("/tool-catalog", response_model=ApiData[list[AgentSkillToolRead]])
def get_tool_catalog(
    user: User = Depends(current_user),
) -> ApiData[list[AgentSkillToolRead]]:
    del user
    return ApiData(
        data=[
            AgentSkillToolRead.model_validate(item)
            for item in selectable_tool_catalog()
        ]
    )


@router.post(
    "/authoring-assistance",
    response_model=ApiData[AgentSkillAuthoringSuggestion],
)
async def post_authoring_assistance(
    payload: AgentSkillAuthoringRequest,
    user: User = Depends(current_user),
) -> ApiData[AgentSkillAuthoringSuggestion]:
    del user
    try:
        selected_tools = validate_tool_names(payload.selected_tool_names)
        result = await AgentModelRouter().run_skill_authoring(
            [
                {
                    "role": "user",
                    "content": (
                        "请生成或优化一份 Skill 草稿建议。\n"
                        f"goal: {payload.goal}\n"
                        f"selected_tool_names: {selected_tools}\n"
                        "current_instructions:\n"
                        f"{payload.current_instructions or '（无）'}"
                    ),
                }
            ],
            SkillAuthoringObserver(),
        )
        suggestion = AgentSkillAuthoringSuggestion.model_validate(
            result.structured_output
        )
        suggested_tools = validate_tool_names(suggestion.suggested_tool_names)
        expanded = sorted(set(suggested_tools).difference(selected_tools))
        if expanded:
            raise AgentSkillValidationError(
                f"AI 建议扩大了 Tool 白名单: {', '.join(expanded)}"
            )
        suggestion.suggested_tool_names = suggested_tools
    except AgentModelRoutingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.failure.safe_message,
        ) from exc
    except (AgentSkillManagementError, ValueError) as exc:
        if isinstance(exc, AgentSkillManagementError):
            _raise_service_error(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 返回的 Skill 建议不符合约束",
        ) from exc
    return ApiData(data=suggestion)


@router.get("", response_model=ApiData[AgentSkillListPage])
def get_skills(
    scope: str = Query(default="mine", pattern=r"^(mine|system)$"),
    skill_status: AgentSkillStatus | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillListPage]:
    try:
        result = list_skills(
            db,
            user_id=user.id,
            scope=scope,
            status=skill_status,
            query=query,
            page=page,
            page_size=page_size,
        )
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(
        data=AgentSkillListPage(
            items=[_skill_summary(skill) for skill in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
            has_more=page * page_size < result.total,
        )
    )


@router.post("", response_model=ApiData[AgentSkillDetail], status_code=status.HTTP_201_CREATED)
def post_skill(
    payload: AgentSkillCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        skill = create_skill(db, user=user, **payload.model_dump())
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(skill))


@router.get("/{skill_id}", response_model=ApiData[AgentSkillDetail])
def get_skill(
    skill_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        skill = load_visible_skill(db, skill_id=skill_id, user_id=user.id)
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(skill))


@router.patch("/{skill_id}", response_model=ApiData[AgentSkillDetail])
def patch_skill(
    skill_id: str,
    payload: AgentSkillDraftUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        skill = load_owned_skill(db, skill_id=skill_id, user_id=user.id)
        skill = update_skill_draft(db, skill=skill, **payload.model_dump())
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(skill))


@router.post("/{skill_id}/publish", response_model=ApiData[AgentSkillVersionDetail])
def post_publish_skill(
    skill_id: str,
    payload: AgentSkillPublish,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillVersionDetail]:
    try:
        skill = load_owned_skill(db, skill_id=skill_id, user_id=user.id)
        version = publish_skill(db, skill=skill, user=user, **payload.model_dump())
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    summary = _version_summary(version, active_version_id=version.id)
    return ApiData(
        data=AgentSkillVersionDetail(
            **summary.model_dump(),
            skill_id=skill.id,
            instructions=version.instructions,
        )
    )


@router.get("/{skill_id}/versions", response_model=ApiData[AgentSkillVersionListPage])
def get_skill_versions(
    skill_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillVersionListPage]:
    try:
        skill = load_visible_skill(db, skill_id=skill_id, user_id=user.id)
        result = list_skill_versions(
            db,
            skill=skill,
            page=page,
            page_size=page_size,
        )
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(
        data=AgentSkillVersionListPage(
            items=[
                _version_summary(
                    version,
                    active_version_id=skill.active_version_id,
                )
                for version in result.items
            ],
            page=page,
            page_size=page_size,
            total=result.total,
            has_more=page * page_size < result.total,
        )
    )


@router.get(
    "/{skill_id}/versions/{version_id}",
    response_model=ApiData[AgentSkillVersionDetail],
)
def get_skill_version(
    skill_id: str,
    version_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillVersionDetail]:
    try:
        skill = load_visible_skill(db, skill_id=skill_id, user_id=user.id)
        version = load_skill_version(db, skill=skill, version_id=version_id)
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    summary = _version_summary(
        version,
        active_version_id=skill.active_version_id,
    )
    return ApiData(
        data=AgentSkillVersionDetail(
            **summary.model_dump(),
            skill_id=skill.id,
            instructions=version.instructions,
        )
    )


@router.post(
    "/{skill_id}/versions/{version_id}/activate",
    response_model=ApiData[AgentSkillDetail],
)
def post_activate_skill_version(
    skill_id: str,
    version_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        skill = load_owned_skill(db, skill_id=skill_id, user_id=user.id)
        version = load_skill_version(db, skill=skill, version_id=version_id)
        skill = activate_skill_version(db, skill=skill, version=version)
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(skill))


@router.post("/{skill_id}/archive", response_model=ApiData[AgentSkillDetail])
def post_archive_skill(
    skill_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        skill = load_owned_skill(db, skill_id=skill_id, user_id=user.id)
        skill = archive_skill(db, skill=skill)
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(skill))


@router.post("/{skill_id}/restore", response_model=ApiData[AgentSkillDetail])
def post_restore_skill(
    skill_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        skill = load_owned_skill(db, skill_id=skill_id, user_id=user.id)
        skill = restore_skill(db, skill=skill)
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(skill))


@router.post("/{skill_id}/clone", response_model=ApiData[AgentSkillDetail], status_code=status.HTTP_201_CREATED)
def post_clone_skill(
    skill_id: str,
    payload: AgentSkillClone,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentSkillDetail]:
    try:
        source_skill = load_visible_skill(db, skill_id=skill_id, user_id=user.id)
        version_id = payload.version_id or source_skill.active_version_id
        if version_id is None:
            raise AgentSkillConflictError("Skill 尚无可复制的发布版本")
        source_version = load_skill_version(
            db,
            skill=source_skill,
            version_id=version_id,
        )
        cloned = clone_skill_version(
            db,
            source_skill=source_skill,
            source_version=source_version,
            user=user,
        )
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return ApiData(data=_skill_detail(cloned))


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    skill_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        skill = load_owned_skill(db, skill_id=skill_id, user_id=user.id)
        delete_unpublished_skill(db, skill=skill)
    except AgentSkillManagementError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
