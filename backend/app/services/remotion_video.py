from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from app.core.config import Settings, get_settings


REMOTION_TEMPLATE_ID = "narrated-panel-v1"
REMOTION_MOTION_PRESETS = frozenset(
    {
        "static",
        "zoom_in",
        "zoom_out",
        "pan_left",
        "pan_right",
        "pan_up",
        "pan_down",
    }
)


class RemotionVideoError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemotionScene:
    scene_id: str
    image_path: Path
    audio_path: Path
    subtitle: str
    duration_ms: int
    motion_preset: str
    image_width: int
    image_height: int


@dataclass(frozen=True)
class GeneratedRemotionVideo:
    content: bytes
    content_type: str
    template_id: str
    renderer_version: str
    duration_ms: int
    duration_in_frames: int
    fps: int
    width: int
    height: int


def _project_dir(settings: Settings) -> Path:
    project_dir = settings.remotion_project_dir
    if not project_dir.is_absolute():
        project_dir = Path(__file__).resolve().parents[3] / project_dir
    return project_dir.resolve()


def _validate_scene(scene: RemotionScene, index: int) -> None:
    if not scene.scene_id.strip():
        raise RemotionVideoError(f"第 {index} 个 Scene 缺少 ID")
    if not scene.image_path.is_file():
        raise RemotionVideoError(f"第 {index} 个 Scene 图片文件不存在")
    if not scene.audio_path.is_file():
        raise RemotionVideoError(f"第 {index} 个 Scene 音频文件不存在")
    if not scene.subtitle.strip():
        raise RemotionVideoError(f"第 {index} 个 Scene 字幕不能为空")
    if scene.duration_ms <= 0:
        raise RemotionVideoError(f"第 {index} 个 Scene 音频时长无效")
    if scene.motion_preset not in REMOTION_MOTION_PRESETS:
        raise RemotionVideoError(
            f"第 {index} 个 Scene Motion 不受支持：{scene.motion_preset}"
        )
    if not 64 <= scene.image_width <= 4096:
        raise RemotionVideoError(
            f"第 {index} 个 Scene 图片宽度超出 64–4096"
        )
    if not 64 <= scene.image_height <= 4096:
        raise RemotionVideoError(
            f"第 {index} 个 Scene 图片高度超出 64–4096"
        )


def _even_dimension(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def render_remotion_video(
    *,
    scenes: list[RemotionScene],
    bgm_path: Path | None,
    settings: Settings | None = None,
) -> GeneratedRemotionVideo:
    resolved_settings = settings or get_settings()
    if not scenes:
        raise RemotionVideoError("render_story_video 至少需要一个 Scene")
    if len(scenes) > 30:
        raise RemotionVideoError("render_story_video 最多支持 30 个 Scene")
    for index, scene in enumerate(scenes, start=1):
        _validate_scene(scene, index)
    source_ratio = scenes[0].image_width / scenes[0].image_height
    for index, scene in enumerate(scenes[1:], start=2):
        scene_ratio = scene.image_width / scene.image_height
        if abs(scene_ratio - source_ratio) > 0.01:
            raise RemotionVideoError(
                f"第 {index} 个 Scene 图片比例与首张图片不一致"
            )
    if bgm_path is not None and not bgm_path.is_file():
        raise RemotionVideoError("BGM 音频文件不存在")

    project_dir = _project_dir(resolved_settings)
    render_script = project_dir / "render.mjs"
    node_modules = project_dir / "node_modules"
    if not render_script.is_file():
        raise RemotionVideoError(
            f"Remotion 渲染脚本不存在：{render_script}"
        )
    if not node_modules.is_dir():
        raise RemotionVideoError(
            f"Remotion 依赖未安装：请在 {project_dir} 执行 npm ci"
        )

    manifest = {
        "templateId": REMOTION_TEMPLATE_ID,
        "width": _even_dimension(scenes[0].image_width),
        "height": _even_dimension(scenes[0].image_height),
        "scenes": [
            {
                "id": scene.scene_id,
                "imagePath": str(scene.image_path.resolve()),
                "audioPath": str(scene.audio_path.resolve()),
                "subtitle": scene.subtitle.strip(),
                "durationMs": scene.duration_ms,
                "motion": scene.motion_preset,
            }
            for scene in scenes
        ],
        "bgmPath": str(bgm_path.resolve()) if bgm_path is not None else None,
    }
    with TemporaryDirectory(prefix="doodlestory-remotion-input-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "manifest.json"
        output_path = temp_path / "output.mp4"
        input_path.write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [
                    resolved_settings.remotion_node_executable,
                    str(render_script),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=resolved_settings.remotion_render_timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RemotionVideoError(
                f"Remotion Node 可执行文件不存在："
                f"{resolved_settings.remotion_node_executable}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RemotionVideoError(
                "Remotion 视频渲染超时"
            ) from exc
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout).strip()[-2000:]
            raise RemotionVideoError(
                f"Remotion 视频渲染失败：exit={completed.returncode} "
                f"error={error}"
            )
        result: dict[str, object] | None = None
        for line in reversed(completed.stdout.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                result = candidate
                break
        if result is None or result.get("status") != "succeeded":
            raise RemotionVideoError("Remotion 成功退出但没有返回渲染结果")
        if not output_path.is_file():
            raise RemotionVideoError("Remotion 成功退出但没有生成 MP4")
        content = output_path.read_bytes()
        if not content:
            raise RemotionVideoError("Remotion 生成了空 MP4")
        duration_ms = sum(scene.duration_ms for scene in scenes)
        return GeneratedRemotionVideo(
            content=content,
            content_type="video/mp4",
            template_id=str(result.get("templateId") or ""),
            renderer_version=str(result.get("rendererVersion") or ""),
            duration_ms=duration_ms,
            duration_in_frames=int(result.get("durationInFrames") or 0),
            fps=int(result.get("fps") or 0),
            width=int(result.get("width") or 0),
            height=int(result.get("height") or 0),
        )
