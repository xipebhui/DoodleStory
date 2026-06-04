import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from app.core.config import get_settings
from app.services.llm import LLMConfigError, LLMProviderError, LLMResponseError
from app.services.prompt_logging import log_prompt_trace

import logging

logger = logging.getLogger(__name__)

MAX_CONTENT_EXTRACTION_IMAGES = 40

IMAGE_TEXT_PROMPT = """请只提取这张图片中可见的中文或英文文字，保持原始顺序和原始措辞。
不要解释图片内容，不要总结，不要改写。
如果图片里没有可读文字，返回空字符串。"""

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
    settings = get_settings()
    model = settings.siliconflow_vision_model.strip()
    text = _chat_multimodal(
        model=model,
        prompt_name="content_extraction_image_text",
        content=[
            {"type": "image_url", "image_url": {"url": data_url(path, content_type), "detail": "high"}},
            {"type": "text", "text": IMAGE_TEXT_PROMPT},
        ],
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
