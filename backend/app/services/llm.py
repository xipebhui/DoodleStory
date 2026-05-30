import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.enums import ImageCountMode

PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"


class LLMProviderError(Exception):
    pass


class LLMConfigError(LLMProviderError):
    pass


class LLMResponseError(LLMProviderError):
    pass


class StorySegment(BaseModel):
    panel_order: int = Field(ge=1)
    text: str = Field(min_length=1)


class StorySegmentationResult(BaseModel):
    panels: list[StorySegment] = Field(min_length=1)


class PanelPrompt(BaseModel):
    panel_order: int = Field(ge=1)
    prompt: str = Field(min_length=1)


class PanelPromptResult(BaseModel):
    panels: list[PanelPrompt] = Field(min_length=1)


def read_prompt(name: str) -> str:
    return (PROMPT_ROOT / name).read_text(encoding="utf-8")


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
    response = client.chat.completions.create(
        model=settings.siliconflow_model,
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
    return result


def generate_panel_prompts(
    *,
    original_text: str,
    style_prompt: str,
    panels: list[StorySegment],
) -> PanelPromptResult:
    system_prompt = read_prompt("generate_panel_prompt_v1.md")
    input_panels = [{"panel_order": panel.panel_order, "text": panel.text} for panel in panels]
    user_prompt = json.dumps(
        {
            "original_text": original_text,
            "style_prompt": style_prompt,
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
    return result
