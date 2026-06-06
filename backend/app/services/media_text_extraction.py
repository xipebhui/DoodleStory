import base64
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from app.core.config import get_settings
from app.services.llm import LLMConfigError, LLMProviderError, LLMResponseError, create_siliconflow_client
from app.services.prompt_logging import log_prompt_trace

import logging

logger = logging.getLogger(__name__)

MAX_CONTENT_EXTRACTION_IMAGES = 40

COMIC_CONTENT_EXTRACTION_PROMPT = """逐页完整提取漫画内容，严格按以下要求输出：

1、旁白文字：原文旁白必须逐字照抄，一字不改、一字不漏。
2、对话文字：原文对话必须逐字照抄，保留标点和语气，一字不改。
3、人物内心OS/独白/心里话：完整逐字照抄，标注为【内心OS】。
4、画面描述：客观描述每页画面内容（人物动作、神态、环境、道具），不做删减。
5、分格信息：如果是分格漫画，明确标注【上格】【中格】【下格】及各格内容。

输出格式：
第X页：
【分格】单页 / 上中下三格等
画面：（客观描述画面内容）
旁白：（逐字照抄原文旁白）
对话：（逐字照抄原文对话）
内心OS：（逐字照抄，无则写"无"）"""

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


def _data_url_summary(url: str) -> str:
    if not url.startswith("data:"):
        return url
    header, separator, encoded = url.partition(",")
    if not separator:
        return f"{header},[invalid_data_url]"
    return f"{header},[base64_chars={len(encoded)}]"


def _safe_multimodal_content_for_log(content: list[dict[str, object]]) -> list[dict[str, object]]:
    safe_parts: list[dict[str, object]] = []
    for index, part in enumerate(content, start=1):
        part_type = part.get("type")
        if part_type == "text":
            safe_parts.append(
                {
                    "index": index,
                    "type": "text",
                    "text": part.get("text"),
                }
            )
            continue
        if part_type == "image_url":
            image_url = part.get("image_url")
            if isinstance(image_url, dict):
                raw_url = image_url.get("url")
                safe_parts.append(
                    {
                        "index": index,
                        "type": "image_url",
                        "detail": image_url.get("detail"),
                        "url": _data_url_summary(str(raw_url)) if raw_url else None,
                    }
                )
            else:
                safe_parts.append({"index": index, "type": "image_url", "image_url": str(image_url)})
            continue
        if part_type == "audio_url":
            audio_url = part.get("audio_url")
            if isinstance(audio_url, dict):
                raw_url = audio_url.get("url")
                safe_parts.append(
                    {
                        "index": index,
                        "type": "audio_url",
                        "url": _data_url_summary(str(raw_url)) if raw_url else None,
                    }
                )
            else:
                safe_parts.append({"index": index, "type": "audio_url", "audio_url": str(audio_url)})
            continue
        safe_parts.append({"index": index, "type": str(part_type), "part": str(part)})
    return safe_parts


def data_url(path: Path, content_type: str) -> str:
    content = path.read_bytes()
    if not content:
        raise LLMResponseError(f"媒体文件为空：{path}")
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _chat_multimodal(*, model: str, content: list[dict[str, object]], prompt_name: str) -> str:
    if not model.strip():
        raise LLMConfigError("SiliconFlow 多模态模型未配置")
    client = create_multimodal_client()
    trace_context = {"model": model, "prompt_name": prompt_name}
    started = monotonic()
    logger.info(
        "content_extraction_ai_debug multimodal_request prompt_name=%s model=%s content=%s",
        prompt_name,
        model,
        json.dumps(_safe_multimodal_content_for_log(content), ensure_ascii=False, default=str),
    )
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
    logger.info(
        "content_extraction_ai_debug multimodal_response prompt_name=%s model=%s response_id=%s finish_reason=%s content_chars=%s content=%s",
        prompt_name,
        model,
        getattr(response, "id", None),
        getattr(response.choices[0], "finish_reason", None),
        len(text),
        text,
    )
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


