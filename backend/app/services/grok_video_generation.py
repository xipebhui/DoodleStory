from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from app.core.config import Settings, get_settings
from app.services.grokcli_runtime import serialized_grokcli_call


GROKCLI_PINNED_COMMIT = "2dcd4d4b2dc6c35f013a6b2a826721e4b98bfe13"
GROKCLI_PINNED_VERSION = "0.2.0"
GROK_VIDEO_TEMPLATE_ID = "grok-video-clip-v1"
GROK_VIDEO_ASPECT_RATIOS = frozenset(
    {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"}
)
GROK_VIDEO_RESOLUTIONS = frozenset({"480p", "720p", "1080p"})
GROK_VIDEO_MIN_DURATION_SECONDS = 1
GROK_VIDEO_MAX_DURATION_SECONDS = 15
_MP4_FORMAT_NAMES = frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"})
_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|access[_-]?token|refresh[_-]?token|bearer)"
    r"(\s*[:=]\s*|\s+)([^\s,;]+)"
)


class GrokVideoConfigError(RuntimeError):
    pass


class GrokVideoGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedGrokVideo:
    content: bytes
    content_type: str
    template_id: str
    renderer_version: str
    provider: str
    model: str
    mode: str
    duration_ms: int
    duration_in_frames: int
    fps: int
    width: int
    height: int


def _clean_error_output(value: str) -> str:
    compact = " ".join(value.strip().split())[:1000]
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", compact)


def build_grokcli_video_command(
    *,
    prompt: str,
    image_path: Path | None,
    duration_seconds: int,
    aspect_ratio: str,
    settings: Settings | None = None,
) -> list[str]:
    resolved_settings = settings or get_settings()
    executable = resolved_settings.grokcli_executable.strip()
    if not executable:
        raise GrokVideoConfigError("GROKCLI_EXECUTABLE 未配置")
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise GrokVideoConfigError("Grok 视频 Prompt 不能为空")
    if aspect_ratio not in GROK_VIDEO_ASPECT_RATIOS:
        supported = "、".join(sorted(GROK_VIDEO_ASPECT_RATIOS))
        raise GrokVideoConfigError(
            f"Grok 视频不支持画面比例 {aspect_ratio}，可用值：{supported}"
        )
    if not GROK_VIDEO_MIN_DURATION_SECONDS <= duration_seconds <= GROK_VIDEO_MAX_DURATION_SECONDS:
        raise GrokVideoConfigError("Grok 视频时长只支持 1–15 秒")
    model = resolved_settings.grokcli_video_model.strip()
    if not model:
        raise GrokVideoConfigError("GROKCLI_VIDEO_MODEL 未配置")
    resolution = resolved_settings.grokcli_video_resolution.strip().lower()
    if resolution not in GROK_VIDEO_RESOLUTIONS:
        raise GrokVideoConfigError(
            "GROKCLI_VIDEO_RESOLUTION 只支持 480p、720p 或 1080p"
        )
    if image_path is not None:
        image_path = image_path.expanduser().resolve()
        if not image_path.is_file():
            raise GrokVideoConfigError("Grok 图生视频源图片不存在")

    command = [
        executable,
        "video",
        cleaned_prompt,
        "--model",
        model,
        "--aspect",
        aspect_ratio,
        "--resolution",
        resolution,
        "--duration",
        str(duration_seconds),
        "--timeout",
        str(resolved_settings.grokcli_video_timeout_seconds),
        "--output",
        "json",
        "--no-color",
    ]
    if image_path is not None:
        command.extend(["--image", str(image_path)])
    return command


def _parse_grokcli_video_path(stdout: str, output_root: Path) -> Path:
    try:
        body = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GrokVideoGenerationError("grokcli 返回内容不是合法 JSON") from exc
    raw_path = body.get("path") if isinstance(body, dict) else None
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise GrokVideoGenerationError("grokcli 返回中缺少唯一视频路径")
    video_path = Path(raw_path).expanduser().resolve()
    resolved_root = output_root.resolve()
    if not video_path.is_relative_to(resolved_root):
        raise GrokVideoGenerationError("grokcli 返回了输出目录之外的视频路径")
    if not video_path.is_file():
        raise GrokVideoGenerationError("grokcli 成功退出但没有生成视频文件")
    candidates = [path for path in resolved_root.rglob("*") if path.is_file()]
    if candidates != [video_path]:
        raise GrokVideoGenerationError("grokcli 输出目录必须且只能包含一个视频文件")
    return video_path


