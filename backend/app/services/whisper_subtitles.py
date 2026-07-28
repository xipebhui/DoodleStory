from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.local_whisper import (
    LocalWhisperError,
    load_whisper_model,
    normalize_transcription_text,
)


class WhisperSubtitleError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class GeneratedSubtitles:
    content: bytes
    text: str
    language: str
    model: str
    duration_ms: int
    cues: tuple[SubtitleCue, ...]


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def build_webvtt(cues: tuple[SubtitleCue, ...]) -> bytes:
    lines = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        lines.extend(
            [
                str(index),
                f"{_timestamp(cue.start_ms)} --> {_timestamp(cue.end_ms)}",
                cue.text,
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


def validate_subtitle_cues(
    cues: tuple[SubtitleCue, ...],
    *,
    duration_ms: int,
) -> None:
    if duration_ms <= 0:
        raise WhisperSubtitleError("音频时长无效，无法生成字幕")
    if not cues:
        raise WhisperSubtitleError("Whisper 未识别到字幕")
    previous_end = 0
    for index, cue in enumerate(cues, start=1):
        if not cue.text.strip():
            raise WhisperSubtitleError(f"第 {index} 条字幕文本为空")
        if cue.start_ms < previous_end or cue.end_ms <= cue.start_ms:
            raise WhisperSubtitleError(f"第 {index} 条字幕时间轴无效或不单调")
        if cue.end_ms > duration_ms:
            raise WhisperSubtitleError(f"第 {index} 条字幕超出音频总时长")
        previous_end = cue.end_ms


def generate_whisper_subtitles(
    *,
    audio_path: Path,
    duration_ms: int,
    settings: Settings | None = None,
) -> GeneratedSubtitles:
    resolved = settings or get_settings()
    model_name = resolved.local_whisper_model.strip() or "tiny"
    device = resolved.local_whisper_device.strip() or "auto"
    compute_type = resolved.local_whisper_compute_type.strip() or "default"
    model = load_whisper_model(model_name, device, compute_type)
    try:
        segments, info = model.transcribe(
            str(audio_path),
            vad_filter=True,
            language="zh",
        )
        cues = tuple(
            SubtitleCue(
                start_ms=round(float(segment.start) * 1000),
                end_ms=round(float(segment.end) * 1000),
                text=normalize_transcription_text(segment.text),
            )
            for segment in segments
        )
    except LocalWhisperError as exc:
        raise WhisperSubtitleError(str(exc)) from exc
    except Exception as exc:
        raise WhisperSubtitleError(f"Whisper 字幕识别失败：{exc}") from exc
    validate_subtitle_cues(cues, duration_ms=duration_ms)
    full_text = "".join(cue.text for cue in cues)
    return GeneratedSubtitles(
        content=build_webvtt(cues),
        text=full_text,
        language=str(getattr(info, "language", "zh") or "zh"),
        model=model_name,
        duration_ms=duration_ms,
        cues=cues,
    )
