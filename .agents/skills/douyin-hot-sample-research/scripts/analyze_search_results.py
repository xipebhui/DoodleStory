#!/usr/bin/env python3
"""Analyze Douyin search outputs into a candidate shortlist."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def parse_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or text.lower() == "none":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} is not valid JSONL: {exc}") from exc
    return rows


def split_csv_urls(value: Any) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def extract_hashtags(text: str) -> list[str]:
    tags: list[str] = []
    for part in text.replace("\n", " ").split("#")[1:]:
        tag = part.strip().split(" ")[0].strip(" #，,。.!！?？")
        if tag:
            tags.append(tag)
    return tags


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def freshness_bucket(create_time: int, now_ts: int) -> str:
    if create_time <= 0:
        return "unknown"
    age_days = max(0.0, (now_ts - create_time) / 86400)
    if age_days <= 1:
        return "1d"
    if age_days <= 3:
        return "3d"
    if age_days <= 7:
        return "7d"
    if age_days <= 30:
        return "30d"
    return "old"


def log_score(value: int, weight: float) -> float:
    return math.log10(max(value, 0) + 1) * weight


@dataclass
class CommentSummary:
    count: int = 0
    total_likes: int = 0
    top_comments: list[dict[str, Any]] | None = None


def summarize_comments(comment_rows: Iterable[dict[str, Any]]) -> dict[str, CommentSummary]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comment_rows:
        aweme_id = str(row.get("aweme_id") or "")
        if aweme_id:
            grouped[aweme_id].append(row)

    summaries: dict[str, CommentSummary] = {}
    for aweme_id, rows in grouped.items():
        sorted_rows = sorted(rows, key=lambda item: parse_int(item.get("like_count")), reverse=True)
        summaries[aweme_id] = CommentSummary(
            count=len(rows),
            total_likes=sum(parse_int(item.get("like_count")) for item in rows),
            top_comments=[
                {
                    "content": item.get("content", ""),
                    "like_count": parse_int(item.get("like_count")),
                    "sub_comment_count": parse_int(item.get("sub_comment_count")),
                }
                for item in sorted_rows[:3]
            ],
        )
    return summaries


def classify(row: dict[str, Any], comment_summary: CommentSummary | None, now_ts: int) -> dict[str, Any]:
    aweme_id = str(row.get("aweme_id") or "")
    title = str(row.get("title") or row.get("desc") or "").replace("\n", " ").strip()
    liked = parse_int(row.get("liked_count"))
    collected = parse_int(row.get("collected_count"))
    comments = parse_int(row.get("comment_count"))
    shares = parse_int(row.get("share_count"))
    create_time = parse_int(row.get("create_time"))
    note_urls = split_csv_urls(row.get("note_download_url"))
    is_image_text = str(row.get("aweme_type")) == "68" or bool(note_urls)
    bucket = freshness_bucket(create_time, now_ts)
    tags = extract_hashtags(title)

    share_rate = safe_rate(shares, liked)
    collect_rate = safe_rate(collected, liked)
    comment_rate = safe_rate(comments, liked)
    score = (
        log_score(liked, 18.0)
        + log_score(comments, 10.0)
        + log_score(shares, 12.0)
        + log_score(collected, 8.0)
        + (15.0 if is_image_text else -20.0)
        + (10.0 if bucket in {"1d", "3d", "7d"} else 0.0)
        + min(share_rate * 100, 15.0)
        + min(collect_rate * 100, 10.0)
        + min(comment_rate * 100, 10.0)
    )

    comment_count_collected = comment_summary.count if comment_summary else 0
    strong_signal = liked >= 50000 or shares >= 20000 or comments >= 3000 or share_rate >= 2.0
    promising_signal = liked >= 10000 or shares >= 1000 or comments >= 500 or share_rate >= 0.3

    if not is_image_text:
        grade = "D"
        reason = "not_image_text"
    elif bucket not in {"1d", "3d", "7d"}:
        grade = "C"
        reason = "not_recent"
    elif strong_signal:
        grade = "A"
        reason = "recent_image_text_high_signal"
    elif promising_signal:
        grade = "B"
        reason = "recent_image_text_promising"
    else:
        grade = "C"
        reason = "recent_image_text_low_signal"

    return {
        "grade": grade,
        "reason": reason,
        "score": round(score, 2),
        "aweme_id": aweme_id,
        "media_type": "image_text" if is_image_text else "video_or_other",
        "title": title,
        "nickname": row.get("nickname", ""),
        "create_time": create_time,
        "create_date": datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S") if create_time else "",
        "freshness_bucket": bucket,
        "liked_count": liked,
        "collected_count": collected,
        "comment_count": comments,
        "share_count": shares,
        "share_rate": round(share_rate, 4),
        "collect_rate": round(collect_rate, 4),
        "comment_rate": round(comment_rate, 4),
        "image_count": len(note_urls),
        "tags": ",".join(tags),
        "aweme_url": row.get("aweme_url", ""),
        "cover_url": row.get("cover_url", ""),
        "note_download_url": row.get("note_download_url", ""),
        "comment_collected_count": comment_count_collected,
        "comment_top_likes": comment_summary.total_likes if comment_summary else 0,
        "comment_status": "collected" if comment_summary else "comment_not_collected",
        "top_comments": json.dumps(comment_summary.top_comments or [], ensure_ascii=False) if comment_summary else "[]",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]], content_path: Path, comments_path: Path | None) -> None:
    grade_counts = Counter(row["grade"] for row in rows)
    lines = [
        "# Douyin Hot Sample Analysis",
        "",
        f"- content_source: `{content_path}`",
        f"- comments_source: `{comments_path}`" if comments_path else "- comments_source: not provided",
        f"- total_candidates: {len(rows)}",
        f"- grade_counts: {dict(sorted(grade_counts.items()))}",
        "",
        "## Top Candidates",
        "",
        "| grade | score | aweme_id | metrics | freshness | title | comment_status |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in rows[:20]:
        metrics = (
            f"赞{row['liked_count']} / 评{row['comment_count']} / "
            f"藏{row['collected_count']} / 转{row['share_count']}"
        )
        title = str(row["title"]).replace("|", "\\|")[:80]
        lines.append(
            f"| {row['grade']} | {row['score']} | {row['aweme_id']} | {metrics} | "
            f"{row['freshness_bucket']} | {title} | {row['comment_status']} |"
        )
    lines.extend(
        [
            "",
            "## Next Actions",
            "",
            "- A: download media, run preview_vl on first/last pages, then promote selected samples to full_story_document.",
            "- B: inspect titles, tags, and comments before deciding whether to download.",
            "- C/D: keep as reference or reject unless a specific structure is needed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze MediaCrawler Douyin search outputs.")
    parser.add_argument("--contents", required=True, type=Path, help="MediaCrawler search_contents JSONL path")
    parser.add_argument("--comments", type=Path, help="Optional MediaCrawler search_comments JSONL path")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--now-ts", type=int, default=int(datetime.now(timezone.utc).timestamp()))
    args = parser.parse_args()

    content_rows = load_jsonl(args.contents)
    comment_rows = load_jsonl(args.comments) if args.comments else []
    comment_summaries = summarize_comments(comment_rows)

    analyzed = [classify(row, comment_summaries.get(str(row.get("aweme_id"))), args.now_ts) for row in content_rows]
    analyzed.sort(key=lambda item: (item["grade"], -item["score"], -item["share_count"]))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "candidate_scores.csv", analyzed)
    (args.out_dir / "candidate_scores.json").write_text(
        json.dumps(analyzed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(args.out_dir / "analysis_report.md", analyzed, args.contents, args.comments)
    print(json.dumps({
        "contents": str(args.contents),
        "comments": str(args.comments) if args.comments else None,
        "out_dir": str(args.out_dir),
        "total_candidates": len(analyzed),
        "grade_counts": dict(sorted(Counter(row["grade"] for row in analyzed).items())),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