def _chat_text_llm(*, system_prompt: str, user_prompt: str, prompt_name: str) -> str:
    settings = get_settings()
    model = settings.siliconflow_model.strip()
    if not model:
        raise LLMConfigError("SILICONFLOW_MODEL 未配置")
    client = create_siliconflow_client()
    trace_context = {"model": model, "prompt_name": prompt_name}
    started = monotonic()
    logger.info(
        "content_extraction_ai_debug llm_request prompt_name=%s model=%s temperature=%s system_prompt=%s user_prompt=%s",
        prompt_name,
        model,
        settings.siliconflow_temperature,
        system_prompt,
        user_prompt,
    )
    log_prompt_trace(
        logger,
        "content_extraction_llm_request",
        context=trace_context,
        provider="siliconflow",
        model=model,
        temperature=settings.siliconflow_temperature,
        system_prompt_chars=len(system_prompt),
        user_prompt_chars=len(user_prompt),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=settings.siliconflow_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        log_prompt_trace(
            logger,
            "content_extraction_llm_exception",
            context=trace_context,
            elapsed_ms=round((monotonic() - started) * 1000),
            exception_type=exc.__class__.__name__,
            error=str(exc),
        )
        raise LLMProviderError(str(exc)) from exc

    if not response.choices:
        raise LLMResponseError("SiliconFlow LLM 没有返回 choices")
    message_content = response.choices[0].message.content
    if message_content is None:
        raise LLMResponseError("SiliconFlow LLM 返回内容为空")
    text = str(message_content).strip()
    if not text:
        raise LLMResponseError("SiliconFlow LLM 返回内容为空")
    logger.info(
        "content_extraction_ai_debug llm_response prompt_name=%s model=%s response_id=%s finish_reason=%s content_chars=%s content=%s",
        prompt_name,
        model,
        getattr(response, "id", None),
        getattr(response.choices[0], "finish_reason", None),
        len(text),
        text,
    )
    log_prompt_trace(
        logger,
        "content_extraction_llm_response",
        context=trace_context,
        elapsed_ms=round((monotonic() - started) * 1000),
        response_id=getattr(response, "id", None),
        finish_reason=getattr(response.choices[0], "finish_reason", None),
        usage=getattr(response, "usage", None),
        content_chars=len(text),
        raw_content=text,
    )
    return text


def extract_image_text(path: Path, content_type: str, *, page_number: int) -> MediaTextResult:
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        raise LLMResponseError(f"媒体文件为空：{path}")
    settings = get_settings()
    model = settings.siliconflow_vision_model.strip()
    prompt = f"{COMIC_CONTENT_EXTRACTION_PROMPT}\n\n当前输入是第{page_number}页图片，请输出为“第{page_number}页：”。"
    logger.info(
        "content_extraction_ai_debug comic_page_prompt page_number=%s model=%s source_path=%s content_type=%s prompt=%s",
        page_number,
        model,
        path,
        content_type,
        prompt,
    )
    text = _chat_multimodal(
        model=model,
        prompt_name="content_extraction_comic_page_vision",
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url(path, content_type), "detail": "high"}},
        ],
    )
    logger.info(
        "content_extraction_ai_debug comic_page_extracted page_number=%s model=%s text_chars=%s text=%s",
        page_number,
        model,
        len(text),
        text,
    )
    return MediaTextResult(text=text, model=model)


def normalize_comic_extraction_text(raw_text: str) -> MediaTextResult:
    if not raw_text.strip():
        raise LLMResponseError("图片识别结果为空，无法继续调用 SiliconFlow LLM")
    user_prompt = (
        "以下是上一轮按图片顺序识别得到的漫画内容。请严格按系统提示词的格式重新整理为最终内容提取结果；"
        "不要新增图片中没有的信息，不要删除已识别出的旁白、对话、内心OS、画面描述或分格信息。\n\n"
        f"{raw_text.strip()}"
    )
    settings = get_settings()
    model = settings.siliconflow_model.strip()
    logger.info(
        "content_extraction_ai_debug comic_normalize_prompt model=%s raw_text_chars=%s system_prompt=%s user_prompt=%s",
        model,
        len(raw_text),
        COMIC_CONTENT_EXTRACTION_PROMPT,
        user_prompt,
    )
    text = _chat_text_llm(
        system_prompt=COMIC_CONTENT_EXTRACTION_PROMPT,
        user_prompt=user_prompt,
        prompt_name="content_extraction_comic_text_llm",
    )
    logger.info(
        "content_extraction_ai_debug comic_normalized_result model=%s text_chars=%s text=%s",
        model,
        len(text),
        text,
    )
    return MediaTextResult(text=text, model=model)


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
