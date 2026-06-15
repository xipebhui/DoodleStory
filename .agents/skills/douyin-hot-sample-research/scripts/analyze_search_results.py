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


def deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        key = str(row.get("aweme_id") or row.get("aweme_id_str") or "").strip()
        if not key:
            key = f"row:{index}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


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


CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "family_marriage",
        (
            "家庭",
            "婆媳",
            "婚姻",
            "老公",
            "老婆",
            "媳妇",
            "妻子",
            "丈夫",
            "父母",
            "妈妈",
            "爸爸",
            "孩子",
            "亲情",
        ),
    ),
    (
        "social_safety",
        (
            "女性安全",
            "拒绝沉默",
            "伤害",
            "被伤害",
            "安全",
            "霸凌",
            "侵害",
            "受害",
        ),
    ),
    (
        "suspense_horror",
        (
            "恐怖",
            "悬疑",
            "惊悚",
            "案件",
            "诡异",
            "睡前故事",
            "怪谈",
            "真相",
            "秘密",
        ),
    ),
    (
        "revenge_moral",
        (
            "复仇",
            "反转",
            "打脸",
            "报应",
            "渣男",
            "背叛",
            "绿茶",
            "恶人",
            "善良",
            "选择",
        ),
    ),
    (
        "workplace_social",
        (
            "职场",
            "同事",
            "老板",
            "上司",
            "高情商",
            "社交",
            "人情世故",
            "发疯文学",
        ),
    ),
    (
        "pure_love_healing",
        (
            "纯爱",
            "治愈",
            "心动",
            "爱情",
            "恋爱",
            "暗恋",
            "异地恋",
            "校花",
            "情侣",
            "双向奔赴",
            "喜欢你",
            "婚纱",
        ),
    ),
    (
        "life_growth",
        (
            "人生",
            "焦虑",
            "成长",
            "考研",
            "上岸",
            "学习",
            "努力",
            "励志",
            "生活",
            "治愈系",
        ),
    ),
]


def infer_content_category(title: str, tags: list[str]) -> str:
    haystack = f"{title} {' '.join(tags)}"
    for category, keywords in CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category
    if "故事" in haystack:
        return "other_story"
    return "uncategorized"


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


