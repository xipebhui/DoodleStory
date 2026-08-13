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
DRAFT_PATH = PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-production-draft.json"
REMOTION_ROOT = PROJECT_ROOT / "remotion"
RENDER_SCRIPT = REMOTION_ROOT / "render-paynes-creek.mjs"
EXPECTED_DRAFT_SHA256 = "cf51a723e441c6635b7fdf3f1984f2e935e0d3155dc7b8a95892c7ccb88c32e4"
EXPECTED_NARRATION_SHA256 = "adca90d4366d27d05b62a4b79063d596826d798bac39f95c6cff73c7df57f7dd"
TEMPLATE_ID = "paynes-creek-vector-v1"
TTS_MODEL = "FunAudioLLM/CosyVoice2-0.5B"
TTS_VOICE = "FunAudioLLM/CosyVoice2-0.5B:alex"
FPS = 30
WIDTH = 1920
HEIGHT = 1080
OUTPUT_NAMES = {
    "audio": "paynes-creek-narration-v1.mp3",
    "manifest": "paynes-creek-vector-manifest-v1.json",
    "raw_video": "paynes-creek-vector-pilot-v1.mp4",
    "video": "paynes-creek-vector-pilot-v1-yuv420p.mp4",
    "contact_sheet": "paynes-creek-vector-contact-sheet-v1.png",
    "s03_frame": "paynes-creek-s03-midpoint-v1.png",
    "report": "paynes-creek-vector-pilot-v1-report.json",
}
EVIDENCE_LABELS = {
    "S01": "解释",
    "S02": "直接证据",
    "S03": "重建",
    "S04": "解释",
    "S05": "解释",
    "S06": "解释",
    "S07": "解释",
    "S08": "直接证据",
    "S09": "未知边界",
    "S10": "未知边界",
    "S11": "直接证据",
    "S12": "未知边界",
}


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


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_draft() -> dict[str, Any]:
    value = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("scenes"), list):
        raise RuntimeError("Paynes Creek 生产草案结构无效")
    return value


def narration_text(draft: dict[str, Any]) -> str:
    return "".join(str(scene["narration"]) for scene in draft["scenes"])


def allocate_scene_frames(total_frames: int, weights: list[int]) -> list[int]:
    if total_frames < len(weights) * FPS:
        raise RuntimeError("真实旁白太短，无法为每个 Scene 分配至少一秒")
    if not weights or any(weight <= 0 for weight in weights):
        raise RuntimeError("Scene 时长权重必须全部为正整数")
    weight_sum = sum(weights)
    ideal = [total_frames * weight / weight_sum for weight in weights]
    frames = [max(FPS, math.floor(value)) for value in ideal]
    difference = total_frames - sum(frames)
    if difference > 0:
        order = sorted(range(len(weights)), key=lambda index: (ideal[index] - math.floor(ideal[index]), -index), reverse=True)
        for offset in range(difference):
            frames[order[offset % len(order)]] += 1
    elif difference < 0:
        order = sorted(range(len(weights)), key=lambda index: (frames[index] - FPS, ideal[index]), reverse=True)
        remaining = -difference
        for index in order:
            removable = min(remaining, frames[index] - FPS)
            frames[index] -= removable
            remaining -= removable
            if remaining == 0:
                break
        if remaining:
            raise RuntimeError("无法在一秒最小时长内匹配真实旁白总帧数")
    if sum(frames) != total_frames:
        raise RuntimeError("Scene 帧数分配没有守恒")
    return frames


