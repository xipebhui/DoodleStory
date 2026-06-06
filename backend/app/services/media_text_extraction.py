import base64
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from app.core.config import get_settings
from app.services.llm import LLMConfigError, LLMProviderError, LLMResponseError
from app.services.prompt_logging import log_prompt_trace

logger = logging.getLogger(__name__)

MAX_CONTENT_EXTRACTION_IMAGES = 40

COMIC_CONTENT_EXTRACTION_PROMPT = """请把我接下来按顺序提供的一组漫画图片作为同一个连续作品理解，逐页完整提取漫画内容，并严格按以下要求输出：

1、旁白文字：原文旁白必须逐字照抄，一字不改、一字不漏。
2、对话文字：原文对话必须逐字照抄，保留标点和语气，一字不改。
3、人物内心OS/独白/心里话：完整逐字照抄，标注为【内心OS】。
4、画面描述：客观描述每页画面内容（人物动作、神态、环境、道具），不做删减。
5、分格信息：如果是分格漫画，明确标注【上格】【中格】【下格】及各格内容。
6、必须结合前后图片保持内容连贯，但输出必须按输入图片顺序逐页排列，不要跳页、合并页或改写成故事总结。

输出格式：
第X页：
【分格】单页 / 上中下三格等
画面：（客观描述画面内容）
旁白：（逐字照抄原文旁白，无则写"无"）
对话：（逐字照抄原文对话，无则写"无"）
内心OS：（逐字照抄，无则写"无"）"""

AUDIO_TRANSCRIPTION_PROMPT = """请转录这段音频中的原始口播、旁白或对白。
保持原始语气词、停顿和句子顺序，尽量不要改写。
不要总结，不要补充音频里没有的内容。
如果无法识别，请说明无法识别的原因。"""

@dataclass(frozen=True)
class MediaTextResult:
    text: str
    model: str


@dataclass(frozen=True)
class AudioExtractionResult:
    text: str
    model: str
    audio_bytes: bytes


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


def extract_ordered_gallery_comic_content(images: list[tuple[Path, str]]) -> MediaTextResult:
    if not images:
        raise LLMResponseError("没有可提取的图文图片")
    if len(images) > MAX_CONTENT_EXTRACTION_IMAGES:
        raise LLMResponseError(f"图文图片数量超过上限：{MAX_CONTENT_EXTRACTION_IMAGES}")
    settings = get_settings()
    model = settings.siliconflow_vision_model.strip()
    content: list[dict[str, object]] = [{"type": "text", "text": COMIC_CONTENT_EXTRACTION_PROMPT}]
    for index, (path, content_type) in enumerate(images, start=1):
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            raise LLMResponseError(f"媒体文件为空：{path}")
        content.append({"type": "text", "text": f"第 {index} 张图片："})
        content.append({"type": "image_url", "image_url": {"url": data_url(path, content_type), "detail": "high"}})
    logger.info(
        "content_extraction_ai_debug ordered_gallery_prompt model=%s image_count=%s prompt=%s image_paths=%s",
        model,
        len(images),
        COMIC_CONTENT_EXTRACTION_PROMPT,
        [str(path) for path, _content_type in images],
    )
    text = _chat_multimodal(
        model=model,
        prompt_name="content_extraction_ordered_comic_gallery",
        content=content,
    )
    logger.info(
        "content_extraction_ai_debug ordered_gallery_result model=%s image_count=%s text_chars=%s text=%s",
        model,
        len(images),
        len(text),
        text,
    )
    return MediaTextResult(text=text, model=model)


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
