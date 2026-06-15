#!/usr/bin/env python3
"""Summarize douyin-downloader search and download outputs for sample research."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Sample:
    aweme_id: str
    title: str
    author_name: str
    publish_date: str
    media_type: str
    image_count: int
    digg_count: int | None
    comment_count: int | None
    collect_count: int | None
    share_count: int | None
    tags: list[str]
    source: str


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            yield item


def title_from_desc(desc: Any) -> str:
    text = str(desc or "").strip()
    if not text:
        return ""
    return text.split("#", 1)[0].strip()


def tags_from_item(item: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    raw_tags = item.get("tags")
    if isinstance(raw_tags, list):
        tags.extend(str(tag) for tag in raw_tags if tag)
    for extra in item.get("text_extra") or []:
        if isinstance(extra, dict) and extra.get("hashtag_name"):
            tags.append(str(extra["hashtag_name"]))
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def date_from_ts(value: Any) -> str:
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d")


def media_type_from_item(item: dict[str, Any]) -> str:
    media_type = item.get("media_type")
    if media_type in (2, 68, 150, "2", "68", "150"):
        return "gallery"
    if media_type:
        return str(media_type)
    aweme_type = item.get("aweme_type")
    if aweme_type in (2, 68, 150) or item.get("images") or item.get("image_post_info"):
        return "gallery"
    if item.get("video"):
        return "video"
    return "unknown"


def image_count_from_item(item: dict[str, Any]) -> int:
    images = item.get("images")
    if isinstance(images, list):
        return len(images)
    image_post = item.get("image_post_info")
    if isinstance(image_post, dict):
        image_list = image_post.get("images")
        if isinstance(image_list, list):
            return len(image_list)
    file_names = item.get("file_names")
    if isinstance(file_names, list):
        return sum(1 for name in file_names if str(name).lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    return 0


def sample_from_item(item: dict[str, Any], source: Path) -> Sample | None:
    aweme_id = str(item.get("aweme_id") or "").strip()
    if not aweme_id:
        return None
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    stats = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    author_name = item.get("author_name") or author.get("nickname") or ""
    create_time = item.get("create_time") or item.get("publish_timestamp")
    return Sample(
        aweme_id=aweme_id,
        title=title_from_desc(item.get("desc")),
        author_name=str(author_name or ""),
        publish_date=date_from_ts(create_time),
        media_type=media_type_from_item(item),
        image_count=image_count_from_item(item),
        digg_count=int(stats["digg_count"]) if "digg_count" in stats else None,
        comment_count=int(stats["comment_count"]) if "comment_count" in stats else None,
        collect_count=int(stats["collect_count"]) if "collect_count" in stats else None,
        share_count=int(stats["share_count"]) if "share_count" in stats else None,
        tags=tags_from_item(item),
        source=str(source),
    )


def collect_samples(root: Path, data_roots: list[Path]) -> list[Sample]:
    samples: dict[str, Sample] = {}
    paths: list[Path] = []
    paths.extend(sorted(root.glob("Downloaded/search/*.jsonl")))
    paths.extend(sorted(root.rglob("*_data.json")))
    for data_root in data_roots:
        paths.extend(sorted(data_root.rglob("search/*.jsonl")))
        paths.extend(sorted(data_root.rglob("*_data.json")))

    for path in paths:
        if path.suffix == ".jsonl":
            for item in iter_jsonl(path):
                sample = sample_from_item(item, path)
                if sample and sample.aweme_id not in samples:
                    samples[sample.aweme_id] = sample
        else:
            sample = sample_from_item(load_json(path), path)
            if sample:
                samples[sample.aweme_id] = sample
    return sorted(
        samples.values(),
        key=lambda s: ((s.publish_date or ""), s.digg_count or 0, s.comment_count or 0),
        reverse=True,
    )


def render_markdown(samples: list[Sample], limit: int) -> str:
    rows = samples[:limit]
    lines = [
        "| date | aweme_id | title | author | media | images | digg | comments | collects | shares | tags | source |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for s in rows:
        title = s.title.replace("|", " ")
        tags = ",".join(s.tags).replace("|", " ")
        lines.append(
            f"| {s.publish_date} | {s.aweme_id} | {title} | {s.author_name} | "
            f"{s.media_type} | {s.image_count} | {s.digg_count or ''} | "
            f"{s.comment_count or ''} | {s.collect_count or ''} | {s.share_count or ''} | "
            f"{tags} | `{s.source}` |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloader-root", type=Path, default=Path("../douyin-downloader"))
    parser.add_argument(
        "--data-root",
        action="append",
        type=Path,
        default=[],
        help="Additional directory to scan for search JSONL and *_data.json files.",
    )
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    root = args.downloader_root.expanduser().resolve()
    data_roots = [path.expanduser().resolve() for path in args.data_root]
    samples = collect_samples(root, data_roots)
    if args.format == "json":
        print(json.dumps([asdict(s) for s in samples[: args.limit]], ensure_ascii=False, indent=2))
    else:
        print(render_markdown(samples, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
