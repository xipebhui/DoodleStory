from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import (  # noqa: E402
    FileAsset,
    NativeAgentVideo,
    PublishableVideo,
    YoutubeChannel,
    YoutubePublishTask,
)
from app.models.enums import FileAssetPurpose  # noqa: E402
from app.services.reviewed_local_video_publication import (  # noqa: E402
    ReviewedLocalVideoPublicationError,
    load_reviewed_video_facts,
    publication_result,
    rank_normal_channels,
    refresh_publication,
    register_reviewed_video,
    require_import_skill_version,
    require_single_admin,
    submit_publication,
    upsert_target_channel,
)
from app.services.youtube_publisher import YoutubePublisherClient  # noqa: E402


ACCEPTANCE_PATH = PROJECT_ROOT / (
    "docs/testing/paynes-creek-maya-salt-publish-en-v2-2026-08-14.json"
)
VIDEO_PATH = PROJECT_ROOT / (
    "storage/exports/paynes-creek/maya-salt-publish-en-v2/"
    "paynes-creek-maya-salt-publish-en-v2-yuv420p.mp4"
)
REPORT_PATH = PROJECT_ROOT / (
    "docs/testing/paynes-creek-maya-salt-youtube-publication-2026-08-15.json"
)
TARGET_CHANNEL_ID = "UCjOzKTQ7NzrNtkBbBYoCX_w"
TARGET_CHANNEL_TITLE = "Strandburg Behler"
TITLE = "No Shipping Records: How Did Maya Salt Travel Inland?"
DESCRIPTION = """How did Maya salt move from coastal workshops to inland communities when no shipping records survive?

This short follows archaeological clues from Paynes Creek: concentrating brine, boiling it in clay basins, crystallizing salt, and a full-size wooden paddle that points to canoe transport. The process can be reconstructed, but the exact route, buyer, and shipment remain unknown.

#Maya #Archaeology #AncientHistory"""
TAGS = [
    "Maya civilization",
    "archaeology",
    "Paynes Creek",
    "ancient salt",
    "ancient trade",
    "Belize",
    "Maya history",
    "ancient history",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import and publish the Sprint 203 reviewed Paynes Creek video."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--execute", action="store_true")
    action.add_argument("--refresh", action="store_true")
    parser.add_argument("--source-git-commit")
    return parser.parse_args()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise ReviewedLocalVideoPublicationError(
            f"Git 命令失败：{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def require_frozen_source(source_git_commit: str | None) -> str:
    if not source_git_commit:
        raise ReviewedLocalVideoPublicationError("必须提供 --source-git-commit")
    head = git("rev-parse", "HEAD")
    if head != source_git_commit:
        raise ReviewedLocalVideoPublicationError("--source-git-commit 与 HEAD 不一致")
    if git("status", "--porcelain"):
        raise ReviewedLocalVideoPublicationError("真实执行前 worktree 必须干净")
    return head


def current_local_state(checksum_sha256: str) -> dict[str, Any]:
    with SessionLocal() as db:
        owner = require_single_admin(db)
        skill = require_import_skill_version(db)
        asset = db.scalar(
            select(FileAsset).where(
                FileAsset.purpose == FileAssetPurpose.generated_video,
                FileAsset.checksum_sha256 == checksum_sha256,
            )
        )
        video = (
            db.scalar(
                select(NativeAgentVideo).where(NativeAgentVideo.asset_id == asset.id)
            )
            if asset is not None
            else None
        )
        publishable = (
            db.scalar(
                select(PublishableVideo).where(
                    PublishableVideo.source_native_agent_video_id == video.id
                )
            )
            if video is not None
            else None
        )
        channel = db.scalar(
            select(YoutubeChannel).where(
                YoutubeChannel.channel_id == TARGET_CHANNEL_ID
            )
        )
        task = (
            db.scalar(
                select(YoutubePublishTask).where(
                    YoutubePublishTask.channel_id == channel.id,
                    YoutubePublishTask.publishable_video_id == publishable.id,
                )
            )
            if channel is not None and publishable is not None
            else None
        )
        return {
            "owner_user_id": owner.id,
            "skill_version_id": skill.id,
            "asset_id": asset.id if asset else None,
            "native_agent_video_id": video.id if video else None,
            "publishable_video_id": publishable.id if publishable else None,
            "channel_pk": channel.id if channel else None,
            "publish_task_id": task.id if task else None,
            "remote_task_id": task.remote_task_id if task else None,
            "task_status": task.status if task else None,
        }


def preflight(source_git_commit: str | None, *, require_clean: bool) -> dict[str, Any]:
    source_commit = (
        require_frozen_source(source_git_commit)
        if require_clean
        else git("rev-parse", "HEAD")
    )
    facts = load_reviewed_video_facts(
        PROJECT_ROOT,
        acceptance_path=ACCEPTANCE_PATH,
        video_path=VIDEO_PATH,
    )
    client = YoutubePublisherClient()
    ranked = rank_normal_channels(client)
    selected = ranked[0]
    if selected.channel_id != TARGET_CHANNEL_ID or selected.title != TARGET_CHANNEL_TITLE:
        raise ReviewedLocalVideoPublicationError(
            "远端最少发布频道已变化，拒绝使用冻结目标"
        )
    local_state = current_local_state(facts.checksum_sha256)
    return {
        "schema_version": 1,
        "status": "pass",
        "source_git_commit": source_commit,
        "video": asdict(facts),
        "channel_selection": {
            "rule": "normal_then_published_count_then_channel_id",
            "selected": {
                "channel_id": selected.channel_id,
                "title": selected.title,
                "status": selected.status,
                "published_video_count": selected.published_video_count,
            },
            "runner_up": {
                "channel_id": ranked[1].channel_id,
                "title": ranked[1].title,
                "published_video_count": ranked[1].published_video_count,
            },
            "normal_channel_count": len(ranked),
        },
        "publication": {
            "title": TITLE,
            "visibility": "public",
            "contains_synthetic_media": True,
            "notify_subscribers": False,
            "made_for_kids": False,
            "paid_product_placement": False,
            "thumbnail_url": None,
        },
        "local_state": local_state,
    }


def write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def execute(source_git_commit: str | None) -> dict[str, Any]:
    frozen = preflight(source_git_commit, require_clean=True)
    facts = load_reviewed_video_facts(
        PROJECT_ROOT,
        acceptance_path=ACCEPTANCE_PATH,
        video_path=VIDEO_PATH,
    )
    client = YoutubePublisherClient()
    selected = rank_normal_channels(client)[0]
    if selected.channel_id != TARGET_CHANNEL_ID or selected.title != TARGET_CHANNEL_TITLE:
        raise ReviewedLocalVideoPublicationError(
            "远端最少发布频道在执行前发生变化，拒绝提交"
        )
    before = frozen["local_state"]
    with SessionLocal() as db:
        owner = require_single_admin(db)
        skill = require_import_skill_version(db)
        channel = upsert_target_channel(db, selected)
        asset, video, publishable = register_reviewed_video(
            db,
            owner=owner,
            skill_version=skill,
            facts=facts,
            video_path=VIDEO_PATH,
            source_git_commit=str(frozen["source_git_commit"]),
            title=TITLE,
            description=DESCRIPTION,
            tags=TAGS,
        )
        idempotency_key = (
            f"sprint-204:{facts.checksum_sha256[:24]}:{TARGET_CHANNEL_ID}"
        )
        task = submit_publication(
            db,
            owner=owner,
            channel=channel,
            publishable=publishable,
            idempotency_key=idempotency_key,
            client=client,
        )
        result = publication_result(
            asset=asset,
            video=video,
            publishable=publishable,
            channel=channel,
            task=task,
        )
    report = {
        **frozen,
        "status": result.status,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "result": asdict(result),
        "calls": {
            "object_storage_upload": 0 if before["asset_id"] else 1,
            "remote_publish_create": 0 if before["publish_task_id"] else 1,
            "remote_status_get": 0,
            "model": 0,
            "image": 0,
            "video_generation": 0,
            "tts": 0,
        },
        "sensitive_values_removed": True,
    }
    write_report(report)
    return report


def refresh() -> dict[str, Any]:
    if not REPORT_PATH.is_file():
        raise ReviewedLocalVideoPublicationError("执行报告不存在，不能刷新")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    result = report.get("result")
    if not isinstance(result, dict) or not result.get("publish_task_id"):
        raise ReviewedLocalVideoPublicationError("执行报告缺少本地发布任务 ID")
    task_id = str(result["publish_task_id"])
    previous_status = str(result.get("status") or "")
    terminal_statuses = {"succeeded", "failed", "cancelled", "outcome_unknown"}
    did_remote_status_get = previous_status not in terminal_statuses
    client = YoutubePublisherClient()
    with SessionLocal() as db:
        task = refresh_publication(db, task_id=task_id, client=client)
        asset = db.get(FileAsset, result["asset_id"])
        video = db.get(NativeAgentVideo, result["native_agent_video_id"])
        publishable = db.get(PublishableVideo, result["publishable_video_id"])
        channel = db.get(YoutubeChannel, result["channel_pk"])
        if any(item is None for item in (asset, video, publishable, channel)):
            raise ReviewedLocalVideoPublicationError("发布链路本地记录不完整")
        refreshed = publication_result(
            asset=asset,
            video=video,
            publishable=publishable,
            channel=channel,
            task=task,
        )
    report["result"] = asdict(refreshed)
    report["status"] = refreshed.status
    report["last_status_checked_at"] = datetime.now(timezone.utc).isoformat()
    report["calls"]["remote_status_get"] = int(
        report["calls"].get("remote_status_get") or 0
    ) + (1 if did_remote_status_get else 0)
    write_report(report)
    return report


def public_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "source_git_commit": report.get("source_git_commit"),
        "channel": report.get("channel_selection", {}).get("selected"),
        "result": report.get("result"),
        "report": REPORT_PATH.relative_to(PROJECT_ROOT).as_posix()
        if REPORT_PATH.exists()
        else None,
    }


def main() -> int:
    args = parse_args()
    try:
        if args.preflight:
            report = preflight(args.source_git_commit, require_clean=True)
        elif args.execute:
            report = execute(args.source_git_commit)
        else:
            report = refresh()
    except ReviewedLocalVideoPublicationError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(public_summary(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
