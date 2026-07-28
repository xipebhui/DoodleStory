from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import unicodedata

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


@dataclass(frozen=True)
class _TimedCharacter:
    text: str
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class _ReferenceChunk:
    text: str
    start_character: int
    end_character: int


_MIN_ALIGNMENT_RATIO = 0.5
_MAX_CUE_CHARACTERS = 18
_STRONG_CUE_BREAKS = frozenset("。！？!?；;\n")
_SOFT_CUE_BREAKS = frozenset("，,、：:")


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


def _alignment_characters(text: str) -> tuple[str, ...]:
    normalized = normalize_transcription_text(
        unicodedata.normalize("NFKC", text)
    )
    return tuple(
        character.casefold()
        for character in normalized
        if character.isalnum()
    )


def _timed_characters(
    segments: tuple[object, ...],
    *,
    duration_ms: int,
) -> tuple[_TimedCharacter, ...]:
    characters: list[_TimedCharacter] = []
    for segment in segments:
        words = tuple(getattr(segment, "words", None) or ())
        if not words:
            raise WhisperSubtitleError("Whisper 未返回原文校准所需的词级时间戳")
        for span in words:
            span_characters = _alignment_characters(
                str(getattr(span, "word", None) or getattr(span, "text", ""))
            )
            if not span_characters:
                continue
            start_ms = float(getattr(span, "start")) * 1000
            end_ms = float(getattr(span, "end")) * 1000
            if (
                start_ms < 0
                or end_ms <= start_ms
                or end_ms > duration_ms
            ):
                raise WhisperSubtitleError("Whisper 返回了无效的词级时间戳")
            character_duration = (end_ms - start_ms) / len(span_characters)
            for index, character in enumerate(span_characters):
                characters.append(
                    _TimedCharacter(
                        text=character,
                        start_ms=start_ms + character_duration * index,
                        end_ms=start_ms + character_duration * (index + 1),
                    )
                )
    return tuple(characters)


def _aligned_character_boundaries(
    reference_text: str,
    recognized: tuple[_TimedCharacter, ...],
) -> tuple[float, ...]:
    reference = _alignment_characters(reference_text)
    if not reference:
        raise WhisperSubtitleError("语音生成原文没有可用于字幕对齐的文字")
    if not recognized:
        raise WhisperSubtitleError("Whisper 未识别到可用于原文校准的时间锚点")

    matcher = SequenceMatcher(
        None,
        reference,
        tuple(character.text for character in recognized),
        autojunk=False,
    )
    blocks = tuple(block for block in matcher.get_matching_blocks() if block.size)
    matched_characters = sum(block.size for block in blocks)
    alignment_ratio = (
        2 * matched_characters / (len(reference) + len(recognized))
    )
    if alignment_ratio < _MIN_ALIGNMENT_RATIO:
        raise WhisperSubtitleError(
            "Whisper 识别结果与语音生成原文差异过大，"
            f"无法可靠校准字幕时间轴（匹配率 {alignment_ratio:.0%}）"
        )

    centers: list[float | None] = [None] * len(reference)
    for block in blocks:
        for offset in range(block.size):
            recognized_character = recognized[block.b + offset]
            centers[block.a + offset] = (
                recognized_character.start_ms + recognized_character.end_ms
            ) / 2

    first_anchor = next(
        index for index, center in enumerate(centers) if center is not None
    )
    first_center = float(centers[first_anchor])
    timeline_start = recognized[0].start_ms
    for index in range(first_anchor):
        centers[index] = timeline_start + (
            (first_center - timeline_start)
            * (index + 1)
            / (first_anchor + 1)
        )

    previous_anchor = first_anchor
    for next_anchor in range(first_anchor + 1, len(centers)):
        next_center = centers[next_anchor]
        if next_center is None:
            continue
        previous_center = float(centers[previous_anchor])
        gap = next_anchor - previous_anchor
        for index in range(previous_anchor + 1, next_anchor):
            centers[index] = previous_center + (
                (float(next_center) - previous_center)
                * (index - previous_anchor)
                / gap
            )
        previous_anchor = next_anchor

    last_center = float(centers[previous_anchor])
    timeline_end = recognized[-1].end_ms
    suffix_length = len(centers) - previous_anchor
    for index in range(previous_anchor + 1, len(centers)):
        centers[index] = last_center + (
            (timeline_end - last_center)
            * (index - previous_anchor)
            / suffix_length
        )

    resolved_centers: list[float] = []
    for center in centers:
        resolved = float(center)
        if resolved_centers:
            resolved = max(resolved, resolved_centers[-1])
        resolved_centers.append(resolved)

    boundaries = [timeline_start]
    boundaries.extend(
        (left + right) / 2
        for left, right in zip(resolved_centers, resolved_centers[1:])
    )
    boundaries.append(timeline_end)
    return tuple(boundaries)