def _probe_grok_video(
    video_path: Path,
    *,
    settings: Settings,
) -> tuple[int, int, int, int, int]:
    try:
        completed = subprocess.run(
            [
                settings.ffprobe_executable,
                "-v",
                "error",
                "-count_frames",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration:format=format_name,duration",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GrokVideoConfigError(
            f"找不到 ffprobe 可执行文件：{settings.ffprobe_executable}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GrokVideoGenerationError("ffprobe 校验 Grok 视频超时") from exc
    if completed.returncode != 0:
        error = _clean_error_output(completed.stderr or completed.stdout)
        raise GrokVideoGenerationError(
            f"ffprobe 无法解析 Grok 视频：exit={completed.returncode} error={error}"
        )
    try:
        body = json.loads(completed.stdout)
        streams = body["streams"]
        stream = streams[0]
        format_data = body["format"]
        codec_name = str(stream["codec_name"])
        width = int(stream["width"])
        height = int(stream["height"])
        frame_rate = float(Fraction(str(stream["avg_frame_rate"])))
        frame_count = int(stream["nb_read_frames"])
        duration_seconds = float(
            stream.get("duration") or format_data["duration"]
        )
        format_names = set(str(format_data["format_name"]).split(","))
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise GrokVideoGenerationError("ffprobe 返回的视频元数据不完整") from exc
    if codec_name != "h264":
        raise GrokVideoGenerationError(
            f"Grok 视频编码必须为 H.264，实际为 {codec_name or 'unknown'}"
        )
    if not format_names.intersection(_MP4_FORMAT_NAMES):
        raise GrokVideoGenerationError("Grok 视频容器不是 MP4")
    if width <= 0 or height <= 0 or duration_seconds <= 0:
        raise GrokVideoGenerationError("Grok 视频宽高或时长无效")
    if frame_rate <= 0 or frame_count <= 0:
        raise GrokVideoGenerationError("Grok 视频帧率或帧数无效")
    return (
        round(duration_seconds * 1000),
        frame_count,
        round(frame_rate),
        width,
        height,
    )


def _raise_grokcli_failure(returncode: int, output: str) -> None:
    error = _clean_error_output(output)
    labels = {
        2: "参数配置错误",
        3: "OAuth 认证或订阅权限错误",
        4: "额度或计费限制",
        5: "服务端生成超时",
        6: "网络错误",
        10: "内容审核拦截",
    }
    label = labels.get(returncode, "生成错误")
    exception_type = GrokVideoConfigError if returncode in {2, 3} else GrokVideoGenerationError
    raise exception_type(
        f"grokcli 视频{label}（退出码 {returncode}）：{error or '无错误详情'}"
    )


def request_grokcli_video(
    *,
    prompt: str,
    image_path: Path | None,
    duration_seconds: int,
    aspect_ratio: str,
    settings: Settings | None = None,
) -> GeneratedGrokVideo:
    resolved_settings = settings or get_settings()
    command = build_grokcli_video_command(
        prompt=prompt,
        image_path=image_path,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        settings=resolved_settings,
    )
    environment = os.environ.copy()
    environment["NO_COLOR"] = "1"
    if resolved_settings.grokcli_home.strip():
        environment["GROKCLI_HOME"] = resolved_settings.grokcli_home.strip()

    with tempfile.TemporaryDirectory(prefix="doodlestory-grokcli-video-") as temporary_dir:
        working_directory = Path(temporary_dir)
        output_root = working_directory / "output"
        environment["GROKCLI_OUTPUT_DIR"] = str(output_root)
        try:
            with serialized_grokcli_call():
                completed = subprocess.run(
                    command,
                    cwd=working_directory,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=resolved_settings.grokcli_video_timeout_seconds + 15,
                    check=False,
                )
        except FileNotFoundError as exc:
            raise GrokVideoConfigError(
                f"找不到 grokcli 可执行文件：{command[0]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GrokVideoGenerationError(
                "grokcli 视频进程超时；结果状态未知，禁止自动重试"
            ) from exc
        if completed.returncode != 0:
            _raise_grokcli_failure(
                completed.returncode,
                completed.stderr or completed.stdout,
            )
        video_path = _parse_grokcli_video_path(completed.stdout, output_root)
        try:
            content = video_path.read_bytes()
        except OSError as exc:
            raise GrokVideoGenerationError("无法读取 grokcli 生成的视频") from exc
        if len(content) < 12 or content[4:8] != b"ftyp":
            raise GrokVideoGenerationError("grokcli 输出不是有效 MP4 文件")
        duration_ms, frame_count, fps, width, height = _probe_grok_video(
            video_path,
            settings=resolved_settings,
        )
        return GeneratedGrokVideo(
            content=content,
            content_type="video/mp4",
            template_id=GROK_VIDEO_TEMPLATE_ID,
            renderer_version=f"grokcli/{GROKCLI_PINNED_VERSION}",
            provider="grok",
            model=resolved_settings.grokcli_video_model.strip(),
            mode="image_to_video" if image_path is not None else "text_to_video",
            duration_ms=duration_ms,
            duration_in_frames=frame_count,
            fps=fps,
            width=width,
            height=height,
        )
