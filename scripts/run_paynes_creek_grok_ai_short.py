from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

from app.core.config import get_settings
from app.services.siliconflow_voice import SiliconFlowVoiceClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN_PATH = (
    PROJECT_ROOT
    / "docs/strategy/youtube/paynes-creek-grok-ai-short-v1.json"
)
REMOTION_ROOT = PROJECT_ROOT / "remotion"
RENDER_SCRIPT = REMOTION_ROOT / "render-paynes-creek-grok-short.mjs"
TEMPLATE_ID = "paynes-creek-grok-ai-short-v1"
SCENE_IDS = ("S01", "S03", "S04", "S09", "S12")
FPS = 30
WIDTH = 1920
HEIGHT = 1080
SUPPORTED_LOCALES = frozenset({"zh-CN", "en-US"})
SUPPORTED_EDIT_MODES = frozenset({"classic", "retention"})
RETENTION_MOTIONS = frozenset({"push_in", "drift_left", "drift_right"})
RETENTION_VISUAL_TREATMENTS = (
    "coast_to_inland",
    "process_filter",
    "process_boil",
    "transport_clue",
    "evidence_chain",
)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_plan(plan_path: Path = DEFAULT_PLAN_PATH) -> dict[str, Any]:
    value = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("scenes"), list):
        raise RuntimeError("Grok AI 短片计划结构无效")
    if value.get("template_id") != TEMPLATE_ID:
        raise RuntimeError("Grok AI 短片计划模板无效")
    if value.get("locale") not in SUPPORTED_LOCALES:
        raise RuntimeError("Grok AI 短片 locale 只支持 zh-CN 或 en-US")
    if value.get("edit_mode") not in SUPPORTED_EDIT_MODES:
        raise RuntimeError("Grok AI 短片 edit_mode 只支持 classic 或 retention")
    if not str(value.get("footer") or "").strip():
        raise RuntimeError("Grok AI 短片计划缺少页脚")
    artifact_slug = str(value.get("artifact_slug") or "")
    if (
        not artifact_slug
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in artifact_slug)
        or artifact_slug.startswith("-")
        or artifact_slug.endswith("-")
    ):
        raise RuntimeError("Grok AI 短片 artifact_slug 无效")
    if value.get("publication_authorized") is not False or value.get("bgm") is not False:
        raise RuntimeError("Grok AI 短片必须保持禁止发布且无 BGM")
    scene_ids = tuple(str(scene.get("id")) for scene in value["scenes"])
    if scene_ids != SCENE_IDS:
        raise RuntimeError("Grok AI 短片场景顺序必须固定为 S01/S03/S04/S09/S12")
    if value["edit_mode"] == "retention":
        if value["locale"] != "en-US":
            raise RuntimeError("Retention edit 当前只支持 en-US")
        word_count = 0
        for index, scene in enumerate(value["scenes"]):
            narration = str(scene.get("narration") or "").strip()
            captions = scene.get("captions")
            if (
                not isinstance(captions, list)
                or not 2 <= len(captions) <= 4
                or any(not isinstance(caption, str) or not caption.strip() for caption in captions)
                or " ".join(captions) != narration
            ):
                raise RuntimeError(f"Retention Scene {scene_ids[index]} 短语字幕未完整重建旁白")
            if not isinstance(scene.get("timing_weight"), int) or not 1 <= scene["timing_weight"] <= 100:
                raise RuntimeError(f"Retention Scene {scene_ids[index]} timing_weight 无效")
            if scene.get("motion") not in RETENTION_MOTIONS:
                raise RuntimeError(f"Retention Scene {scene_ids[index]} motion 无效")
            if scene.get("visual_treatment") != RETENTION_VISUAL_TREATMENTS[index]:
                raise RuntimeError(f"Retention Scene {scene_ids[index]} visual_treatment 无效")
            word_count += len(narration.split())
        hook = value["scenes"][0].get("hook")
        if not isinstance(hook, dict) or any(
            not str(hook.get(key) or "").strip()
            for key in ("eyebrow", "headline", "question")
        ):
            raise RuntimeError("Retention edit 缺少前三秒钩子")
        if not 90 <= word_count <= 115:
            raise RuntimeError("Retention edit 英文旁白必须控制在 90–115 词")
    return value