def build_manifest(
    *, draft: dict[str, Any], audio_path: Path, audio_duration_ms: int, audio_sha256: str
) -> dict[str, Any]:
    scenes = draft["scenes"]
    expected_ids = [f"S{index:02d}" for index in range(1, 13)]
    observed_ids = [str(scene.get("scene_id")) for scene in scenes]
    if observed_ids != expected_ids:
        raise RuntimeError("生产草案 Scene 顺序不是严格 S01–S12")
    full_narration = narration_text(draft)
    if sha256_text(full_narration) != EXPECTED_NARRATION_SHA256:
        raise RuntimeError("生产草案旁白 hash 与冻结值不一致")
    total_frames = math.ceil((audio_duration_ms / 1000) * FPS)
    frame_counts = allocate_scene_frames(
        total_frames,
        [int(scene["han_characters"]) for scene in scenes],
    )
    manifest_scenes = []
    for scene, duration_frames in zip(scenes, frame_counts, strict=True):
        scene_id = str(scene["scene_id"])
        heading = str(scene["prompt_heading"])
        title = heading.split("｜", 1)[1] if "｜" in heading else heading
        manifest_scenes.append(
            {
                "id": scene_id,
                "title": title,
                "narration": str(scene["narration"]),
                "evidence": EVIDENCE_LABELS[scene_id],
                "durationInFrames": duration_frames,
            }
        )
    return {
        "schemaVersion": 1,
        "templateId": TEMPLATE_ID,
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "publicationAuthorized": False,
        "bgm": False,
        "sourceDraft": "docs/strategy/youtube/paynes-creek-production-draft.json",
        "sourceDraftSha256": sha256_bytes(DRAFT_PATH.read_bytes()),
        "narrationAudioPath": str(audio_path.resolve()),
        "narrationSha256": EXPECTED_NARRATION_SHA256,
        "audioSha256": audio_sha256,
        "audioDurationMs": audio_duration_ms,
        "totalFrames": total_frames,
        "scenes": manifest_scenes,
    }


def ffprobe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,pix_fmt,color_range,r_frame_rate,duration,nb_frames,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe 失败：{completed.stderr.strip()[-500:]}")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("ffprobe 没有返回 JSON object")
    return value


