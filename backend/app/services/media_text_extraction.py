import base64
import json
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from app.core.config import get_settings
from app.services.llm import LLMConfigError, LLMProviderError, LLMResponseError
from app.services.prompt_logging import log_prompt_trace

import logging

logger = logging.getLogger(__name__)

MAX_CONTENT_EXTRACTION_IMAGES = 40
LOCAL_OCR_MODEL_NAME = "rapidocr-onnxruntime"

AUDIO_TRANSCRIPTION_PROMPT = """请转录这段音频中的原始口播、旁白或对白。
保持原始语气词、停顿和句子顺序，尽量不要改写。
不要总结，不要补充音频里没有的内容。
如果无法识别，请说明无法识别的原因。"""

STORY_SUMMARY_PROMPT = """请按图片顺序理解这一组抖音图文作品，输出故事总结。
只返回一个合法 JSON 对象，不要 Markdown，不要解释。
JSON 字段必须是：
- story_content: 概括故事内容，说明人物、处境、情绪变化和结局。
- story_highlight: 提炼故事爆点，说明最容易打动观众、引发转发或评论的点。
- target_audience: 判断目标观众，说明适合哪些人群以及他们会被什么吸引。
每个字段使用中文，内容要具体，不要写空话。"""


@dataclass(frozen=True)
class MediaTextResult:
    text: str
    model: str


@dataclass(frozen=True)
class AudioExtractionResult:
    text: str
    model: str
    audio_bytes: bytes


@dataclass(frozen=True)
class StorySummaryResult:
    story_content: str
    story_highlight: str
    target_audience: str
    model: str


def create_multimodal_client():
    settings = get_settings()
    if not settings.siliconflow_api_key.strip():
        raise LLMConfigError("SILICONFLOW_API_KEY 未配置")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigError("缺少 openai 依赖，请安装 backend/requirements.txt") from exc
    return OpenAI(api_key=settings.siliconflow_api_key, base_url=settings.siliconflow_base_url)


def data_url(path: Path, content_type: str) -> str:
    content = path.read_bytes()
    if not content:
        raise LLMResponseError(f"媒体文件为空：{path}")
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


@lru_cache
def local_ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise LLMConfigError("缺少 rapidocr-onnxruntime 依赖，请安装 backend/requirements.txt") from exc
    return RapidOCR()


def _ocr_text_lines(path: Path) -> list[str]:
    try:
        result, _elapsed = local_ocr_engine()(str(path))
    except Exception as exc:
        raise LLMProviderError(f"本地 OCR 识别失败：{exc}") from exc
    if result is None:
        return []
    if not isinstance(result, list):
        raise LLMResponseError("本地 OCR 返回内容格式不正确")

    lines: list[str] = []
    for item in result:
        if not isinstance(item, list) or len(item) < 2:
            raise LLMResponseError("本地 OCR 返回行格式不正确")
        text = item[1]
        if not isinstance(text, str):
            raise LLMResponseError("本地 OCR 返回文字格式不正确")
        value = text.strip()
        if value:
            lines.append(value)
    return lines


