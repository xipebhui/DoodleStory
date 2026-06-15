#!/usr/bin/env python3
"""Collect Douyin search candidates from a logged-in browser session."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo


DEFAULT_OUTPUT_DIR = Path("/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/Downloaded/browser_search")
SEARCH_API_MARKERS = (
    "/aweme/v1/web/general/search/single/",
    "/aweme/v1/web/general/search/stream/",
)
GALLERY_TYPE_VALUES = {2, 68, 150, "2", "68", "150"}
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class SearchCandidate:
    keyword: str
    aweme_id: str
    title: str
    description: str
    author_name: str
    author_sec_uid: str
    create_time: int | None
    publish_date: str
    media_type: str
    aweme_type: str
    image_count: int
    digg_count: int | None
    comment_count: int | None
    collect_count: int | None
    share_count: int | None
    tags: list[str]
    source_url: str
    response_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open Douyin search with a logged-in browser storage_state, listen for "
            "general search network responses, and write raw/candidate evidence."
        )
    )
    parser.add_argument("--keyword", required=True, help="Douyin search keyword, for example: 故事")
    parser.add_argument(
        "--storage-state",
        required=True,
        type=Path,
        help="Playwright/Patchright storage_state JSON from a logged-in Douyin browser session.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scrolls", type=int, default=5, help="How many search-result scrolls to perform.")
    parser.add_argument("--wait-ms", type=int, default=2500, help="Wait time after page load and each scroll.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum candidates to write into summary/all files.")
    parser.add_argument("--channel", default="chrome", help="Browser channel for Patchright launch.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless. Default is headed.")
    parser.add_argument(
        "--entry-mode",
        choices=["ui", "url"],
        default="ui",
        help="Use UI search-box entry by default. Direct URL entry can load the shell without results.",
    )
    return parser.parse_args()


def require_patchright() -> Any:
    try:
        from patchright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "patchright is required. Run this script with "
            "/Users/pengfei.shi/workspace/tmp-project/social-auto-upload/.venv/bin/python"
        ) from exc
    return async_playwright


async def dismiss_save_login_prompt(page: Any) -> None:
    body_text = ""
    try:
        body_text = await page.locator("body").inner_text(timeout=2000)
    except Exception:
        return
    if "是否保存登录信息" not in body_text:
        return
    cancel_button = page.get_by_text("取消", exact=True)
    try:
        await cancel_button.click(timeout=3000)
        await page.wait_for_timeout(500)
    except Exception:
        return


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", text.strip(), flags=re.UNICODE).strip("_")
    return slug or "keyword"


def int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def publish_date_from_ts(value: Any) -> str:
    ts = int_or_none(value)
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def first_title(desc: Any) -> str:
    text = str(desc or "").strip()
    return text.split("#", 1)[0].strip()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def tags_from_aweme(aweme: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for extra in aweme.get("text_extra") or []:
        if isinstance(extra, dict) and extra.get("hashtag_name"):
            tags.append(str(extra["hashtag_name"]))
    desc = str(aweme.get("desc") or "")
    tags.extend(match.strip() for match in re.findall(r"#([^#\s]+)", desc))
    return dedupe(tags)


def image_count_from_aweme(aweme: dict[str, Any]) -> int:
    for key in ("images", "image_list", "image_infos"):
        value = aweme.get(key)
        if isinstance(value, list):
            return len(value)
    image_post_info = aweme.get("image_post_info")
    if isinstance(image_post_info, dict):
        images = image_post_info.get("images")
        if isinstance(images, list):
            return len(images)
    return 0


def media_type_from_aweme(aweme: dict[str, Any], image_count: int) -> str:
    if image_count > 0:
        return "gallery"
    if aweme.get("media_type") in GALLERY_TYPE_VALUES or aweme.get("aweme_type") in GALLERY_TYPE_VALUES:
        return "gallery"
    if aweme.get("video"):
        return "video"
    return "unknown"


def iter_aweme_infos(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    data = payload.get("data")
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            aweme = entry.get("aweme_info")
            if isinstance(aweme, dict):
                items.append(aweme)
            elif entry.get("aweme_id"):
                items.append(entry)
    return items


def share_url_from_aweme(aweme: dict[str, Any]) -> str:
    share_url = aweme.get("share_url")
    if share_url:
        return str(share_url)
    share_info = aweme.get("share_info")
    if isinstance(share_info, dict) and share_info.get("share_url"):
        return str(share_info["share_url"])
    return ""


def candidate_from_aweme(keyword: str, aweme: dict[str, Any], response_url: str) -> SearchCandidate | None:
    aweme_id = str(aweme.get("aweme_id") or "").strip()
    if not aweme_id:
        return None
    author = aweme.get("author") if isinstance(aweme.get("author"), dict) else {}
    stats = aweme.get("statistics") if isinstance(aweme.get("statistics"), dict) else {}
    image_count = image_count_from_aweme(aweme)
    create_time = int_or_none(aweme.get("create_time"))
    return SearchCandidate(
        keyword=keyword,
        aweme_id=aweme_id,
        title=first_title(aweme.get("desc")),
        description=str(aweme.get("desc") or ""),
        author_name=str(author.get("nickname") or ""),
        author_sec_uid=str(author.get("sec_uid") or ""),
        create_time=create_time,
        publish_date=publish_date_from_ts(create_time),
        media_type=media_type_from_aweme(aweme, image_count),
        aweme_type=str(aweme.get("aweme_type") or ""),
        image_count=image_count,
        digg_count=int_or_none(stats.get("digg_count")),
        comment_count=int_or_none(stats.get("comment_count")),
        collect_count=int_or_none(stats.get("collect_count")),
        share_count=int_or_none(stats.get("share_count")),
        tags=tags_from_aweme(aweme),
        source_url=share_url_from_aweme(aweme),
        response_url=response_url,
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def render_summary(
    keyword: str,
    candidates: list[SearchCandidate],
    gallery: list[SearchCandidate],
    meta: dict[str, Any],
) -> str:
    lines = [
        f"# Douyin browser search: {keyword}",
        "",
        "## Meta",
        "",
        f"- collected_at: {meta['collected_at']}",
        f"- response_count: {meta['response_count']}",
        f"- all_candidates: {len(candidates)}",
        f"- gallery_candidates: {len(gallery)}",
        f"- storage_state: {meta['storage_state']}",
        "",
        "## Gallery Candidates",
        "",
        "| publish_date | aweme_id | title | author | images | digg | comments | collects | shares | tags |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in gallery:
        title = item.title.replace("|", " ")
        tags = ",".join(item.tags).replace("|", " ")
        lines.append(
            f"| {item.publish_date} | {item.aweme_id} | {title} | {item.author_name} | "
            f"{item.image_count} | {item.digg_count or ''} | {item.comment_count or ''} | "
            f"{item.collect_count or ''} | {item.share_count or ''} | {tags} |"
        )
    return "\n".join(lines) + "\n"


async def collect(args: argparse.Namespace) -> int:
    storage_state = args.storage_state.expanduser().resolve()
    if not storage_state.exists():
        raise FileNotFoundError(f"storage_state file does not exist: {storage_state}")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=LOCAL_TZ).strftime("%Y%m%d-%H%M%S")
    stem = f"{safe_slug(args.keyword)}_{ts}"

    raw_responses: list[dict[str, Any]] = []
    response_errors: list[str] = []
    response_tasks: list[asyncio.Task[None]] = []

    async def handle_response(response: Any) -> None:
        if not any(marker in response.url for marker in SEARCH_API_MARKERS):
            return
        try:
            payload = await response.json()
        except Exception as exc:
            response_errors.append(f"{response.url}: {type(exc).__name__}: {exc}")
            return
        if isinstance(payload, dict):
            raw_responses.append({"url": response.url, "payload": payload})

    async_playwright = require_patchright()
    search_url = f"https://www.douyin.com/search/{quote(args.keyword)}?type=general"
    final_url = search_url
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel=args.channel, headless=args.headless)
        context = await browser.new_context(storage_state=str(storage_state))
        page = await context.new_page()
        page.on("response", lambda response: response_tasks.append(asyncio.create_task(handle_response(response))))
        if args.entry_mode == "ui":
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(args.wait_ms)
            search_input = page.locator("input").first
            await search_input.click(timeout=10000)
            await search_input.fill(args.keyword)
            await page.keyboard.press("Enter")
        else:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(args.wait_ms)
        for _ in range(max(args.scrolls, 0)):
            await page.mouse.wheel(0, 1800)
            await page.wait_for_timeout(args.wait_ms)
        if response_tasks:
            await asyncio.gather(*response_tasks)
        final_url = page.url
        await dismiss_save_login_prompt(page)
        await browser.close()

    raw_path = output_dir / f"{stem}_raw_responses.json"
    raw_path.write_text(json.dumps(raw_responses, ensure_ascii=False, indent=2), encoding="utf-8")

    candidates_by_id: dict[str, SearchCandidate] = {}
    for raw in raw_responses:
        response_url = str(raw.get("url") or "")
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        for aweme in iter_aweme_infos(payload):
            candidate = candidate_from_aweme(args.keyword, aweme, response_url)
            if candidate and candidate.aweme_id not in candidates_by_id:
                candidates_by_id[candidate.aweme_id] = candidate

    candidates = sorted(
        candidates_by_id.values(),
        key=lambda item: (item.create_time or 0, item.digg_count or 0, item.comment_count or 0),
        reverse=True,
    )[: args.limit]
    gallery = [item for item in candidates if item.media_type == "gallery"]

    candidate_rows = [asdict(item) for item in candidates]
    gallery_rows = [asdict(item) for item in gallery]
    write_jsonl(output_dir / f"{stem}_all_aweme.jsonl", candidate_rows)
    write_jsonl(output_dir / f"{stem}_gallery.jsonl", gallery_rows)

    meta = {
        "keyword": args.keyword,
        "search_url": search_url,
        "final_url": final_url,
        "entry_mode": args.entry_mode,
        "collected_at": datetime.now(tz=LOCAL_TZ).isoformat(timespec="seconds"),
        "storage_state": str(storage_state),
        "output_dir": str(output_dir),
        "response_count": len(raw_responses),
        "response_errors": response_errors,
        "all_candidate_count": len(candidates),
        "gallery_candidate_count": len(gallery),
        "raw_responses_path": str(raw_path),
    }
    (output_dir / f"{stem}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / f"{stem}_summary.md").write_text(render_summary(args.keyword, candidates, gallery, meta), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    if not raw_responses:
        raise RuntimeError(
            "No Douyin search API responses were captured. Check that the browser session is logged in "
            "and the page is not blocked by verification."
        )
    if not candidates:
        raise RuntimeError("Search responses were captured, but no aweme candidates were parsed.")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(collect(args))


if __name__ == "__main__":
    raise SystemExit(main())