def media_duration_ms(probe: dict[str, Any]) -> int:
    try:
        duration = float(probe["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("ffprobe 没有返回有效时长") from exc
    return round(duration * 1000)


def video_stream(probe: dict[str, Any]) -> dict[str, Any]:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise RuntimeError("MP4 ffprobe 缺少 streams")
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        raise RuntimeError("MP4 必须正好包含一条视频流")
    return videos[0]


def stream_duration_ms(stream: dict[str, Any]) -> int:
    try:
        return round(float(stream["duration"]) * 1000)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("ffprobe 视频流没有有效时长") from exc


def validate_video_probe(
    probe: dict[str, Any], *, source_audio_duration_ms: int, expected_total_frames: int
) -> dict[str, Any]:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise RuntimeError("MP4 ffprobe 缺少 streams")
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) != 1:
        raise RuntimeError("MP4 必须正好包含一条视频流和一条音频流")
    video = videos[0]
    audio = audios[0]
    checks = {
        "video_codec_h264": video.get("codec_name") == "h264",
        "audio_codec_aac": audio.get("codec_name") == "aac",
        "width_1920": video.get("width") == WIDTH,
        "height_1080": video.get("height") == HEIGHT,
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "fps_30": video.get("r_frame_rate") == "30/1",
        "frame_count_matches_manifest": int(video.get("nb_frames") or 0) == expected_total_frames,
        "video_stream_duration_within_one_frame_of_source_audio": abs(
            stream_duration_ms(video) - source_audio_duration_ms
        ) <= math.ceil(1000 / FPS),
    }
    if not all(checks.values()):
        raise RuntimeError(f"MP4 媒体校验失败：{checks}")
    return checks


def validate_raw_video_probe(probe: dict[str, Any], *, expected_total_frames: int) -> dict[str, Any]:
    video = video_stream(probe)
    streams = probe.get("streams", [])
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    checks = {
        "video_codec_h264": video.get("codec_name") == "h264",
        "audio_codec_aac": len(audios) == 1 and audios[0].get("codec_name") == "aac",
        "width_1920": video.get("width") == WIDTH,
        "height_1080": video.get("height") == HEIGHT,
        "fps_30": video.get("r_frame_rate") == "30/1",
        "frame_count_matches_manifest": int(video.get("nb_frames") or 0) == expected_total_frames,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Remotion 原始 MP4 校验失败：{checks}")
    return checks


def normalize_video(raw_video_path: Path, video_path: Path) -> None:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(raw_video_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-vf",
            "scale=in_range=pc:out_range=tv,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-color_range",
            "tv",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(video_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not video_path.is_file():
        raise RuntimeError(f"FFmpeg yuv420p 规范化失败：{completed.stderr.strip()[-1000:]}")


def scene_midpoint_frames(manifest: dict[str, Any]) -> list[int]:
    frames = []
    cursor = 0
    for scene in manifest["scenes"]:
        duration = int(scene["durationInFrames"])
        frames.append(cursor + duration // 2)
        cursor += duration
    return frames


def extract_frame_evidence(video_path: Path, output_dir: Path, manifest: dict[str, Any]) -> None:
    midpoints = scene_midpoint_frames(manifest)
    select_expression = "+".join(f"eq(n\\,{frame})" for frame in midpoints)
    contact = output_dir / OUTPUT_NAMES["contact_sheet"]
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"select='{select_expression}',scale=480:270,tile=4x3",
            "-frames:v",
            "1",
            str(contact),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not contact.is_file():
        raise RuntimeError(f"逐镜接触表生成失败：{completed.stderr.strip()[-500:]}")
    s03_frame = output_dir / OUTPUT_NAMES["s03_frame"]
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"select='eq(n\\,{midpoints[2]})'",
            "-frames:v",
            "1",
            str(s03_frame),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not s03_frame.is_file():
        raise RuntimeError(f"S03 中点帧生成失败：{completed.stderr.strip()[-500:]}")


def preflight(source_commit: str, output_dir: Path) -> dict[str, Any]:
    settings = get_settings()
    checks = {
        "source_commit_matches": _git("rev-parse", "HEAD") == source_commit,
        "working_tree_clean": not _git("status", "--porcelain"),
        "draft_hash_matches": sha256_bytes(DRAFT_PATH.read_bytes()) == EXPECTED_DRAFT_SHA256,
        "narration_hash_matches": sha256_text(narration_text(load_draft())) == EXPECTED_NARRATION_SHA256,
        "scene_count_12": len(load_draft()["scenes"]) == 12,
        "siliconflow_key_configured": bool(settings.siliconflow_api_key.strip()),
        "siliconflow_base_configured": bool(settings.siliconflow_base_url.strip()),
        "tts_model_locked": settings.video_tts_model == TTS_MODEL,
        "node_available": shutil.which("node") is not None,
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "ffprobe_available": shutil.which("ffprobe") is not None,
        "remotion_renderer_exists": RENDER_SCRIPT.is_file(),
        "remotion_dependencies_exist": (REMOTION_ROOT / "node_modules").is_dir(),
        "output_files_absent": not any((output_dir / name).exists() for name in OUTPUT_NAMES.values()),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "all_passed": not blockers,
        "blockers": blockers,
        "checks": checks,
        "source_commit": source_commit,
        "observed_commit": _git("rev-parse", "HEAD"),
        "draft_sha256": sha256_bytes(DRAFT_PATH.read_bytes()),
        "narration_sha256": sha256_text(narration_text(load_draft())),
        "tts": {
            "provider": "siliconflow",
            "model": TTS_MODEL,
            "voice": TTS_VOICE,
            "response_format": "mp3",
            "sample_rate": 32000,
            "speed": 1.0,
            "gain": 0.0,
            "automatic_retry": False,
        },
    }


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")


def _tts_snapshot() -> dict[str, Any]:
    return {
        "provider": "siliconflow",
        "model": TTS_MODEL,
        "voice": TTS_VOICE,
        "response_format": "mp3",
        "sample_rate": 32000,
        "speed": 1.0,
        "gain": 0.0,
        "automatic_retry": False,
    }


def build_report(
    *,
    source_commit: str,
    raw_render_source_commit: str,
    audio_path: Path,
    manifest_path: Path,
    raw_video_path: Path,
    video_path: Path,
    manifest: dict[str, Any],
    audio_probe: dict[str, Any],
    raw_probe: dict[str, Any],
    video_probe: dict[str, Any],
    raw_checks: dict[str, Any],
    media_checks: dict[str, Any],
    renderer_result: dict[str, Any],
    audio_content_type: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_kind": "paynes_creek_deterministic_vector_local_pilot",
        "status": "rendered_awaiting_visual_review",
        "source_git_commit": source_commit,
        "raw_render_source_git_commit": raw_render_source_commit,
        "publication_authorized": False,
        "source": {
            "draft": _relative(DRAFT_PATH),
            "draft_sha256": EXPECTED_DRAFT_SHA256,
            "narration_sha256": EXPECTED_NARRATION_SHA256,
            "scene_count": 12,
        },
        "calls": {
            "siliconflow_tts": 1,
            "image_provider": 0,
            "vision_provider": 0,
            "video_generation_provider": 0,
            "remotion_local_render": 1,
            "ffmpeg_color_normalization": 1,
            "publish": 0,
            "automatic_retry": 0,
        },
        "tts": {
            **_tts_snapshot(),
            "content_type": audio_content_type,
            "audio": _relative(audio_path),
            "audio_sha256": sha256_bytes(audio_path.read_bytes()),
            "audio_bytes": audio_path.stat().st_size,
            "audio_duration_ms": media_duration_ms(audio_probe),
            "probe": audio_probe,
        },
        "render": {
            "template_id": TEMPLATE_ID,
            "renderer_result": renderer_result,
            "manifest": _relative(manifest_path),
            "manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
            "raw_video": _relative(raw_video_path),
            "raw_video_sha256": sha256_bytes(raw_video_path.read_bytes()),
            "raw_video_bytes": raw_video_path.stat().st_size,
            "raw_probe": raw_probe,
            "raw_checks": raw_checks,
            "normalization": {
                "filter": "scale=in_range=pc:out_range=tv,format=yuv420p",
                "video_codec": "libx264",
                "preset": "medium",
                "crf": 18,
                "color_range": "tv",
                "audio_codec": "copy",
                "overwrite": False,
            },
            "video": _relative(video_path),
            "video_sha256": sha256_bytes(video_path.read_bytes()),
            "video_bytes": video_path.stat().st_size,
            "video_container_duration_ms": media_duration_ms(video_probe),
            "video_stream_duration_ms": stream_duration_ms(video_stream(video_probe)),
            "probe": video_probe,
            "checks": media_checks,
        },
        "frame_evidence": {
            "contact_sheet": _relative(video_path.parent / OUTPUT_NAMES["contact_sheet"]),
            "s03_midpoint": _relative(video_path.parent / OUTPUT_NAMES["s03_frame"]),
            "scene_midpoint_frames": scene_midpoint_frames(manifest),
            "visual_review": "not_reviewed",
        },
        "decision": {
            "status": "rendered_awaiting_visual_review",
            "local_video_ready": False,
            "publication_authorized": False,
        },
        "sensitive_values_removed": True,
    }


def finalize_existing(
    *,
    source_commit: str,
    raw_render_source_commit: str,
    output_dir: Path,
    expected_audio_sha256: str,
    expected_manifest_sha256: str,
    expected_raw_video_sha256: str,
) -> dict[str, Any]:
    if _git("rev-parse", "HEAD") != source_commit:
        raise RuntimeError("规范化源码 commit 与当前 HEAD 不一致")
    if _git("status", "--porcelain"):
        raise RuntimeError("规范化前工作树必须干净")
    audio_path = output_dir / OUTPUT_NAMES["audio"]
    manifest_path = output_dir / OUTPUT_NAMES["manifest"]
    raw_video_path = output_dir / OUTPUT_NAMES["raw_video"]
    video_path = output_dir / OUTPUT_NAMES["video"]
    report_path = output_dir / OUTPUT_NAMES["report"]
    contact_path = output_dir / OUTPUT_NAMES["contact_sheet"]
    s03_path = output_dir / OUTPUT_NAMES["s03_frame"]
    required = (audio_path, manifest_path, raw_video_path)
    if not all(path.is_file() and path.stat().st_size > 0 for path in required):
        raise RuntimeError("规范化缺少已观测的音频、Manifest 或 Remotion 原始 MP4")
    if any(path.exists() for path in (video_path, report_path, contact_path, s03_path)):
        raise RuntimeError("规范化目标或证据文件已存在，拒绝覆盖")
    observed_hashes = {
        "audio": sha256_bytes(audio_path.read_bytes()),
        "manifest": sha256_bytes(manifest_path.read_bytes()),
        "raw_video": sha256_bytes(raw_video_path.read_bytes()),
    }
    expected_hashes = {
        "audio": expected_audio_sha256,
        "manifest": expected_manifest_sha256,
        "raw_video": expected_raw_video_sha256,
    }
    if observed_hashes != expected_hashes:
        raise RuntimeError(f"规范化输入 hash 漂移：observed={observed_hashes}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("templateId") != TEMPLATE_ID
        or manifest.get("sourceDraftSha256") != EXPECTED_DRAFT_SHA256
        or manifest.get("narrationSha256") != EXPECTED_NARRATION_SHA256
        or manifest.get("publicationAuthorized") is not False
        or len(manifest.get("scenes", [])) != 12
    ):
        raise RuntimeError("规范化 Manifest 与冻结生产输入不一致")
    if manifest.get("audioSha256") != observed_hashes["audio"]:
        raise RuntimeError("Manifest 音频 hash 与已生成音频不一致")
    audio_probe = ffprobe(audio_path)
    raw_probe = ffprobe(raw_video_path)
    raw_checks = validate_raw_video_probe(
        raw_probe,
        expected_total_frames=int(manifest["totalFrames"]),
    )
    normalize_video(raw_video_path, video_path)
    video_probe = ffprobe(video_path)
    media_checks = validate_video_probe(
        video_probe,
        source_audio_duration_ms=int(manifest["audioDurationMs"]),
        expected_total_frames=int(manifest["totalFrames"]),
    )
    extract_frame_evidence(video_path, output_dir, manifest)
    package = json.loads((REMOTION_ROOT / "node_modules/remotion/package.json").read_text(encoding="utf-8"))
    renderer_result = {
        "status": "succeeded",
        "templateId": TEMPLATE_ID,
        "rendererVersion": package["version"],
        "durationInFrames": manifest["totalFrames"],
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "evidence_source": "existing_immutable_raw_mp4",
    }
    report = build_report(
        source_commit=source_commit,
        raw_render_source_commit=raw_render_source_commit,
        audio_path=audio_path,
        manifest_path=manifest_path,
        raw_video_path=raw_video_path,
        video_path=video_path,
        manifest=manifest,
        audio_probe=audio_probe,
        raw_probe=raw_probe,
        video_probe=video_probe,
        raw_checks=raw_checks,
        media_checks=media_checks,
        renderer_result=renderer_result,
        audio_content_type="audio/mpeg",
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def execute(source_commit: str, output_dir: Path) -> dict[str, Any]:
    initial = preflight(source_commit, output_dir)
    if not initial["all_passed"]:
        raise RuntimeError(f"Sprint 198 preflight 未通过：{initial['blockers']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    draft = load_draft()
    narration = narration_text(draft)
    audio_path = output_dir / OUTPUT_NAMES["audio"]
    client = SiliconFlowVoiceClient()
    audio_content, content_type = client.generate_speech(
        text=narration,
        voice_uri=TTS_VOICE,
        model=TTS_MODEL,
        response_format="mp3",
        sample_rate=32000,
        speed=1.0,
        gain=0.0,
        timeout=get_settings().video_tts_timeout_seconds,
    )
    if not audio_content:
        raise RuntimeError("SiliconFlow TTS 返回空音频")
    audio_path.write_bytes(audio_content)
    audio_probe = ffprobe(audio_path)
    audio_duration_ms = media_duration_ms(audio_probe)
    manifest = build_manifest(
        draft=draft,
        audio_path=audio_path,
        audio_duration_ms=audio_duration_ms,
        audio_sha256=sha256_bytes(audio_content),
    )
    manifest_path = output_dir / OUTPUT_NAMES["manifest"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raw_video_path = output_dir / OUTPUT_NAMES["raw_video"]
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
        raise RuntimeError(f"Remotion 渲染失败：{(completed.stderr or completed.stdout).strip()[-2000:]}")
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
        raise RuntimeError("Remotion 成功退出但没有返回结构化成功结果")
    if not raw_video_path.is_file() or raw_video_path.stat().st_size <= 0:
        raise RuntimeError("Remotion 没有生成非空 MP4")
    raw_probe = ffprobe(raw_video_path)
    raw_checks = validate_raw_video_probe(
        raw_probe,
        expected_total_frames=int(manifest["totalFrames"]),
    )
    video_path = output_dir / OUTPUT_NAMES["video"]
    normalize_video(raw_video_path, video_path)
    video_probe = ffprobe(video_path)
    media_checks = validate_video_probe(
        video_probe,
        source_audio_duration_ms=audio_duration_ms,
        expected_total_frames=int(manifest["totalFrames"]),
    )
    extract_frame_evidence(video_path, output_dir, manifest)
    report = build_report(
        source_commit=source_commit,
        raw_render_source_commit=source_commit,
        audio_path=audio_path,
        manifest_path=manifest_path,
        raw_video_path=raw_video_path,
        video_path=video_path,
        manifest=manifest,
        audio_probe=audio_probe,
        raw_probe=raw_probe,
        video_probe=video_probe,
        raw_checks=raw_checks,
        media_checks=media_checks,
        renderer_result=renderer_result,
        audio_content_type=content_type,
    )
    report_path = output_dir / OUTPUT_NAMES["report"]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the deterministic Paynes Creek local pilot")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--execute", action="store_true")
    action.add_argument("--finalize-existing", action="store_true")
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument("--raw-render-source-git-commit")
    parser.add_argument("--expected-audio-sha256")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--expected-raw-video-sha256")
    parser.add_argument(
        "--output-dir",
        default="storage/exports/paynes-creek/vector-pilot-v1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = (PROJECT_ROOT / args.output_dir).resolve()
    if args.preflight:
        result = preflight(args.source_git_commit, output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["all_passed"] else 2
    if args.finalize_existing:
        required = {
            "raw_render_source_git_commit": args.raw_render_source_git_commit,
            "expected_audio_sha256": args.expected_audio_sha256,
            "expected_manifest_sha256": args.expected_manifest_sha256,
            "expected_raw_video_sha256": args.expected_raw_video_sha256,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"--finalize-existing 缺少参数：{missing}")
        result = finalize_existing(
            source_commit=args.source_git_commit,
            raw_render_source_commit=args.raw_render_source_git_commit,
            output_dir=output_dir,
            expected_audio_sha256=args.expected_audio_sha256,
            expected_manifest_sha256=args.expected_manifest_sha256,
            expected_raw_video_sha256=args.expected_raw_video_sha256,
        )
    else:
        result = execute(args.source_git_commit, output_dir)
    print(
        json.dumps(
            {
                "status": result["status"],
                "video": result["render"]["video"],
                "video_sha256": result["render"]["video_sha256"],
                "duration_ms": result["render"]["video_container_duration_ms"],
                "tts_calls": result["calls"]["siliconflow_tts"],
                "render_calls": result["calls"]["remotion_local_render"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