def output_names(plan: dict[str, Any]) -> dict[str, str]:
    slug = str(plan["artifact_slug"])
    return {
        "audio": f"{slug}-narration.mp3",
        "manifest": f"{slug}-manifest.json",
        "raw_video": f"{slug}.mp4",
        "video": f"{slug}-yuv420p.mp4",
        "contact_sheet": f"{slug}-contact-sheet.png",
        "report": f"{slug}-report.json",
    }


def narration_text(plan: dict[str, Any]) -> str:
    separator = " " if plan["locale"] == "en-US" else ""
    return separator.join(str(scene["narration"]) for scene in plan["scenes"])


def allocate_scene_frames(total_frames: int, weights: list[int]) -> list[int]:
    if not weights or any(weight <= 0 for weight in weights):
        raise RuntimeError("Grok AI 短片场景权重必须全部为正整数")
    if total_frames < len(weights) * 120:
        raise RuntimeError("真实旁白太短，无法为每个场景分配至少四秒")
    weight_sum = sum(weights)
    raw = [total_frames * weight / weight_sum for weight in weights]
    frames = [math.floor(value) for value in raw]
    for index in sorted(
        range(len(raw)),
        key=lambda item: raw[item] - frames[item],
        reverse=True,
    )[: total_frames - sum(frames)]:
        frames[index] += 1
    if any(frame < 120 for frame in frames):
        raise RuntimeError("旁白权重导致某个场景不足四秒")
    return frames


def allocate_caption_frames(total_frames: int, captions: list[str]) -> list[int]:
    weights = [max(1, len(caption.split())) for caption in captions]
    weight_sum = sum(weights)
    raw = [total_frames * weight / weight_sum for weight in weights]
    frames = [math.floor(value) for value in raw]
    for index in sorted(
        range(len(raw)),
        key=lambda item: raw[item] - frames[item],
        reverse=True,
    )[: total_frames - sum(frames)]:
        frames[index] += 1
    if any(frame <= 0 for frame in frames):
        raise RuntimeError("短语字幕未获得有效帧数")
    return frames


def ffprobe(path: Path) -> dict[str, Any]:
    executable = get_settings().ffprobe_executable
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,pix_fmt,color_range,avg_frame_rate,nb_read_frames,duration:format=format_name,duration",
            "-of",
            "json",
            str(path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"ffprobe 无法解析 {path.name}：{(completed.stderr or completed.stdout).strip()[-1000:]}"
        )
    return json.loads(completed.stdout)


def media_duration_ms(probe: dict[str, Any]) -> int:
    return round(float(probe["format"]["duration"]) * 1000)


def stream_by_type(probe: dict[str, Any], stream_type: str) -> dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == stream_type:
            return stream
    raise RuntimeError(f"媒体缺少 {stream_type} stream")


def frame_rate(stream: dict[str, Any]) -> float:
    numerator, denominator = str(stream["avg_frame_rate"]).split("/", 1)
    return float(numerator) / float(denominator)


def validate_source_clip(
    scene: dict[str, Any],
    video_path: Path,
    probe: dict[str, Any],
) -> None:
    video = stream_by_type(probe, "video")
    if video.get("codec_name") != "h264":
        raise RuntimeError(f"{scene['id']} Grok 视频不是 H.264")
    if int(video.get("width", 0)) != 1280 or int(video.get("height", 0)) != 720:
        raise RuntimeError(f"{scene['id']} Grok 视频不是 1280×720")
    if abs(frame_rate(video) - 24) > 0.01:
        raise RuntimeError(f"{scene['id']} Grok 视频不是 24fps")
    if abs(media_duration_ms(probe) - int(scene["video_duration_ms"])) > 100:
        raise RuntimeError(f"{scene['id']} Grok 视频时长与计划不一致")
    if sha256_file(video_path) != scene["video_sha256"]:
        raise RuntimeError(f"{scene['id']} Grok 视频 hash 漂移")


