import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.enums import ImageCountMode, PanelType

PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"
logger = logging.getLogger(__name__)


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
    emphasis: str | None = None


class PanelPrompt(BaseModel):
    panel_order: int = Field(ge=1)
    visual_prompt: str = Field(min_length=1)
    image_text: ImageTextPlan = Field(default_factory=ImageTextPlan)
    text_layout: str = Field(min_length=1)


class PanelPromptResult(BaseModel):
    panels: list[PanelPrompt] = Field(min_length=1)


class StoryboardPanelPlan(PanelPrompt):
    panel_type: PanelType
    story_beat: str = Field(min_length=1)


class StoryboardPlanningResult(BaseModel):
    story_title: str = Field(min_length=1, max_length=120)
    story_hook: str = Field(min_length=1, max_length=200)
    story_outline: str = Field(min_length=1)
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
    text_layout: str = Field(min_length=1)
    appearance_keys: list[str] = Field(default_factory=list)
    usage_notes: dict[str, str] = Field(default_factory=dict)


class PanelPromptWithCharactersResult(BaseModel):
    panels: list[PanelPromptWithCharacters] = Field(min_length=1)


class RevisedPanelPrompt(BaseModel):
    visual_prompt: str = Field(min_length=1)
    image_text: ImageTextPlan = Field(default_factory=ImageTextPlan)
    text_layout: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)


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


def create_siliconflow_client():
    settings = get_settings()
    if not settings.siliconflow_api_key.strip():
        raise LLMConfigError("SILICONFLOW_API_KEY 未配置")
    if not settings.siliconflow_model.strip():
        raise LLMConfigError("SILICONFLOW_MODEL 未配置")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigError("缺少 openai 依赖，请安装 backend/requirements.txt") from exc

    return OpenAI(api_key=settings.siliconflow_api_key, base_url=settings.siliconflow_base_url)


def call_siliconflow_json(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    settings = get_settings()
    client = create_siliconflow_client()
    logger.info(
        "calling siliconflow model=%s temperature=%s system_prompt_chars=%s user_prompt_chars=%s",
        settings.siliconflow_model,
        settings.siliconflow_temperature,
        len(system_prompt),
        len(user_prompt),
    )
    response = client.chat.completions.create(
        model=settings.siliconflow_model,
        temperature=settings.siliconflow_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if not response.choices:
        raise LLMResponseError("LLM 没有返回 choices")
    content = response.choices[0].message.content
    if not content:
        raise LLMResponseError("LLM 返回内容为空")
    logger.info("siliconflow returned content_chars=%s", len(content))
    return parse_json_object(content)


def segment_story(
    *,
    original_text: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
) -> StorySegmentationResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = read_prompt("segment_story_v1.md")
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。请按语义自然切分。"
    )
    user_prompt = "\n".join(
        [
            count_instruction,
            "用户原始故事：",
            original_text,
        ]
    )
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = StorySegmentationResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 故事切分 JSON 结构不符合要求") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的分镜数量与用户指定图片数量不一致")
    logger.info(
        "story segmentation succeeded image_count_mode=%s requested_image_count=%s panel_count=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
    )
    return result


def adapt_story_for_douyin(*, original_text: str) -> AdaptedStoryResult:
    system_prompt = read_prompt("adapt_story_for_douyin_v1.md")
    user_prompt = json.dumps({"original_text": original_text}, ensure_ascii=False)
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = AdaptedStoryResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 故事增强 JSON 结构不符合要求") from exc
    logger.info(
        "story adaptation succeeded title_chars=%s hook_chars=%s story_chars=%s",
        len(result.title),
        len(result.hook),
        len(result.adapted_story),
    )
    return result


def plan_adapted_story_panels(
    *,
    title: str,
    hook: str,
    adapted_story: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
) -> StorySegmentationResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = read_prompt("plan_adapted_story_panels_v1.md")
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels，且第 1 个是封面。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。必须先输出 1 个封面，再按剧情自然规划分镜。"
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
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = StorySegmentationResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 增强故事分镜 JSON 结构不符合要求") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    if result.panels[0].panel_type != PanelType.cover:
        raise LLMResponseError("增强故事分镜的第一个 panel 必须是封面")
    if any(panel.panel_type == PanelType.cover for panel in result.panels[1:]):
        raise LLMResponseError("增强故事分镜只能第一个 panel 是封面")
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的分镜数量与用户指定图片数量不一致")
    logger.info(
        "adapted story panel planning succeeded image_count_mode=%s requested_image_count=%s panel_count=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
    )
    return result