def load_creator_profiles(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    rows = load_jsonl(path)
    profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in ("user_id", "sec_uid"):
            value = str(row.get(key) or "")
            if value:
                profiles[value] = row
    return profiles


def account_probe_priority(grade: str, sec_uid: str, liked: int, shares: int, comments: int) -> str:
    if not sec_uid:
        return "no_sec_uid"
    if grade == "A" or liked >= 50000 or shares >= 20000 or comments >= 3000:
        return "high"
    if grade == "B" or liked >= 10000 or shares >= 1000 or comments >= 500:
        return "medium"
    return "low"


def mimicability(
    *,
    grade: str,
    liked: int,
    shares: int,
    comments: int,
    creator_profile: dict[str, Any] | None,
) -> tuple[str, str, int, int, int]:
    if not creator_profile:
        return "needs_account_probe", "creator_profile_not_provided", 0, 0, 0

    videos_count = parse_int(creator_profile.get("videos_count"))
    fans = parse_int(creator_profile.get("fans"))
    total_favorited = parse_int(creator_profile.get("interaction"))
    strong_traffic = grade == "A" or liked >= 50000 or shares >= 20000 or comments >= 3000
    promising_traffic = grade in {"A", "B"} or liked >= 10000 or shares >= 1000 or comments >= 500

    if videos_count >= 300 or fans >= 100000:
        return "low_mimicability", "large_mature_account_penalty", videos_count, fans, total_favorited
    if videos_count and videos_count <= 50 and promising_traffic:
        return "high_mimicability", "few_works_high_traffic", videos_count, fans, total_favorited
    if videos_count and videos_count <= 150 and strong_traffic:
        return "medium_mimicability", "mid_work_count_high_traffic", videos_count, fans, total_favorited
    if promising_traffic:
        return "medium_mimicability", "traffic_strong_but_account_not_small", videos_count, fans, total_favorited
    return "low_mimicability", "weak_sample_traffic", videos_count, fans, total_favorited


def classify(
    row: dict[str, Any],
    comment_summary: CommentSummary | None,
    now_ts: int,
    creator_profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    aweme_id = str(row.get("aweme_id") or "")
    title = str(row.get("title") or row.get("desc") or "").replace("\n", " ").strip()
    sec_uid = str(row.get("sec_uid") or "")
    liked = parse_int(row.get("liked_count"))
    collected = parse_int(row.get("collected_count"))
    comments = parse_int(row.get("comment_count"))
    shares = parse_int(row.get("share_count"))
    create_time = parse_int(row.get("create_time"))
    note_urls = split_csv_urls(row.get("note_download_url"))
    is_image_text = str(row.get("aweme_type")) == "68" or bool(note_urls)
    bucket = freshness_bucket(create_time, now_ts)
    tags = extract_hashtags(title)
    category = infer_content_category(title, tags)

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
    high_ratio_sample = liked >= 1000 and share_rate >= 2.0
    promising_ratio_sample = liked >= 1000 and share_rate >= 0.3
    strong_signal = liked >= 50000 or shares >= 20000 or comments >= 3000 or high_ratio_sample
    promising_signal = liked >= 10000 or shares >= 1000 or comments >= 500 or promising_ratio_sample

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

    creator_profile = creator_profiles.get(sec_uid)
    mimic_label, mimic_reason, creator_videos_count, creator_fans, creator_total_favorited = mimicability(
        grade=grade,
        liked=liked,
        shares=shares,
        comments=comments,
        creator_profile=creator_profile,
    )

    return {
        "grade": grade,
        "reason": reason,
        "score": round(score, 2),
        "content_category": category,
        "aweme_id": aweme_id,
        "media_type": "image_text" if is_image_text else "video_or_other",
        "title": title,
        "nickname": row.get("nickname", ""),
        "author_sec_uid": sec_uid,
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
        "account_probe_priority": account_probe_priority(grade, sec_uid, liked, shares, comments),
        "creator_videos_count": creator_videos_count,
        "creator_fans": creator_fans,
        "creator_total_favorited": creator_total_favorited,
        "mimicability_label": mimic_label,
        "mimicability_reason": mimic_reason,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize_categories(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("content_category") or "uncategorized")].append(row)

    summaries: list[dict[str, Any]] = []
    for category, items in grouped.items():
        liked_values = sorted(parse_int(item.get("liked_count")) for item in items)
        score_values = [float(item.get("score") or 0.0) for item in items]
        grade_counts = Counter(str(item.get("grade")) for item in items)
        top_items = sorted(items, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:3]
        median_likes = liked_values[len(liked_values) // 2] if liked_values else 0
        summaries.append(
            {
                "content_category": category,
                "candidate_count": len(items),
                "ab_count": grade_counts.get("A", 0) + grade_counts.get("B", 0),
                "a_count": grade_counts.get("A", 0),
                "b_count": grade_counts.get("B", 0),
                "total_likes": sum(parse_int(item.get("liked_count")) for item in items),
                "median_likes": median_likes,
                "total_comments": sum(parse_int(item.get("comment_count")) for item in items),
                "total_shares": sum(parse_int(item.get("share_count")) for item in items),
                "avg_score": round(sum(score_values) / len(score_values), 2) if score_values else 0.0,
                "top_aweme_ids": ",".join(str(item.get("aweme_id") or "") for item in top_items),
                "top_titles": " | ".join(str(item.get("title") or "")[:40] for item in top_items),
            }
        )
    summaries.sort(
        key=lambda item: (
            -parse_int(item["ab_count"]),
            -parse_int(item["total_shares"]),
            -parse_int(item["total_likes"]),
        )
    )
    return summaries


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    content_path: Path,
    comments_path: Path | None,
    creators_path: Path | None,
) -> None:
    grade_counts = Counter(row["grade"] for row in rows)
    lines = [
        "# 抖音热门样本分析",
        "",
        f"- content_source: `{content_path}`",
        f"- comments_source: `{comments_path}`" if comments_path else "- comments_source: not provided",
        f"- creators_source: `{creators_path}`" if creators_path else "- creators_source: not provided",
        f"- total_candidates: {len(rows)}",
        f"- grade_counts: {dict(sorted(grade_counts.items()))}",
        "",
        "## 类目横向对比",
        "",
        "| category | candidates | A/B | likes | comments | shares | avg_score | top_titles |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in category_rows:
        titles = str(row["top_titles"]).replace("|", "\\|")[:120]
        lines.append(
            f"| {row['content_category']} | {row['candidate_count']} | {row['ab_count']} | "
            f"{row['total_likes']} | {row['total_comments']} | {row['total_shares']} | "
            f"{row['avg_score']} | {titles} |"
        )
    lines.extend(
        [
            "",
            "## 候选样本",
        "",
            "| grade | score | category | aweme_id | metrics | freshness | account | title | comment_status |",
            "|---|---:|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows[:20]:
        metrics = (
            f"赞{row['liked_count']} / 评{row['comment_count']} / "
            f"藏{row['collected_count']} / 转{row['share_count']}"
        )
        title = str(row["title"]).replace("|", "\\|")[:80]
        account = f"{row['account_probe_priority']} / {row['mimicability_label']}"
        lines.append(
            f"| {row['grade']} | {row['score']} | {row['content_category']} | {row['aweme_id']} | "
            f"{metrics} | {row['freshness_bucket']} | {account} | {title} | {row['comment_status']} |"
        )
    lines.extend(
        [
            "",
            "## 最近 7 天处理说明",
            "",
            "- 先做类目横向对比。多个 A/B 样本支撑的类目，比单个孤立爆款更可靠。",
            "- 优先探测账号优先级为 `high` 的样本。账号作品数和粉丝数越大，越可能依赖账号积累，模仿难度应降低评分。",
            "- 真人照片或证据式结尾应记录为可复用的真实感机制，不直接复制原素材。",
            "",
            "## 下一步",
            "",
            "- A：下载或读取媒体，先做首尾页 `preview_vl`，进入生成前必须对被选中的源样本做 `full_story_document`。",
            "- B：先看标题、标签、评论，再决定是否下载和全量 VL。",
            "- C/D：仅作为结构参考或拒绝，除非有明确需要的机制。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze MediaCrawler Douyin search outputs.")
    parser.add_argument("--contents", required=True, type=Path, help="MediaCrawler search_contents JSONL path")
    parser.add_argument("--comments", type=Path, help="Optional MediaCrawler search_comments JSONL path")
    parser.add_argument("--creators", type=Path, help="Optional MediaCrawler creator_creators JSONL path")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--now-ts", type=int, default=int(datetime.now(timezone.utc).timestamp()))
    parser.add_argument("--no-dedup", action="store_true", help="Keep duplicate aweme rows instead of deduplicating by aweme_id")
    args = parser.parse_args()

    content_rows = load_jsonl(args.contents)
    raw_total = len(content_rows)
    if not args.no_dedup:
        content_rows = deduplicate_rows(content_rows)
    comment_rows = load_jsonl(args.comments) if args.comments else []
    comment_summaries = summarize_comments(comment_rows)
    creator_profiles = load_creator_profiles(args.creators)

    analyzed = [
        classify(row, comment_summaries.get(str(row.get("aweme_id"))), args.now_ts, creator_profiles)
        for row in content_rows
    ]
    analyzed.sort(key=lambda item: (item["grade"], -item["score"], -item["share_count"]))
    category_rows = summarize_categories(analyzed)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "candidate_scores.csv", analyzed)
    write_csv(args.out_dir / "category_summary.csv", category_rows)
    (args.out_dir / "candidate_scores.json").write_text(
        json.dumps(analyzed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "category_summary.json").write_text(
        json.dumps(category_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(args.out_dir / "analysis_report.md", analyzed, category_rows, args.contents, args.comments, args.creators)
    print(json.dumps({
        "contents": str(args.contents),
        "comments": str(args.comments) if args.comments else None,
        "creators": str(args.creators) if args.creators else None,
        "out_dir": str(args.out_dir),
        "total_candidates": len(analyzed),
        "raw_candidates": raw_total,
        "deduplicated": not args.no_dedup,
        "grade_counts": dict(sorted(Counter(row["grade"] for row in analyzed).items())),
        "category_count": len(category_rows),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