def _chat_multimodal(*, model: str, content: list[dict[str, object]], prompt_name: str) -> str:
    if not model.strip():
        raise LLMConfigError("SiliconFlow 多模态模型未配置")
    client = create_multimodal_client()
    trace_context = {"model": model, "prompt_name": prompt_name}
    started = monotonic()
    log_prompt_trace(
        logger,
        "content_extraction_multimodal_request",
        context=trace_context,
        provider="siliconflow",
        model=model,
        content_part_count=len(content),
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        log_prompt_trace(
            logger,
            "content_extraction_multimodal_exception",
            context=trace_context,
            elapsed_ms=round((monotonic() - started) * 1000),
            exception_type=exc.__class__.__name__,
            error=str(exc),
        )
        raise LLMProviderError(str(exc)) from exc

    if not response.choices:
        raise LLMResponseError("SiliconFlow 多模态模型没有返回 choices")
    message_content = response.choices[0].message.content
    if message_content is None:
        raise LLMResponseError("SiliconFlow 多模态模型返回内容为空")
    text = str(message_content).strip()
    log_prompt_trace(
        logger,
        "content_extraction_multimodal_response",
        context=trace_context,
        elapsed_ms=round((monotonic() - started) * 1000),
        response_id=getattr(response, "id", None),
        finish_reason=getattr(response.choices[0], "finish_reason", None),
        usage=getattr(response, "usage", None),
        content_chars=len(text),
        raw_content=text,
    )
    return text


def extract_image_text(path: Path, content_type: str) -> MediaTextResult:
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        raise LLMResponseError(f"媒体文件为空：{path}")
    lines = _ocr_text_lines(path)
    return MediaTextResult(text="\n".join(lines), model=LOCAL_OCR_MODEL_NAME)


def _json_object_from_text(text: str) -> dict[str, object]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1]).strip()
            if value.startswith("json"):
                value = value[4:].strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"故事总结不是合法 JSON：{text}") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("故事总结返回内容不是 JSON 对象")
    return parsed


def _required_text_field(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise LLMResponseError(f"故事总结缺少字段：{field_name}")
    return value.strip()


def summarize_images_story(images: list[tuple[Path, str]]) -> StorySummaryResult:
    if not images:
        raise LLMResponseError("没有可总结的图文图片")
    if len(images) > MAX_CONTENT_EXTRACTION_IMAGES:
        raise LLMResponseError(f"图文图片数量超过上限：{MAX_CONTENT_EXTRACTION_IMAGES}")
    settings = get_settings()
    model = settings.siliconflow_vision_model.strip()
    content: list[dict[str, object]] = [{"type": "text", "text": STORY_SUMMARY_PROMPT}]
    for index, (path, content_type) in enumerate(images, start=1):
        content.append({"type": "text", "text": f"第 {index} 张图片："})
        content.append({"type": "image_url", "image_url": {"url": data_url(path, content_type), "detail": "high"}})
    text = _chat_multimodal(
        model=model,
        prompt_name="content_extraction_story_summary",
        content=content,
    )
    payload = _json_object_from_text(text)
    return StorySummaryResult(
        story_content=_required_text_field(payload, "story_content"),
        story_highlight=_required_text_field(payload, "story_highlight"),
        target_audience=_required_text_field(payload, "target_audience"),
        model=model,
    )


def split_audio_to_mp3(video_path: Path) -> bytes:
    with TemporaryDirectory(prefix="doodlestory-content-audio-") as temp_dir:
        audio_path = Path(temp_dir) / "audio.mp3"
        try:
            process = subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "libmp3lame", str(audio_path)],
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise LLMConfigError("系统 ffmpeg 不可执行，无法从视频分离音频") from exc
        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "").strip()
            raise LLMResponseError(f"视频音频分离失败：{detail}")
        if not audio_path.exists() or audio_path.stat().st_size <= 0:
            raise LLMResponseError("视频音频分离后没有产生音频文件")
        return audio_path.read_bytes()


def transcribe_video_audio(video_path: Path) -> AudioExtractionResult:
    settings = get_settings()
    model = settings.siliconflow_audio_model.strip()
    audio_bytes = split_audio_to_mp3(video_path)
    with TemporaryDirectory(prefix="doodlestory-content-audio-read-") as temp_dir:
        audio_path = Path(temp_dir) / "audio.mp3"
        audio_path.write_bytes(audio_bytes)
        text = _chat_multimodal(
            model=model,
            prompt_name="content_extraction_audio_transcription",
            content=[
                {"type": "audio_url", "audio_url": {"url": data_url(audio_path, "audio/mpeg")}},
                {"type": "text", "text": AUDIO_TRANSCRIPTION_PROMPT},
            ],
        )
    return AudioExtractionResult(text=text, model=model, audio_bytes=audio_bytes)