def _reference_chunks(reference_text: str) -> tuple[_ReferenceChunk, ...]:
    source = reference_text.strip()
    if not source:
        raise WhisperSubtitleError("语音生成原文为空，无法生成字幕")

    chunks: list[_ReferenceChunk] = []
    chunk_start_offset = 0
    chunk_start_character = 0
    current_character = 0

    for offset, character in enumerate(source):
        current_character += len(_alignment_characters(character))
        chunk_character_count = current_character - chunk_start_character
        should_break = (
            character in _STRONG_CUE_BREAKS
            or (
                character in _SOFT_CUE_BREAKS
                and chunk_character_count >= 8
            )
            or chunk_character_count >= _MAX_CUE_CHARACTERS
        )
        if not should_break:
            continue
        chunk_text = source[chunk_start_offset : offset + 1].strip()
        if chunk_text and current_character > chunk_start_character:
            chunks.append(
                _ReferenceChunk(
                    text=chunk_text,
                    start_character=chunk_start_character,
                    end_character=current_character,
                )
            )
        elif chunk_text and chunks:
            previous = chunks[-1]
            chunks[-1] = _ReferenceChunk(
                text=f"{previous.text}{chunk_text}",
                start_character=previous.start_character,
                end_character=previous.end_character,
            )
        chunk_start_offset = offset + 1
        chunk_start_character = current_character

    remaining = source[chunk_start_offset:].strip()
    if remaining and current_character > chunk_start_character:
        chunks.append(
            _ReferenceChunk(
                text=remaining,
                start_character=chunk_start_character,
                end_character=current_character,
            )
        )
    elif remaining and chunks:
        previous = chunks[-1]
        chunks[-1] = _ReferenceChunk(
            text=f"{previous.text}{remaining}",
            start_character=previous.start_character,
            end_character=previous.end_character,
        )
    if not chunks:
        raise WhisperSubtitleError("语音生成原文没有可显示的字幕内容")
    return tuple(chunks)


def align_reference_subtitles(
    *,
    reference_text: str,
    segments: tuple[object, ...],
    duration_ms: int,
) -> tuple[SubtitleCue, ...]:
    recognized = _timed_characters(segments, duration_ms=duration_ms)
    boundaries = _aligned_character_boundaries(reference_text, recognized)
    chunks = _reference_chunks(reference_text)
    cues: list[SubtitleCue] = []
    previous_end = 0
    for chunk in chunks:
        start_ms = max(
            previous_end,
            round(boundaries[chunk.start_character]),
        )
        end_ms = round(boundaries[chunk.end_character])
        if end_ms <= start_ms:
            end_ms = start_ms + 1
        if end_ms > duration_ms:
            raise WhisperSubtitleError("原文校准后的字幕超出音频总时长")
        cues.append(
            SubtitleCue(
                start_ms=start_ms,
                end_ms=end_ms,
                text=chunk.text,
            )
        )
        previous_end = end_ms
    return tuple(cues)


def generate_whisper_subtitles(
    *,
    audio_path: Path,
    duration_ms: int,
    reference_text: str,
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
            word_timestamps=True,
        )
        cues = align_reference_subtitles(
            reference_text=reference_text,
            segments=tuple(segments),
            duration_ms=duration_ms,
        )
    except LocalWhisperError as exc:
        raise WhisperSubtitleError(str(exc)) from exc
    except Exception as exc:
        raise WhisperSubtitleError(f"Whisper 字幕识别失败：{exc}") from exc
    validate_subtitle_cues(cues, duration_ms=duration_ms)
    full_text = reference_text.strip()
    return GeneratedSubtitles(
        content=build_webvtt(cues),
        text=full_text,
        language=str(getattr(info, "language", "zh") or "zh"),
        model=f"{model_name}:source-aligned-v1",
        duration_ms=duration_ms,
        cues=cues,
    )
