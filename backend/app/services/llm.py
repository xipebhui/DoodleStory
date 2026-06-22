import json
import logging
import re
import time
from uuid import uuid4
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.enums import ImageCountMode, PanelType
from app.services.prompt_logging import log_prompt_trace

PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"
logger = logging.getLogger(__name__)
FINAL_IMAGE_PROMPT_MAX_ATTEMPTS = 3


class LLMProviderError(Exception):
    pass


class LLMConfigError(LLMProviderError):
    pass


class LLMResponseError(LLMProviderError):
    pass


class StorySegment(BaseModel):
    panel_order: int = Field(ge=1)
    panel_type: PanelType = PanelType.scene
    text: str = Field(min_length=1)
    narration_text: str | None = None
    dialogue_text: str | None = None
    visual_prompt: str | None = None
    image_text: dict[str, str | None] | None = None
    text_layout: str | None = None


class StorySegmentationResult(BaseModel):
    panels: list[StorySegment] = Field(min_length=1)


class AdaptedStoryResult(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    hook: str = Field(min_length=1, max_length=160)
    adapted_story: str = Field(min_length=1)


class ImageTextPlan(BaseModel):
    title: str | None = None
    narration: str | None = None
    dialogue: str | None = None
    inner_os: str | None = None
    emphasis: str | None = None


class PanelPrompt(BaseModel):
    panel_order: int = Field(ge=1)
    visual_prompt: str = Field(min_length=1)
    image_text: ImageTextPlan = Field(default_factory=ImageTextPlan)
    text_layout: str | None = None


class PanelPromptResult(BaseModel):
    panels: list[PanelPrompt] = Field(min_length=1)


class StoryboardPanelPlan(PanelPrompt):
    panel_type: PanelType
    story_beat: str = Field(min_length=1)


class StoryboardPlanningResult(BaseModel):
    story_title: str = Field(min_length=1, max_length=120)
    story_hook: str = Field(min_length=1, max_length=200)
    story_outline: str = Field(min_length=1)
    continuity_plan: dict[str, Any] | None = None
    panels: list[StoryboardPanelPlan] = Field(min_length=1)


class CharacterAppearancePlan(BaseModel):
    appearance_key: str = Field(min_length=1)
    age_stage: str | None = None
    visual_prompt: str = Field(min_length=1)
    panel_orders: list[int] = Field(default_factory=list)


class TaskCharacterPlan(BaseModel):
    character_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    appearances: list[CharacterAppearancePlan] = Field(min_length=1)


class TaskCharacterExtractionResult(BaseModel):
    characters: list[TaskCharacterPlan] = Field(default_factory=list)


class PanelPromptWithCharacters(BaseModel):
    panel_order: int = Field(ge=1)
    visual_prompt: str = Field(min_length=1)
    image_text: ImageTextPlan = Field(default_factory=ImageTextPlan)
    text_layout: str | None = None
    appearance_keys: list[str] = Field(default_factory=list)
    usage_notes: dict[str, str] = Field(default_factory=dict)


class PanelPromptWithCharactersResult(BaseModel):
    panels: list[PanelPromptWithCharacters] = Field(min_length=1)


class RevisedPanelPrompt(BaseModel):
    visual_prompt: str = Field(min_length=1)
    image_text: ImageTextPlan = Field(default_factory=ImageTextPlan)
    text_layout: str | None = None
    change_summary: str = Field(min_length=1)


class PolicyRewrittenImagePrompt(BaseModel):
    final_prompt: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)


class FinalImagePromptPanel(BaseModel):
    panel_order: int = Field(ge=1)
    final_prompt: str = Field(min_length=1)
    consistency_notes: list[str] = Field(default_factory=list)


class FinalImagePromptResult(BaseModel):
    panels: list[FinalImagePromptPanel] = Field(min_length=1)


class CharacterMergedStory(BaseModel):
    story_text: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)


class ExtractedCharacterNames(BaseModel):
    names: list[str] = Field(default_factory=list)


AGE_STAGE_SPECS = [
    (("童年", "儿童", "幼年", "小孩"), "child", "童年"),
    (("少年", "青少年"), "teen", "少年"),
    (("青年", "年轻"), "young_adult", "青年"),
    (("中年",), "middle_aged", "中年"),
    (("老年", "年老", "老人"), "elderly", "老年"),
    (("成年", "成人"), "adult", "成年"),
]
DEFAULT_AGE_STAGE_SLUG = "default"
DEFAULT_AGE_STAGE_LABEL = "默认"
STATE_VISUAL_TOKENS = (
    "愤怒",
    "生气",
    "焦虑",
    "紧张",
    "失败",
    "崩溃",
    "幻想",
    "画饼",
    "平静",
    "冷静",
    "石化",
    "无奈",
    "流汗",
    "质问",
    "指责",
    "问话",
    "回答",
    "离开",
    "满意",
    "夸张",
    "表情",
    "动作",
    "拍桌",
    "前倾",
    "手指",
    "竖起",
    "摸头",
    "摊开",
    "坐在",
    "站在",
    "躺在",
    "常伴有",
    "可能",
)
VISUAL_CLAUSE_SEPARATORS = ("。", "，", "；", ";", "\n")