def resolve_plan_media(plan: dict[str, Any]) -> list[dict[str, Any]]:
    resolved = []
    for scene in plan["scenes"]:
        image_path = (PROJECT_ROOT / scene["image_path"]).resolve()
        video_path = (PROJECT_ROOT / scene["video_path"]).resolve()
        if not image_path.is_file() or not video_path.is_file():
            raise RuntimeError(f"{scene['id']} 缺少选中图片或 Grok 视频")
        if sha256_file(image_path) != scene["image_sha256"]:
            raise RuntimeError(f"{scene['id']} 选中图片 hash 漂移")
        video_probe = ffprobe(video_path)
        validate_source_clip(scene, video_path, video_probe)
        resolved.append(
            {
                **scene,
                "image_path_resolved": image_path,
                "video_path_resolved": video_path,
                "video_probe": video_probe,
            }
        )
    return resolved


def build_render_manifest(
    *,
    plan: dict[str, Any],
    resolved_scenes: list[dict[str, Any]],
    audio_path: Path,
    audio_duration_ms: int,
    audio_sha256: str,
    source_plan_path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, Any]:
    total_frames = math.ceil((audio_duration_ms / 1000) * FPS)
    scene_frames = allocate_scene_frames(
        total_frames,
        [
            int(scene.get("timing_weight", len(str(scene["narration"]))))
            for scene in resolved_scenes
        ],
    )
    scenes = []
    for scene, duration_in_frames in zip(resolved_scenes, scene_frames, strict=True):
        scene_duration_ms = (duration_in_frames / FPS) * 1000
        playback_rate = int(scene["video_duration_ms"]) / scene_duration_ms
        if not 0.65 <= playback_rate <= 1.35:
            raise RuntimeError(
                f"{scene['id']} 需要的 playback rate {playback_rate:.4f} 超出安全范围"
            )
        caption_texts = list(scene.get("captions") or [str(scene["narration"])])
        caption_frames = allocate_caption_frames(duration_in_frames, caption_texts)
        caption_offset = 0
        caption_cues = []
        for caption, caption_duration in zip(
            caption_texts,
            caption_frames,
            strict=True,
        ):
            caption_cues.append(
                {
                    "text": caption,
                    "startFrame": caption_offset,
                    "endFrame": caption_offset + caption_duration,
                }
            )
            caption_offset += caption_duration
        scenes.append(
            {
                "id": scene["id"],
                "title": scene["title"],
                "narration": scene["narration"],
                "evidence": scene["evidence"],
                "videoPath": str(scene["video_path_resolved"]),
                "videoSha256": scene["video_sha256"],
                "videoDurationMs": scene["video_duration_ms"],
                "durationInFrames": duration_in_frames,
                "playbackRate": playback_rate,
                "captions": caption_cues,
                "motion": scene.get("motion", "none"),
                "visualTreatment": scene.get("visual_treatment", "none"),
                "hook": scene.get("hook"),
            }
        )
    return {
        "schemaVersion": 1,
        "templateId": TEMPLATE_ID,
        "title": plan["title"],
        "locale": plan["locale"],
        "editMode": plan["edit_mode"],
        "footer": plan["footer"],
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "publicationAuthorized": False,
        "bgm": False,
        "sourcePlan": str(source_plan_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "sourcePlanSha256": sha256_file(source_plan_path),
        "narrationAudioPath": str(audio_path.resolve()),
        "narrationSha256": audio_sha256,
        "audioDurationMs": audio_duration_ms,
        "totalFrames": total_frames,
        "scenes": scenes,
    }


def normalize_video(raw_path: Path, final_path: Path) -> None:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise RuntimeError("找不到 ffmpeg")
    completed = subprocess.run(
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-i",
            str(raw_path),
            "-vf",
            "scale=in_range=pc:out_range=tv,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(final_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=get_settings().remotion_render_timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"FFmpeg 规范化失败：{(completed.stderr or completed.stdout).strip()[-1500:]}"
        )


def validate_final_video(
    probe: dict[str, Any],
    *,
    audio_duration_ms: int,
    total_frames: int,
) -> None:
    video = stream_by_type(probe, "video")
    audio = stream_by_type(probe, "audio")
    checks = {
        "video_codec": video.get("codec_name") == "h264",
        "audio_codec": audio.get("codec_name") == "aac",
        "size": (int(video.get("width", 0)), int(video.get("height", 0)))
        == (WIDTH, HEIGHT),
        "fps": abs(frame_rate(video) - FPS) <= 0.01,
        "frames": abs(int(video.get("nb_read_frames", 0)) - total_frames) <= 1,
        "pixel_format": video.get("pix_fmt") == "yuv420p",
        "duration": abs(media_duration_ms(probe) - audio_duration_ms) <= 1000,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"最终 Grok AI 短片媒体检查失败：{failed}")


def extract_contact_sheet(
    video_path: Path,
    output_path: Path,
    manifest: dict[str, Any],
) -> list[int]:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise RuntimeError("找不到 ffmpeg")
    frames = []
    offset = 0
    for scene in manifest["scenes"]:
        duration = int(scene["durationInFrames"])
        frames.append(offset + duration // 2)
        offset += duration
    selector = "+".join(f"eq(n\\,{frame})" for frame in frames)
    completed = subprocess.run(
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"select={selector},scale=480:-1,tile=5x1:padding=8:margin=8:color=0x061922",
            "-fps_mode",
            "vfr",
            "-frames:v",
            "1",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"最终 Grok AI 短片接触表生成失败：{(completed.stderr or completed.stdout).strip()[-1200:]}"
        )
    return frames


def preflight(
    source_commit: str,
    output_dir: Path,
    plan_path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, Any]:
    plan = load_plan(plan_path)
    names = output_names(plan)
    current_commit = _git("rev-parse", "HEAD")
    checks = {
        "source_commit_matches": source_commit == current_commit,
        "worktree_clean": not _git("status", "--porcelain"),
        "plan_template": plan["template_id"] == TEMPLATE_ID,
        "scene_count": len(plan["scenes"]) == 5,
        "siliconflow_key_configured": bool(get_settings().siliconflow_api_key.strip()),
        "ffprobe_available": Path(get_settings().ffprobe_executable).is_file()
        or shutil.which(get_settings().ffprobe_executable) is not None,
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "node_available": shutil.which("node") is not None,
        "remotion_renderer_exists": RENDER_SCRIPT.is_file(),
        "remotion_dependencies_exist": (REMOTION_ROOT / "node_modules").is_dir(),
        "output_files_absent": not any(
            (output_dir / name).exists() for name in names.values()
        ),
    }
    media_error = None
    try:
        resolve_plan_media(plan)
    except Exception as exc:  # noqa: BLE001 - preflight must report the exact blocker
        media_error = str(exc)
    checks["selected_media_verified"] = media_error is None
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "all_passed": not blockers,
        "blockers": blockers,
        "checks": checks,
        "media_error": media_error,
        "source_commit": source_commit,
        "observed_commit": current_commit,
        "source_plan": str(plan_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_plan_sha256": sha256_file(plan_path),
    }


def execute(
    source_commit: str,
    output_dir: Path,
    plan_path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, Any]:
    initial = preflight(source_commit, output_dir, plan_path)
    if not initial["all_passed"]:
        raise RuntimeError(f"Grok AI 短片 preflight 未通过：{initial['blockers']}")
    output_dir.mkdir(parents=True, exist_ok=False)
    plan = load_plan(plan_path)
    names = output_names(plan)
    resolved_scenes = resolve_plan_media(plan)
    narration = narration_text(plan)
    audio_path = output_dir / names["audio"]
    tts = plan["tts"]
    audio_content, audio_content_type = SiliconFlowVoiceClient().generate_speech(
        text=narration,
        voice_uri=tts["voice"],
        model=tts["model"],
        response_format=tts["response_format"],
        sample_rate=int(tts["sample_rate"]),
        speed=float(tts["speed"]),
        gain=0.0,
        timeout=get_settings().video_tts_timeout_seconds,
    )
    if not audio_content:
        raise RuntimeError("SiliconFlow TTS 返回空音频")
    audio_path.write_bytes(audio_content)
    audio_probe = ffprobe(audio_path)
    audio_duration_ms = media_duration_ms(audio_probe)
    manifest = build_render_manifest(
        plan=plan,
        resolved_scenes=resolved_scenes,
        audio_path=audio_path,
        audio_duration_ms=audio_duration_ms,
        audio_sha256=sha256_bytes(audio_content),
        source_plan_path=plan_path,
    )
    manifest_path = output_dir / names["manifest"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    raw_video_path = output_dir / names["raw_video"]
    completed = subprocess.run(
        [
            "node",
            str(RENDER_SCRIPT),
            "--input",
            str(manifest_path),
            "--output",
            str(raw_video_path),
        ],
        cwd=REMOTION_ROOT,
        text=True,
        capture_output=True,
        timeout=get_settings().remotion_render_timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Remotion Grok AI 短片渲染失败：{(completed.stderr or completed.stdout).strip()[-2000:]}"
        )
    renderer_result = None
    for line in reversed(completed.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            renderer_result = candidate
            break
    if renderer_result is None or renderer_result.get("status") != "succeeded":
        raise RuntimeError("Remotion 成功退出但没有 Grok AI 短片结构化结果")

    final_video_path = output_dir / names["video"]
    normalize_video(raw_video_path, final_video_path)
    final_probe = ffprobe(final_video_path)
    validate_final_video(
        final_probe,
        audio_duration_ms=audio_duration_ms,
        total_frames=int(manifest["totalFrames"]),
    )
    contact_path = output_dir / names["contact_sheet"]
    midpoint_frames = extract_contact_sheet(
        final_video_path,
        contact_path,
        manifest,
    )
    report = {
        "schema_version": 1,
        "record_kind": "paynes_creek_grok_ai_short_local_pilot",
        "status": "rendered_awaiting_full_watch_review",
        "source_git_commit": source_commit,
        "publication_authorized": False,
        "source": {
            "plan": str(plan_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "plan_sha256": sha256_file(plan_path),
            "locale": plan["locale"],
            "edit_mode": plan["edit_mode"],
            "scene_count": 5,
        },
        "calls": {
            **plan["attempt_accounting"],
            "siliconflow_tts": 1,
            "remotion_render": 1,
            "ffmpeg_normalization": 1,
            "publish": 0,
        },
        "audio": {
            "provider": tts["provider"],
            "model": tts["model"],
            "voice": tts["voice"],
            "path": str(audio_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sha256": sha256_file(audio_path),
            "bytes": audio_path.stat().st_size,
            "duration_ms": audio_duration_ms,
            "content_type": audio_content_type,
            "probe": audio_probe,
        },
        "render": {
            "template_id": TEMPLATE_ID,
            "renderer_result": renderer_result,
            "manifest": str(manifest_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "manifest_sha256": sha256_file(manifest_path),
            "raw_video": str(raw_video_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "raw_video_sha256": sha256_file(raw_video_path),
            "video": str(final_video_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "video_sha256": sha256_file(final_video_path),
            "video_bytes": final_video_path.stat().st_size,
            "duration_ms": media_duration_ms(final_probe),
            "probe": final_probe,
        },
        "evidence": {
            "contact_sheet": str(contact_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "scene_midpoint_frames": midpoint_frames,
            "visual_review": "not_reviewed",
            "full_watch_review": "not_reviewed",
        },
        "sensitive_values_removed": True,
    }
    report_path = output_dir / names["report"]
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the five-scene Paynes Creek Grok AI local short"
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument(
        "--plan",
        default="docs/strategy/youtube/paynes-creek-grok-ai-short-v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default="storage/exports/paynes-creek/grok-ai-short-v1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan_path = (PROJECT_ROOT / args.plan).resolve()
    if not plan_path.is_relative_to(PROJECT_ROOT) or not plan_path.is_file():
        raise RuntimeError("--plan 必须是项目内存在的 JSON 文件")
    output_dir = (PROJECT_ROOT / args.output_dir).resolve()
    if args.preflight:
        result = preflight(args.source_git_commit, output_dir, plan_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["all_passed"] else 2
    report = execute(args.source_git_commit, output_dir, plan_path)
    print(
        json.dumps(
            {
                "status": report["status"],
                "video": report["render"]["video"],
                "video_sha256": report["render"]["video_sha256"],
                "duration_ms": report["render"]["duration_ms"],
                "tts_calls": report["calls"]["siliconflow_tts"],
                "render_calls": report["calls"]["remotion_render"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
