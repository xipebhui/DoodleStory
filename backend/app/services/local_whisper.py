from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import get_settings


class LocalWhisperError(RuntimeError):
    pass


@lru_cache(maxsize=4)
def load_whisper_model(model_name: str, device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise LocalWhisperError("本地 Whisper 依赖未安装，无法转写参考音频") from exc

    kwargs = {}
    if compute_type and compute_type != "default":
        kwargs["compute_type"] = compute_type
    try:
        return WhisperModel(model_name, device=device, **kwargs)
    except Exception as exc:
        raise LocalWhisperError(f"本地 Whisper 模型加载失败：{exc}") from exc


@lru_cache(maxsize=1)
def load_traditional_to_simplified_converter():
    try:
        from opencc import OpenCC
    except ImportError as exc:
        raise LocalWhisperError("简体中文转换依赖未安装，无法规范化转写文本") from exc
    return OpenCC("t2s")


def normalize_transcription_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    try:
        return load_traditional_to_simplified_converter().convert(cleaned).strip()
    except Exception as exc:
        raise LocalWhisperError(f"转写文本转为简体中文失败：{exc}") from exc


def transcribe_audio_content(content: bytes, suffix: str) -> str:
    if not content:
        raise LocalWhisperError("音频内容为空，无法转写")
    settings = get_settings()
    model_name = settings.local_whisper_model.strip() or "tiny"
    device = settings.local_whisper_device.strip() or "auto"
    compute_type = settings.local_whisper_compute_type.strip() or "default"
    with TemporaryDirectory(prefix="doodlestory-audio-reference-") as temp_dir:
        audio_path = Path(temp_dir) / f"reference{suffix or '.audio'}"
        audio_path.write_bytes(content)
        model = load_whisper_model(model_name, device, compute_type)
        try:
            segments, _info = model.transcribe(str(audio_path), vad_filter=True)
            text = normalize_transcription_text("".join(segment.text for segment in segments))
        except Exception as exc:
            if isinstance(exc, LocalWhisperError):
                raise
            raise LocalWhisperError(f"本地 Whisper 转写失败：{exc}") from exc
    if not text:
        raise LocalWhisperError("本地 Whisper 未识别到参考文本")
    return text