def read_prompt(name: str) -> str:
    return (PROMPT_ROOT / name).read_text(encoding="utf-8")


def system_prompt_with_style(system_prompt: str, style_prompt: str) -> str:
    return (
        f"{system_prompt.strip()}\n\n"
        "当前风格规则如下。你必须把这些规则吸收到分镜、画面、人物、文字和排版设计中，"
        "但不要在输出里原样复述这些规则，也不要把它当作最终生图 prompt 的独立字段。\n"
        f"风格规则[\n{style_prompt.strip()}\n]"
    )


def parse_json_object(raw_content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("LLM 返回内容不是合法 JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("LLM 返回 JSON 必须是对象结构")
    return parsed


def ensure_continuous_panel_orders(panel_orders: list[int]) -> None:
    expected = list(range(1, len(panel_orders) + 1))
    if panel_orders != expected:
        raise LLMResponseError("LLM 返回的 panel_order 必须从 1 开始连续递增")


def normalize_character_age_stage(age_stage: str | None) -> tuple[str, str]:
    text = age_stage or ""
    for keywords, slug, label in AGE_STAGE_SPECS:
        if any(keyword in text for keyword in keywords):
            return slug, label
    return DEFAULT_AGE_STAGE_SLUG, DEFAULT_AGE_STAGE_LABEL


def split_visual_clauses(visual_prompt: str) -> list[str]:
    clauses = [visual_prompt.strip()]
    for separator in VISUAL_CLAUSE_SEPARATORS:
        next_clauses: list[str] = []
        for clause in clauses:
            next_clauses.extend(part.strip() for part in clause.split(separator))
        clauses = next_clauses
    return [clause for clause in clauses if clause]


def stable_character_visual_prompt(appearances: list[CharacterAppearancePlan]) -> str:
    candidates = sorted(
        appearances,
        key=lambda appearance: sum(token in appearance.visual_prompt for token in STATE_VISUAL_TOKENS),
    )
    for appearance in candidates:
        stable_clauses = [
            clause
            for clause in split_visual_clauses(appearance.visual_prompt)
            if not any(token in clause for token in STATE_VISUAL_TOKENS)
        ]
        stable_prompt = "，".join(stable_clauses).strip("，。；; ")
        if len(stable_prompt) >= 8:
            return stable_prompt
    return appearances[0].visual_prompt


def normalize_character_extraction_result(result: TaskCharacterExtractionResult) -> TaskCharacterExtractionResult:
    normalized_characters: list[TaskCharacterPlan] = []
    before_count = sum(len(character.appearances) for character in result.characters)

    for character in result.characters:
        grouped: dict[str, tuple[str, list[CharacterAppearancePlan]]] = {}
        group_order: list[str] = []
        for appearance in character.appearances:
            slug, label = normalize_character_age_stage(appearance.age_stage)
            if slug not in grouped:
                grouped[slug] = (label, [])
                group_order.append(slug)
            grouped[slug][1].append(appearance)

        normalized_appearances: list[CharacterAppearancePlan] = []
        for slug in group_order:
            label, appearances = grouped[slug]
            panel_orders = sorted(
                {
                    panel_order
                    for appearance in appearances
                    for panel_order in appearance.panel_orders
                }
            )
            normalized_appearances.append(
                CharacterAppearancePlan(
                    appearance_key=f"{character.character_key}_{slug}",
                    age_stage=label,
                    visual_prompt=stable_character_visual_prompt(appearances),
                    panel_orders=panel_orders,
                )
            )

        normalized_characters.append(
            TaskCharacterPlan(
                character_key=character.character_key,
                name=character.name,
                description=character.description,
                appearances=normalized_appearances,
            )
        )

    normalized_result = TaskCharacterExtractionResult(characters=normalized_characters)
    after_count = sum(len(character.appearances) for character in normalized_result.characters)
    if after_count != before_count:
        logger.info(
            "task character appearances normalized by age stage before_count=%s after_count=%s",
            before_count,
            after_count,
        )
    return normalized_result


def create_lio_client():
    settings = get_settings()
    if not settings.lio_api_key.strip():
        raise LLMConfigError("LIO_API_KEY 未配置")
    if not settings.lio_openai_base_url:
        raise LLMConfigError("LIO_BASE_URL 未配置")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigError("缺少 openai 依赖，请安装 backend/requirements.txt") from exc

    return OpenAI(api_key=settings.lio_api_key, base_url=settings.lio_openai_base_url)


def call_siliconflow_json(
    *,
    system_prompt: str,
    user_prompt: str,
    prompt_name: str,
    trace_context: dict[str, Any] | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    selected_model = (model if model is not None else settings.lio_model).strip()
    if not selected_model:
        raise LLMConfigError("LIO_MODEL 未配置")
    selected_temperature = settings.lio_temperature if temperature is None else temperature
    client = create_lio_client()
    trace_id = uuid4().hex
    context = trace_context or {}
    log_prompt_trace(
        logger,
        "llm_request_prepared",
        trace_id=trace_id,
        prompt_name=prompt_name,
        context=context,
        provider="lio",
        model=selected_model,
        temperature=selected_temperature,
        response_format="json_object",
        system_prompt_chars=len(system_prompt),
        user_prompt_chars=len(user_prompt),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    started = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=selected_model,
            temperature=selected_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        log_prompt_trace(
            logger,
            "llm_request_exception",
            trace_id=trace_id,
            prompt_name=prompt_name,
            context=context,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            exception_type=exc.__class__.__name__,
            error=str(exc),
        )
        raise
    if not response.choices:
        log_prompt_trace(
            logger,
            "llm_response_missing_choices",
            trace_id=trace_id,
            prompt_name=prompt_name,
            context=context,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            response_id=getattr(response, "id", None),
        )
        raise LLMResponseError("LLM 没有返回 choices")
    content = response.choices[0].message.content
    if not content:
        log_prompt_trace(
            logger,
            "llm_response_empty_content",
            trace_id=trace_id,
            prompt_name=prompt_name,
            context=context,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            response_id=getattr(response, "id", None),
            finish_reason=getattr(response.choices[0], "finish_reason", None),
        )
        raise LLMResponseError("LLM 返回内容为空")
    log_prompt_trace(
        logger,
        "llm_response_received",
        trace_id=trace_id,
        prompt_name=prompt_name,
        context=context,
        elapsed_ms=round((time.monotonic() - started) * 1000),
        response_id=getattr(response, "id", None),
        finish_reason=getattr(response.choices[0], "finish_reason", None),
        usage=getattr(response, "usage", None),
        content_chars=len(content),
        raw_content=content,
    )
    try:
        parsed = parse_json_object(content)
    except LLMResponseError:
        log_prompt_trace(
            logger,
            "llm_response_json_parse_failed",
            trace_id=trace_id,
            prompt_name=prompt_name,
            context=context,
            raw_content=content,
        )
        raise
    log_prompt_trace(
        logger,
        "llm_response_json_parsed",
        trace_id=trace_id,
        prompt_name=prompt_name,
        context=context,
        top_level_keys=sorted(parsed.keys()),
    )
    return parsed


def normalize_extracted_character_names(names: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in names:
        name = re.sub(r"\s+", "", value.strip(" ，。！？；：、,.!?;:()（）[]【】《》\"'“”‘’"))
        if not name or len(name) > 30:
            continue
        if any(name == existing or name in existing for existing in normalized):
            continue
        normalized = [existing for existing in normalized if existing not in name]
        normalized.append(name)
        if len(normalized) >= 12:
            break
    return normalized


def extract_character_names_from_story(
    *,
    text: str,
    trace_context: dict[str, Any] | None = None,
) -> ExtractedCharacterNames:
    settings = get_settings()
    model = settings.lio_character_extraction_model.strip()
    if not model:
        raise LLMConfigError("LIO_CHARACTER_EXTRACTION_MODEL 未配置")

    raw = call_siliconflow_json(
        system_prompt=read_prompt("extract_character_names_v1.md"),
        user_prompt=json.dumps({"story_text": text}, ensure_ascii=False),
        prompt_name="extract_character_names_v1.md",
        trace_context={**(trace_context or {}), "operation": "extract_character_names"},
        model=model,
        temperature=settings.character_extraction_temperature,
    )
    try:
        result = ExtractedCharacterNames.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="extract_character_names_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 角色名提取 JSON 结构不符合要求") from exc
    return ExtractedCharacterNames(names=normalize_extracted_character_names(result.names))


def segment_story(
    *,
    original_text: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
    trace_context: dict[str, Any] | None = None,
) -> StorySegmentationResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    result = split_original_story(
        original_text=original_text,
        image_count_mode=image_count_mode,
        requested_image_count=requested_image_count,
    )
    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("完整故事断句数量与用户指定图片数量不一致")
    ensure_original_text_coverage(original_text, result.panels)
    logger.info(
        "story segmentation succeeded image_count_mode=%s requested_image_count=%s panel_count=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
    )
    log_prompt_trace(
        logger,
        "original_story_segmentation_result",
        context=trace_context or {},
        image_count_mode=image_count_mode.value,
        requested_image_count=requested_image_count,
        original_text_chars=len(original_text),
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def split_original_story(
    *,
    original_text: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
) -> StorySegmentationResult:
    atoms = split_text_atoms(original_text)
    if image_count_mode == ImageCountMode.fixed:
        atoms = ensure_atom_count(atoms, requested_image_count or 0)
        segments = group_atoms_fixed(atoms, requested_image_count or 0)
    else:
        segments = group_atoms_auto(atoms)
    return StorySegmentationResult(
        panels=[
            StorySegment(panel_order=index + 1, panel_type=PanelType.scene, text=segment)
            for index, segment in enumerate(segments)
        ]
    )


def merge_character_into_story(
    *,
    story_text: str,
    character_name: str,
    character_description: str | None,
    trace_context: dict[str, Any] | None = None,
) -> CharacterMergedStory:
    user_prompt = json.dumps(
        {
            "story_text": story_text,
            "character": {
                "name": character_name,
                "description": character_description,
            },
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=read_prompt("merge_character_into_story_v1.md"),
        user_prompt=user_prompt,
        prompt_name="merge_character_into_story_v1.md",
        trace_context={**(trace_context or {}), "operation": "merge_character_into_story"},
    )
    try:
        result = CharacterMergedStory.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="merge_character_into_story_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 合并角色 JSON 结构不符合要求") from exc
    return result


def split_text_atoms(text: str) -> list[str]:
    if not text:
        raise LLMResponseError("完整故事不能为空")

    atoms: list[str] = []
    start = 0
    hard_breaks = set("。！？!?；;…\n")
    soft_breaks = set("，,、")
    for index, char in enumerate(text):
        if char in hard_breaks or char in soft_breaks:
            atoms.append(text[start : index + 1])
            start = index + 1
    if start < len(text):
        atoms.append(text[start:])
    return [atom for atom in atoms if atom]


def ensure_atom_count(atoms: list[str], requested_count: int) -> list[str]:
    if requested_count <= 0:
        raise LLMConfigError("固定图片数量必须大于 0")

    expanded = list(atoms)
    while len(expanded) < requested_count:
        split_index = max(range(len(expanded)), key=lambda index: len(expanded[index]))
        atom = expanded[split_index]
        if len(atom) <= 1:
            raise LLMResponseError("固定图片数量超过可切分的原文字数")
        midpoint = len(atom) // 2
        expanded[split_index : split_index + 1] = [atom[:midpoint], atom[midpoint:]]
    return expanded


def group_atoms_fixed(atoms: list[str], requested_count: int) -> list[str]:
    if len(atoms) == requested_count:
        return atoms

    total_length = sum(len(atom) for atom in atoms)
    target_length = max(1, total_length / requested_count)
    groups: list[str] = []
    current: list[str] = []
    current_length = 0
    remaining_groups = requested_count

    for index, atom in enumerate(atoms):
        remaining_atoms = len(atoms) - index
        must_close_after_atom = remaining_atoms == remaining_groups
        should_close_before_atom = (
            current
            and current_length >= target_length
            and remaining_atoms > remaining_groups
        )
        if should_close_before_atom:
            groups.append("".join(current))
            current = []
            current_length = 0
            remaining_groups -= 1

        current.append(atom)
        current_length += len(atom)
        if must_close_after_atom:
            groups.append("".join(current))
            current = []
            current_length = 0
            remaining_groups -= 1

    if current:
        groups.append("".join(current))
    if len(groups) != requested_count:
        raise LLMResponseError("完整故事固定数量断句失败")
    return groups


def group_atoms_auto(atoms: list[str]) -> list[str]:
    target_length = 34
    groups: list[str] = []
    current: list[str] = []
    current_length = 0
    for atom in atoms:
        if current and current_length + len(atom) > target_length:
            groups.append("".join(current))
            current = []
            current_length = 0
        current.append(atom)
        current_length += len(atom)
    if current:
        groups.append("".join(current))
    return groups


def ensure_original_text_coverage(original_text: str, panels: list[StorySegment]) -> None:
    joined = "".join(panel.text for panel in panels)
    if joined != original_text:
        raise LLMResponseError("完整故事断句结果未能逐字覆盖原文")


def normalize_storyboard_coverage_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def ensure_original_storyboard_text_coverage(original_text: str, result: StoryboardPlanningResult) -> None:
    joined = "".join(panel.story_beat for panel in result.panels)
    if normalize_storyboard_coverage_text(joined) != normalize_storyboard_coverage_text(original_text):
        raise LLMResponseError("完整故事 LLM 分镜结果未能覆盖原文内容，仅允许换行或空白差异")
    for panel in result.panels:
        if panel.image_text.narration != panel.story_beat:
            panel.image_text.narration = panel.story_beat
        panel.image_text.dialogue = None
        panel.panel_type = PanelType.scene


def plan_original_storyboard(
    *,
    original_text: str,
    style_prompt: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
    trace_context: dict[str, Any] | None = None,
) -> StoryboardPlanningResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = system_prompt_with_style(read_prompt("plan_original_storyboard_v1.md"), style_prompt)
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels，并优先按语义、场景和情绪节奏选择切分边界。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。请根据故事时间线、场景变化、对白归属和情绪节奏自然切分 panels，不要额外生成封面。"
    )
    user_prompt = json.dumps(
        {
            "count_instruction": count_instruction,
            "original_text": original_text,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="plan_original_storyboard_v1.md",
        trace_context={**(trace_context or {}), "operation": "plan_original_storyboard"},
    )
    try:
        result = StoryboardPlanningResult.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "original storyboard validation failed errors=%s raw_keys=%s",
            exc.errors(),
            sorted(raw.keys()),
        )
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="plan_original_storyboard_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first_error.get("loc", []))
        message = first_error.get("msg", "未知结构错误")
        raise LLMResponseError(f"LLM 完整故事分镜 JSON 结构不符合要求：{location} {message}") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的完整故事分镜数量与用户指定图片数量不一致")
    ensure_original_storyboard_text_coverage(original_text, result)
    logger.info(
        "original storyboard planning succeeded image_count_mode=%s requested_image_count=%s panel_count=%s title=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
        result.story_title,
    )
    log_prompt_trace(
        logger,
        "original_storyboard_planning_result",
        context=trace_context or {},
        image_count_mode=image_count_mode.value,
        requested_image_count=requested_image_count,
        story_title=result.story_title,
        story_hook=result.story_hook,
        story_outline=result.story_outline,
        continuity_plan=result.continuity_plan,
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def adapt_story_for_douyin(*, original_text: str, trace_context: dict[str, Any] | None = None) -> AdaptedStoryResult:
    system_prompt = read_prompt("adapt_story_for_douyin_v1.md")
    user_prompt = json.dumps({"original_text": original_text}, ensure_ascii=False)
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="adapt_story_for_douyin_v1.md",
        trace_context={**(trace_context or {}), "operation": "adapt_story_for_douyin"},
    )
    try:
        result = AdaptedStoryResult.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="adapt_story_for_douyin_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 故事增强 JSON 结构不符合要求") from exc
    logger.info(
        "story adaptation succeeded title_chars=%s hook_chars=%s story_chars=%s",
        len(result.title),
        len(result.hook),
        len(result.adapted_story),
    )
    log_prompt_trace(
        logger,
        "adapt_story_result",
        context=trace_context or {},
        result=result,
    )
    return result


def plan_adapted_story_panels(
    *,
    title: str,
    hook: str,
    adapted_story: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
    trace_context: dict[str, Any] | None = None,
) -> StorySegmentationResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = read_prompt("plan_adapted_story_panels_v1.md")
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels，所有 panel 都按普通分镜图处理。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。请根据故事节奏自然规划 panels，所有 panel 都按普通分镜图处理，不要额外生成封面。"
    )
    user_prompt = json.dumps(
        {
            "count_instruction": count_instruction,
            "title": title,
            "hook": hook,
            "adapted_story": adapted_story,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="plan_adapted_story_panels_v1.md",
        trace_context={**(trace_context or {}), "operation": "plan_adapted_story_panels"},
    )
    try:
        result = StorySegmentationResult.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="plan_adapted_story_panels_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 增强故事分镜 JSON 结构不符合要求") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    for panel in result.panels:
        panel.panel_type = PanelType.scene
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的分镜数量与用户指定图片数量不一致")
    logger.info(
        "adapted story panel planning succeeded image_count_mode=%s requested_image_count=%s panel_count=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
    )
    log_prompt_trace(
        logger,
        "adapted_story_panel_planning_result",
        context=trace_context or {},
        image_count_mode=image_count_mode.value,
        requested_image_count=requested_image_count,
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def plan_storyboard_from_brief(
    *,
    brief_text: str,
    style_prompt: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
    trace_context: dict[str, Any] | None = None,
) -> StoryboardPlanningResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = system_prompt_with_style(read_prompt("plan_storyboard_from_brief_v1.md"), style_prompt)
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels，所有 panel 都按普通分镜图处理。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。请根据用户方案中的显式或隐式分镜逻辑自然规划 panels，不要额外生成封面。"
    )
    user_prompt = json.dumps(
        {
            "count_instruction": count_instruction,
            "brief_text": brief_text,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="plan_storyboard_from_brief_v1.md",
        trace_context={**(trace_context or {}), "operation": "plan_storyboard_from_brief"},
    )
    try:
        result = StoryboardPlanningResult.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "brief storyboard validation failed errors=%s raw_keys=%s",
            exc.errors(),
            sorted(raw.keys()),
        )
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="plan_storyboard_from_brief_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first_error.get("loc", []))
        message = first_error.get("msg", "未知结构错误")
        raise LLMResponseError(f"LLM 故事方案图文分镜 JSON 结构不符合要求：{location} {message}") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    for panel in result.panels:
        panel.panel_type = PanelType.scene
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的分镜数量与用户指定图片数量不一致")
    logger.info(
        "brief storyboard planning succeeded image_count_mode=%s requested_image_count=%s panel_count=%s title=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
        result.story_title,
    )
    log_prompt_trace(
        logger,
        "storyboard_planning_result",
        context=trace_context or {},
        image_count_mode=image_count_mode.value,
        requested_image_count=requested_image_count,
        story_title=result.story_title,
        story_hook=result.story_hook,
        story_outline=result.story_outline,
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def parse_extracted_storyboard(
    *,
    extracted_text: str,
    style_prompt: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
    trace_context: dict[str, Any] | None = None,
) -> StoryboardPlanningResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = system_prompt_with_style(read_prompt("parse_extracted_storyboard_v1.md"), style_prompt)
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels；如果输入页数不匹配，必须明确失败，不要合并或补页。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。默认按输入中的第X页逐页输出 panels，不新增封面。"
    )
    user_prompt = json.dumps(
        {
            "count_instruction": count_instruction,
            "extracted_text": extracted_text,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="parse_extracted_storyboard_v1.md",
        trace_context={**(trace_context or {}), "operation": "parse_extracted_storyboard"},
    )
    try:
        result = StoryboardPlanningResult.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "extracted storyboard validation failed errors=%s raw_keys=%s",
            exc.errors(),
            sorted(raw.keys()),
        )
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="parse_extracted_storyboard_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first_error.get("loc", []))
        message = first_error.get("msg", "未知结构错误")
        raise LLMResponseError(f"LLM 内容提取分镜 JSON 结构不符合要求：{location} {message}") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    if any(panel.panel_type == PanelType.cover for panel in result.panels):
        raise LLMResponseError("内容提取分镜模式不应自动生成封面 panel")
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的分镜数量与用户指定图片数量不一致")
    logger.info(
        "extracted storyboard parsing succeeded image_count_mode=%s requested_image_count=%s panel_count=%s title=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
        result.story_title,
    )
    log_prompt_trace(
        logger,
        "extracted_storyboard_parse_result",
        context=trace_context or {},
        image_count_mode=image_count_mode.value,
        requested_image_count=requested_image_count,
        story_title=result.story_title,
        story_hook=result.story_hook,
        story_outline=result.story_outline,
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def generate_panel_prompts(
    *,
    style_prompt: str,
    panels: list[StorySegment],
    batch_context: dict[str, Any] | None = None,
    trace_context: dict[str, Any] | None = None,
) -> PanelPromptResult:
    system_prompt = system_prompt_with_style(read_prompt("generate_panel_prompt_v1.md"), style_prompt)
    input_panels = [
        {
            "panel_order": panel.panel_order,
            "panel_type": panel.panel_type.value,
            "text": panel.text,
            "narration_text": panel.narration_text,
            "dialogue_text": panel.dialogue_text,
            "visual_prompt": panel.visual_prompt,
            "image_text": panel.image_text,
            "text_layout": panel.text_layout,
        }
        for panel in panels
    ]
    user_prompt = json.dumps(
        {
            "panels": input_panels,
            "batch_context": batch_context or {},
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="generate_panel_prompt_v1.md",
        trace_context={**(trace_context or {}), "operation": "generate_panel_prompts"},
    )
    try:
        result = PanelPromptResult.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="generate_panel_prompt_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 分镜提示词 JSON 结构不符合要求") from exc

    returned_orders = [panel.panel_order for panel in result.panels]
    expected_orders = [panel.panel_order for panel in panels]
    if returned_orders != expected_orders:
        log_prompt_trace(
            logger,
            "llm_panel_order_mismatch",
            prompt_name="generate_panel_prompt_v1.md",
            context=trace_context or {},
            expected_orders=expected_orders,
            returned_orders=returned_orders,
            raw=raw,
        )
        raise LLMResponseError("LLM 返回的提示词分镜顺序与输入 panels 不一致")
    logger.info("panel prompt generation succeeded panel_count=%s", len(result.panels))
    log_prompt_trace(
        logger,
        "panel_prompt_generation_result",
        context=trace_context or {},
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def extract_task_characters(
    *,
    original_text: str,
    style_prompt: str,
    panels: list[StorySegment] | None = None,
    trace_context: dict[str, Any] | None = None,
) -> TaskCharacterExtractionResult:
    settings = get_settings()
    model = settings.lio_character_extraction_model.strip()
    if not model:
        raise LLMConfigError("LIO_CHARACTER_EXTRACTION_MODEL 未配置")

    system_prompt = system_prompt_with_style(read_prompt("extract_task_characters_v1.md"), style_prompt)
    input_panels = [
        {
            "panel_order": panel.panel_order,
            "panel_type": panel.panel_type.value,
            "text": panel.text,
            "narration_text": panel.narration_text,
            "dialogue_text": panel.dialogue_text,
            "visual_prompt": panel.visual_prompt,
            "image_text": panel.image_text,
            "text_layout": panel.text_layout,
        }
        for panel in (panels or [])
    ]
    user_prompt = json.dumps(
        {
            "original_text": original_text,
            "panels": input_panels,
            "panels_available": bool(panels),
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="extract_task_characters_v1.md",
        trace_context={**(trace_context or {}), "operation": "extract_task_characters"},
        model=model,
        temperature=settings.character_extraction_temperature,
    )
    try:
        result = TaskCharacterExtractionResult.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="extract_task_characters_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 主要人物 JSON 结构不符合要求") from exc

    result = normalize_character_extraction_result(result)

    character_keys: set[str] = set()
    appearance_keys: set[str] = set()
    panel_orders = {panel.panel_order for panel in (panels or [])}
    for character in result.characters:
        if character.character_key in character_keys:
            log_prompt_trace(
                logger,
                "character_extraction_validation_failed",
                prompt_name="extract_task_characters_v1.md",
                context=trace_context or {},
                reason="duplicate_character_key",
                character_key=character.character_key,
                result=result,
            )
            raise LLMResponseError("LLM 返回了重复 character_key")
        character_keys.add(character.character_key)
        for appearance in character.appearances:
            if appearance.appearance_key in appearance_keys:
                log_prompt_trace(
                    logger,
                    "character_extraction_validation_failed",
                    prompt_name="extract_task_characters_v1.md",
                    context=trace_context or {},
                    reason="duplicate_appearance_key",
                    appearance_key=appearance.appearance_key,
                    result=result,
                )
                raise LLMResponseError("LLM 返回了重复 appearance_key")
            if not appearance.appearance_key.startswith(character.character_key):
                log_prompt_trace(
                    logger,
                    "character_extraction_validation_failed",
                    prompt_name="extract_task_characters_v1.md",
                    context=trace_context or {},
                    reason="appearance_key_prefix_mismatch",
                    character_key=character.character_key,
                    appearance_key=appearance.appearance_key,
                    result=result,
                )
                raise LLMResponseError("appearance_key 必须以所属 character_key 开头")
            if panels is not None and any(panel_order not in panel_orders for panel_order in appearance.panel_orders):
                log_prompt_trace(
                    logger,
                    "character_extraction_validation_failed",
                    prompt_name="extract_task_characters_v1.md",
                    context=trace_context or {},
                    reason="appearance_panel_order_unknown",
                    panel_orders=appearance.panel_orders,
                    valid_panel_orders=sorted(panel_orders),
                    result=result,
                )
                raise LLMResponseError("人物 appearance 的 panel_orders 包含不存在的 panel")
            appearance_keys.add(appearance.appearance_key)

    logger.info(
        "task character extraction succeeded character_count=%s appearance_count=%s",
        len(result.characters),
        len(appearance_keys),
    )
    log_prompt_trace(
        logger,
        "character_extraction_result",
        context=trace_context or {},
        character_count=len(result.characters),
        appearance_count=len(appearance_keys),
        characters=result.characters,
    )
    return result


def generate_panel_prompts_with_characters(
    *,
    style_prompt: str,
    panels: list[StorySegment],
    characters: list[TaskCharacterPlan],
    batch_context: dict[str, Any] | None = None,
    trace_context: dict[str, Any] | None = None,
) -> PanelPromptWithCharactersResult:
    system_prompt = system_prompt_with_style(read_prompt("generate_panel_prompt_with_characters_v1.md"), style_prompt)
    input_panels = [
        {
            "panel_order": panel.panel_order,
            "panel_type": panel.panel_type.value,
            "text": panel.text,
            "narration_text": panel.narration_text,
            "dialogue_text": panel.dialogue_text,
            "visual_prompt": panel.visual_prompt,
            "image_text": panel.image_text,
            "text_layout": panel.text_layout,
        }
        for panel in panels
    ]
    character_payload = [character.model_dump() for character in characters]
    valid_appearance_keys = {
        appearance.appearance_key
        for character in characters
        for appearance in character.appearances
    }
    user_prompt = json.dumps(
        {
            "panels": input_panels,
            "characters": character_payload,
            "batch_context": batch_context or {},
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="generate_panel_prompt_with_characters_v1.md",
        trace_context={**(trace_context or {}), "operation": "generate_panel_prompts_with_characters"},
    )
    try:
        result = PanelPromptWithCharactersResult.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="generate_panel_prompt_with_characters_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 带人物分镜提示词 JSON 结构不符合要求") from exc

    returned_orders = [panel.panel_order for panel in result.panels]
    expected_orders = [panel.panel_order for panel in panels]
    if returned_orders != expected_orders:
        log_prompt_trace(
            logger,
            "llm_panel_order_mismatch",
            prompt_name="generate_panel_prompt_with_characters_v1.md",
            context=trace_context or {},
            expected_orders=expected_orders,
            returned_orders=returned_orders,
            raw=raw,
        )
        raise LLMResponseError("LLM 返回的提示词分镜顺序与输入 panels 不一致")
    for panel in result.panels:
        unknown_keys = [key for key in panel.appearance_keys if key not in valid_appearance_keys]
        if unknown_keys:
            log_prompt_trace(
                logger,
                "panel_prompt_character_validation_failed",
                prompt_name="generate_panel_prompt_with_characters_v1.md",
                context=trace_context or {},
                reason="unknown_appearance_keys",
                panel_order=panel.panel_order,
                unknown_keys=unknown_keys,
                valid_appearance_keys=sorted(valid_appearance_keys),
                raw=raw,
            )
            raise LLMResponseError(f"LLM 返回了不存在的人物 appearance_key：{', '.join(unknown_keys)}")
        invalid_usage_keys = [key for key in panel.usage_notes if key not in panel.appearance_keys]
        if invalid_usage_keys:
            log_prompt_trace(
                logger,
                "panel_prompt_character_validation_failed",
                prompt_name="generate_panel_prompt_with_characters_v1.md",
                context=trace_context or {},
                reason="invalid_usage_keys",
                panel_order=panel.panel_order,
                invalid_usage_keys=invalid_usage_keys,
                raw=raw,
            )
            raise LLMResponseError("usage_notes 只能描述当前 panel 的 appearance_keys")

    logger.info("panel prompt with characters generation succeeded panel_count=%s", len(result.panels))
    log_prompt_trace(
        logger,
        "panel_prompt_with_characters_result",
        context=trace_context or {},
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def revise_panel_prompt(
    *,
    original_text: str,
    style_prompt: str,
    panel_text: str,
    current_prompt: str,
    current_image_text: dict[str, str | None] | None,
    current_text_layout: str | None,
    user_instruction: str,
    trace_context: dict[str, Any] | None = None,
) -> RevisedPanelPrompt:
    system_prompt = system_prompt_with_style(read_prompt("revise_panel_prompt_v1.md"), style_prompt)
    user_prompt = json.dumps(
        {
            "original_text": original_text,
            "panel_text": panel_text,
            "current_prompt": current_prompt,
            "current_image_text": current_image_text,
            "current_text_layout": current_text_layout,
            "user_instruction": user_instruction,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_name="revise_panel_prompt_v1.md",
        trace_context={**(trace_context or {}), "operation": "revise_panel_prompt"},
    )
    try:
        result = RevisedPanelPrompt.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="revise_panel_prompt_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM 单分镜提示词修改 JSON 结构不符合要求") from exc
    logger.info(
        "panel prompt revision succeeded prompt_chars=%s change_summary_chars=%s",
        len(result.visual_prompt),
        len(result.change_summary),
    )
    log_prompt_trace(
        logger,
        "panel_prompt_revision_result",
        context=trace_context or {},
        result=result,
    )
    return result


def compose_final_image_prompts(
    *,
    task_payload: dict[str, Any],
    panels: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    trace_context: dict[str, Any] | None = None,
) -> FinalImagePromptResult:
    expected_orders = [int(panel["panel_order"]) for panel in panels]
    payload = {
        "task": task_payload,
        "characters": characters,
        "panels": panels,
    }
    raw: dict[str, Any] | None = None
    result: FinalImagePromptResult | None = None
    returned_orders: list[int] = []
    for attempt in range(1, FINAL_IMAGE_PROMPT_MAX_ATTEMPTS + 1):
        if attempt == 1:
            attempt_payload = payload
        else:
            attempt_payload = {
                **payload,
                "retry_instruction": (
                    "上一次返回的 panels 顺序与输入不一致。必须严格按输入 panels 的顺序返回，"
                    f"panel_order 必须依次为 {expected_orders}，不能缺失、重复、重排或新增 panel。"
                ),
            }
        raw = call_siliconflow_json(
            system_prompt=read_prompt("compose_final_image_prompts_v1.md"),
            user_prompt=json.dumps(attempt_payload, ensure_ascii=False),
            prompt_name="compose_final_image_prompts_v1.md",
            trace_context={
                **(trace_context or {}),
                "operation": "compose_final_image_prompts",
                "attempt": attempt,
                "max_attempts": FINAL_IMAGE_PROMPT_MAX_ATTEMPTS,
            },
            temperature=0.2,
        )
        try:
            result = FinalImagePromptResult.model_validate(raw)
        except ValidationError as exc:
            log_prompt_trace(
                logger,
                "llm_validation_failed",
                prompt_name="compose_final_image_prompts_v1.md",
                context={
                    **(trace_context or {}),
                    "attempt": attempt,
                    "max_attempts": FINAL_IMAGE_PROMPT_MAX_ATTEMPTS,
                },
                errors=exc.errors(),
                raw=raw,
            )
            raise LLMResponseError("LLM 最终生图提示词 JSON 结构不符合要求") from exc
        returned_orders = [panel.panel_order for panel in result.panels]
        if returned_orders == expected_orders:
            if attempt > 1:
                logger.info("final image prompt composition recovered after retry attempt=%s", attempt)
            break
        log_prompt_trace(
            logger,
            "llm_panel_order_mismatch_retrying",
            prompt_name="compose_final_image_prompts_v1.md",
            context={
                **(trace_context or {}),
                "attempt": attempt,
                "max_attempts": FINAL_IMAGE_PROMPT_MAX_ATTEMPTS,
            },
            expected_orders=expected_orders,
            returned_orders=returned_orders,
            raw=raw,
        )
    if result is None or returned_orders != expected_orders:
        log_prompt_trace(
            logger,
            "llm_panel_order_mismatch",
            prompt_name="compose_final_image_prompts_v1.md",
            context={**(trace_context or {}), "attempts": FINAL_IMAGE_PROMPT_MAX_ATTEMPTS},
            expected_orders=expected_orders,
            returned_orders=returned_orders,
            raw=raw,
        )
        raise LLMResponseError("LLM 返回的最终生图提示词顺序与输入 panels 不一致")

    logger.info("final image prompt composition succeeded panel_count=%s", len(result.panels))
    log_prompt_trace(
        logger,
        "final_image_prompt_llm_result",
        context=trace_context or {},
        panel_count=len(result.panels),
        panels=[panel.model_dump() for panel in result.panels],
    )
    return result


def rewrite_policy_blocked_image_prompt(
    *,
    final_prompt: str,
    provider_error: str,
    trace_context: dict[str, Any] | None = None,
) -> PolicyRewrittenImagePrompt:
    user_prompt = json.dumps(
        {
            "final_prompt": final_prompt,
            "provider_error": provider_error,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(
        system_prompt=read_prompt("rewrite_policy_blocked_image_prompt_v1.md"),
        user_prompt=user_prompt,
        prompt_name="rewrite_policy_blocked_image_prompt_v1.md",
        trace_context={**(trace_context or {}), "operation": "rewrite_policy_blocked_image_prompt"},
    )
    try:
        result = PolicyRewrittenImagePrompt.model_validate(raw)
    except ValidationError as exc:
        log_prompt_trace(
            logger,
            "llm_validation_failed",
            prompt_name="rewrite_policy_blocked_image_prompt_v1.md",
            context=trace_context or {},
            errors=exc.errors(),
            raw=raw,
        )
        raise LLMResponseError("LLM Policy 拦截提示词改写 JSON 结构不符合要求") from exc
    logger.info(
        "policy blocked image prompt rewritten prompt_chars=%s change_summary_chars=%s",
        len(result.final_prompt),
        len(result.change_summary),
    )
    log_prompt_trace(
        logger,
        "policy_blocked_image_prompt_rewrite_result",
        context=trace_context or {},
        rewritten_prompt_chars=len(result.final_prompt),
        change_summary=result.change_summary,
        final_prompt=result.final_prompt,
    )
    return result
