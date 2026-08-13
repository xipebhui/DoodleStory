from __future__ import annotations

import json
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.models.entities import FileAsset, GeneratedImage
from app.services.media_text_extraction import (
    LLMConfigError,
    LLMProviderError,
    _chat_multimodal,
    data_url_from_bytes,
)
from app.services.storage import materialize_asset_to_local


class AgentVisionError(RuntimeError):
    pass


class InspectionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    suggested_change: str | None = Field(default=None, max_length=500)


class InspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(pattern=r"^(accept|revise|ask_user|blocked)$")
    scores: dict[str, float]
    issues: list[InspectionIssue] = Field(default_factory=list, max_length=20)


def _json_object(text: str) -> dict[str, object]:
    cleaned = text.strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AgentVisionError("VL 检查结果不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise AgentVisionError("VL 检查结果必须是 JSON object")
    return value


def inspect_generated_image(
    image: GeneratedImage,
    *,
    checks: list[str],
    expected: dict[str, object],
) -> tuple[InspectionResult, str, str, int]:
    if image.asset is None:
        raise AgentVisionError("图片版本缺少可检查资产")
    return inspect_image_asset(image.asset, checks=checks, expected=expected)


def inspect_image_asset(
    asset: FileAsset,
    *,
    checks: list[str],
    expected: dict[str, object],
) -> tuple[InspectionResult, str, str, int]:
    settings = get_settings()
    model = settings.siliconflow_vision_model.strip()
    if not model:
        raise AgentVisionError("SILICONFLOW_VISION_MODEL 未配置，无法执行图片检查")
    path = materialize_asset_to_local(asset)
    content = path.read_bytes()
    if not content:
        raise AgentVisionError("图片资产内容为空")
    prompt = (
        "你是漫画成图质量检查器。只根据当前图片和给定预期检查，不补写不可见事实。"
        "严格返回 JSON object，禁止 Markdown。verdict 只能是 accept、revise、ask_user、blocked。"
        "scores 必须为本次 checks 中每一项提供 0 到 1 的数字；issues 每项包含 code、message，"
        "可选 suggested_change。若图片无法读取或证据不足，使用 blocked 或 ask_user。\n"
        f"checks={json.dumps(checks, ensure_ascii=False)}\n"
        f"expected={json.dumps(expected, ensure_ascii=False, sort_keys=True)}"
    )
    started = monotonic()
    try:
        raw = _chat_multimodal(
            model=model,
            prompt_name="agent_inspect_image",
            max_retries=0,
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url_from_bytes(content, asset.content_type),
                        "detail": "high",
                    },
                },
            ],
        )
    except (LLMConfigError, LLMProviderError) as exc:
        raise AgentVisionError(str(exc)) from exc
    try:
        result = InspectionResult.model_validate(_json_object(raw))
    except ValidationError as exc:
        raise AgentVisionError("VL 检查结果不符合 inspect_image schema") from exc
    missing = set(checks).difference(result.scores)
    unknown = set(result.scores).difference(checks)
    if missing or unknown or any(score < 0 or score > 1 for score in result.scores.values()):
        raise AgentVisionError("VL 检查评分项与请求 checks 不一致")
    return result, "siliconflow", model, round((monotonic() - started) * 1000)
