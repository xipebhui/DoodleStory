from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AgentSkillStatus


class StrictSkillModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentSkillCreate(StrictSkillModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=65536)
    tool_names: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("字段不能为空")
        return cleaned

    @field_validator("instructions")
    @classmethod
    def validate_instructions_bytes(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Skill 正文不能为空")
        if len(value.encode("utf-8")) > 64 * 1024:
            raise ValueError("Skill 正文不能超过 64 KiB")
        return value


class AgentSkillDraftUpdate(AgentSkillCreate):
    expected_draft_revision: int = Field(ge=1)


class AgentSkillPublish(StrictSkillModel):
    expected_draft_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)


class AgentSkillClone(StrictSkillModel):
    version_id: str | None = Field(default=None, min_length=1, max_length=32)


class AgentSkillToolRead(BaseModel):
    name: str
    display_name: str
    description: str
    has_side_effects: bool
    may_wait: bool


class AgentSkillVersionSummary(BaseModel):
    id: str
    version: int
    name: str
    description: str
    tool_names: list[str]
    content_hash: str
    published_at: datetime
    is_active: bool


class AgentSkillSummary(BaseModel):
    id: str
    scope: Literal["mine", "system"]
    name: str
    description: str
    status: AgentSkillStatus
    tool_names: list[str]
    draft_revision: int
    active_version: AgentSkillVersionSummary | None
    created_at: datetime
    updated_at: datetime


class AgentSkillDetail(AgentSkillSummary):
    instructions: str
    archived_at: datetime | None
    is_read_only: bool


class AgentSkillVersionDetail(AgentSkillVersionSummary):
    skill_id: str
    instructions: str


class AgentSkillListPage(BaseModel):
    items: list[AgentSkillSummary]
    page: int
    page_size: int
    total: int
    has_more: bool


class AgentSkillVersionListPage(BaseModel):
    items: list[AgentSkillVersionSummary]
    page: int
    page_size: int
    total: int
    has_more: bool


class AgentSkillAuthoringRequest(StrictSkillModel):
    goal: str = Field(min_length=1, max_length=4000)
    current_instructions: str | None = Field(default=None, max_length=65536)
    selected_tool_names: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("goal")
    @classmethod
    def strip_goal(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("创作目标不能为空")
        return cleaned


class AgentSkillAuthoringSuggestion(StrictSkillModel):
    suggested_name: str = Field(min_length=1, max_length=120)
    suggested_description: str = Field(min_length=1, max_length=500)
    suggested_instructions: str = Field(min_length=1, max_length=65536)
    suggested_tool_names: list[str] = Field(default_factory=list, max_length=32)
    notes: list[str] = Field(default_factory=list, max_length=8)