def plan_storyboard_from_brief(
    *,
    brief_text: str,
    style_prompt: str,
    image_count_mode: ImageCountMode,
    requested_image_count: int | None,
) -> StoryboardPlanningResult:
    if image_count_mode == ImageCountMode.fixed and requested_image_count is None:
        raise LLMConfigError("固定图片数量模式必须提供 requested_image_count")

    system_prompt = system_prompt_with_style(read_prompt("plan_storyboard_from_brief_v1.md"), style_prompt)
    count_instruction = (
        f"固定图片数量：{requested_image_count}。必须刚好输出 {requested_image_count} 个 panels，且第 1 个是封面。"
        if image_count_mode == ImageCountMode.fixed
        else "图片数量：自动判断。请根据用户方案中的显式或隐式分镜逻辑自然规划 panels，默认第 1 个是封面。"
    )
    user_prompt = json.dumps(
        {
            "count_instruction": count_instruction,
            "brief_text": brief_text,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = StoryboardPlanningResult.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "brief storyboard validation failed errors=%s raw_keys=%s",
            exc.errors(),
            sorted(raw.keys()),
        )
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first_error.get("loc", []))
        message = first_error.get("msg", "未知结构错误")
        raise LLMResponseError(f"LLM 故事方案图文分镜 JSON 结构不符合要求：{location} {message}") from exc

    ensure_continuous_panel_orders([panel.panel_order for panel in result.panels])
    if result.panels[0].panel_type != PanelType.cover:
        raise LLMResponseError("故事方案图文分镜的第一个 panel 必须是封面")
    if any(panel.panel_type == PanelType.cover for panel in result.panels[1:]):
        raise LLMResponseError("故事方案图文分镜只能第一个 panel 是封面")
    if image_count_mode == ImageCountMode.fixed and len(result.panels) != requested_image_count:
        raise LLMResponseError("LLM 返回的分镜数量与用户指定图片数量不一致")
    logger.info(
        "brief storyboard planning succeeded image_count_mode=%s requested_image_count=%s panel_count=%s title=%s",
        image_count_mode.value,
        requested_image_count,
        len(result.panels),
        result.story_title,
    )
    return result


def generate_panel_prompts(
    *,
    original_text: str,
    style_prompt: str,
    panels: list[StorySegment],
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
            "original_text": original_text,
            "panels": input_panels,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = PanelPromptResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 分镜提示词 JSON 结构不符合要求") from exc

    returned_orders = [panel.panel_order for panel in result.panels]
    expected_orders = [panel.panel_order for panel in panels]
    if returned_orders != expected_orders:
        raise LLMResponseError("LLM 返回的提示词分镜顺序与输入 panels 不一致")
    logger.info("panel prompt generation succeeded panel_count=%s", len(result.panels))
    return result


def extract_task_characters(
    *,
    original_text: str,
    style_prompt: str,
    panels: list[StorySegment],
) -> TaskCharacterExtractionResult:
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
        for panel in panels
    ]
    user_prompt = json.dumps(
        {
            "original_text": original_text,
            "panels": input_panels,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = TaskCharacterExtractionResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 主要人物 JSON 结构不符合要求") from exc

    result = normalize_character_extraction_result(result)

    character_keys: set[str] = set()
    appearance_keys: set[str] = set()
    panel_orders = {panel.panel_order for panel in panels}
    for character in result.characters:
        if character.character_key in character_keys:
            raise LLMResponseError("LLM 返回了重复 character_key")
        character_keys.add(character.character_key)
        for appearance in character.appearances:
            if appearance.appearance_key in appearance_keys:
                raise LLMResponseError("LLM 返回了重复 appearance_key")
            if not appearance.appearance_key.startswith(character.character_key):
                raise LLMResponseError("appearance_key 必须以所属 character_key 开头")
            if any(panel_order not in panel_orders for panel_order in appearance.panel_orders):
                raise LLMResponseError("人物 appearance 的 panel_orders 包含不存在的 panel")
            appearance_keys.add(appearance.appearance_key)

    logger.info(
        "task character extraction succeeded character_count=%s appearance_count=%s",
        len(result.characters),
        len(appearance_keys),
    )
    return result


def generate_panel_prompts_with_characters(
    *,
    original_text: str,
    style_prompt: str,
    panels: list[StorySegment],
    characters: list[TaskCharacterPlan],
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
            "original_text": original_text,
            "panels": input_panels,
            "characters": character_payload,
        },
        ensure_ascii=False,
    )
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = PanelPromptWithCharactersResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 带人物分镜提示词 JSON 结构不符合要求") from exc

    returned_orders = [panel.panel_order for panel in result.panels]
    expected_orders = [panel.panel_order for panel in panels]
    if returned_orders != expected_orders:
        raise LLMResponseError("LLM 返回的提示词分镜顺序与输入 panels 不一致")
    for panel in result.panels:
        unknown_keys = [key for key in panel.appearance_keys if key not in valid_appearance_keys]
        if unknown_keys:
            raise LLMResponseError(f"LLM 返回了不存在的人物 appearance_key：{', '.join(unknown_keys)}")
        invalid_usage_keys = [key for key in panel.usage_notes if key not in panel.appearance_keys]
        if invalid_usage_keys:
            raise LLMResponseError("usage_notes 只能描述当前 panel 的 appearance_keys")

    logger.info("panel prompt with characters generation succeeded panel_count=%s", len(result.panels))
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
    raw = call_siliconflow_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        result = RevisedPanelPrompt.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError("LLM 单分镜提示词修改 JSON 结构不符合要求") from exc
    logger.info(
        "panel prompt revision succeeded prompt_chars=%s change_summary_chars=%s",
        len(result.visual_prompt),
        len(result.change_summary),
    )
    return result
