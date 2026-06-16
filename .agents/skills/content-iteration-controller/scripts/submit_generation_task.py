#!/usr/bin/env python3
"""Submit content-lab generation briefs to DoodleStory task API."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_API_BASE_URL = os.environ.get("DOODLESTORY_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
BINDINGS_RELATIVE_PATH = Path("content-lab/strategy_state/account_style_bindings.json")
TASK_SUBMISSIONS_DIR = Path("content-lab/task_submissions")
SESSION_COOKIE_NAME = "doodlestory_session"


class SubmitError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_bindings(root: Path) -> dict[str, Any]:
    path = root / BINDINGS_RELATIVE_PATH
    if not path.exists():
        raise SubmitError(f"账号画风绑定文件不存在：{path}。请先执行 init_state 或 bind-style。")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SubmitError(f"账号画风绑定文件格式错误：{path}")
    payload.setdefault("version", 1)
    payload.setdefault("accounts", {})
    if not isinstance(payload["accounts"], dict):
        raise SubmitError(f"账号画风绑定文件 accounts 必须是对象：{path}")
    return payload


def save_bindings(root: Path, payload: dict[str, Any]) -> None:
    write_json(root / BINDINGS_RELATIVE_PATH, payload)


def account_binding(bindings: dict[str, Any], account: str) -> dict[str, Any]:
    accounts = bindings.get("accounts", {})
    binding = accounts.get(account)
    if not isinstance(binding, dict):
        raise SubmitError(f"账号 `{account}` 尚未绑定 DoodleStory 风格，请先执行 bind-style。")
    style_id = str(binding.get("style_id") or "").strip()
    if not style_id:
        raise SubmitError(f"账号 `{account}` 的 style_id 为空，请先补齐账号画风绑定。")
    return binding


def normalize_api_path(api_base_url: str, path: str) -> str:
    base = api_base_url.rstrip("/")
    if base.endswith("/api/v1"):
        return f"{base}{path}"
    return f"{base}/api/v1{path}"


def request_json(
    opener: request.OpenerDirector,
    api_base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    cookie_value: str | None = None,
) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie_value:
        headers["Cookie"] = f"{SESSION_COOKIE_NAME}={cookie_value}"

    req = request.Request(normalize_api_path(api_base_url, path), data=body, headers=headers, method=method)
    try:
        with opener.open(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail = raw
        try:
            parsed = json.loads(raw)
            detail = parsed.get("detail") or parsed.get("error", {}).get("message") or raw
        except json.JSONDecodeError:
            pass
        raise SubmitError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise SubmitError(f"无法连接 DoodleStory 后端：{exc.reason}") from exc

    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SubmitError(f"后端返回非 JSON：{raw[:200]}") from exc


def authenticated_opener(args: argparse.Namespace) -> tuple[request.OpenerDirector, str | None]:
    cookie_value = (args.session_cookie or os.environ.get("DOODLESTORY_SESSION_COOKIE") or "").strip()
    cookie_jar = http.cookiejar.CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(cookie_jar))
    if cookie_value:
        return opener, cookie_value

    email = (args.email or os.environ.get("DOODLESTORY_EMAIL") or "").strip()
    password = args.password or os.environ.get("DOODLESTORY_PASSWORD") or ""
    if not email or not password:
        raise SubmitError(
            "缺少登录凭据。请提供 --email/--password，或设置 DOODLESTORY_EMAIL/DOODLESTORY_PASSWORD，"
            "或提供 --session-cookie / DOODLESTORY_SESSION_COOKIE。"
        )

    request_json(
        opener,
        args.api_base_url,
        "/auth/login",
        method="POST",
        payload={"email": email, "password": password},
    )
    return opener, None


def fetch_style(opener: request.OpenerDirector, api_base_url: str, style_id: str, cookie_value: str | None) -> dict[str, Any]:
    response = request_json(opener, api_base_url, f"/styles/{style_id}", cookie_value=cookie_value)
    style = response.get("data") if isinstance(response, dict) else None
    if not isinstance(style, dict):
        raise SubmitError(f"风格接口返回格式异常：{style_id}")
    if style.get("status") != "active":
        raise SubmitError(f"风格 `{style_id}` 不是 active 状态，不能绑定为发布账号画风。")
    if not str(style.get("image_model_name") or "").strip():
        raise SubmitError(f"风格 `{style_id}` 尚未绑定生图模型，不能创建任务。")
    return style


def extract_storyboard_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SubmitError(f"故事文件为空：{path}")

    markers = [
        "## 可直接粘贴到 DoodleStory 提取分镜模式的 storyboard_text",
        "## 可直接粘贴到 DoodleStory 故事方案模式的 brief_text",
    ]
    for marker in markers:
        index = text.find(marker)
        if index == -1:
            continue
        section = text[index + len(marker) :].strip()
        next_heading = re.search(r"\n##\s+", section)
        if next_heading:
            section = section[: next_heading.start()].strip()
        if section:
            return section
    return text


def publish_plan_path(root: Path, experiment_id: str) -> Path:
    return root / "content-lab" / "experiments" / experiment_id / "publish_plan.json"


def find_post(plan: dict[str, Any], slot_id: str) -> dict[str, Any]:
    posts = plan.get("posts")
    if not isinstance(posts, list):
        raise SubmitError("publish_plan.json 缺少 posts 数组")
    for post in posts:
        if isinstance(post, dict) and post.get("slot_id") == slot_id:
            return post
    raise SubmitError(f"publish_plan.json 中找不到 slot_id：{slot_id}")


def assert_post_can_submit(post: dict[str, Any], *, force_resubmit: bool) -> None:
    status = str(post.get("status") or "")
    if status.startswith("paused"):
        raise SubmitError(f"slot `{post.get('slot_id')}` 当前状态为 `{status}`，不允许提交任务。")
    generation_brief = post.get("generation_brief")
    if isinstance(generation_brief, dict):
        brief_status = str(generation_brief.get("status") or "")
        if brief_status.startswith("paused"):
            raise SubmitError(f"slot `{post.get('slot_id')}` 的 generation_brief 状态为 `{brief_status}`，不允许提交任务。")
    if post.get("task_id") and not force_resubmit:
        raise SubmitError(f"slot `{post.get('slot_id')}` 已有 task_id={post.get('task_id')}。如需再次提交，请显式传 --force-resubmit。")


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def build_task_payload(storyboard_text: str, style_id: str) -> dict[str, Any]:
    return {
        "original_text": storyboard_text,
        "story_input_mode": "extracted_storyboard",
        "image_count_mode": "auto",
        "requested_image_count": None,
        "style_id": style_id,
        "use_character_references": False,
        "story_characters": [],
    }


def submit_payload(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    opener, cookie_value = authenticated_opener(args)
    fetch_style(opener, args.api_base_url, payload["style_id"], cookie_value)
    response = request_json(opener, args.api_base_url, "/tasks", method="POST", payload=payload, cookie_value=cookie_value)
    task = response.get("data") if isinstance(response, dict) else None
    if not isinstance(task, dict) or not task.get("id"):
        raise SubmitError("任务创建接口返回格式异常，未拿到 task_id。")
    return task


def bind_style(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root
    bindings = load_bindings(root)
    style_name = args.style_name
    style_payload: dict[str, Any] | None = None
    verified = False
    if args.verify:
        opener, cookie_value = authenticated_opener(args)
        style_payload = fetch_style(opener, args.api_base_url, args.style_id, cookie_value)
        style_name = style_payload.get("name") or style_name
        verified = True

    bindings["accounts"][args.account] = {
        "style_id": args.style_id,
        "style_name": style_name,
        "style_verified": verified,
        "style_reference_mode": style_payload.get("style_reference_mode") if style_payload else None,
        "aspect_ratio": style_payload.get("aspect_ratio") if style_payload else None,
        "image_model_name": style_payload.get("image_model_name") if style_payload else None,
        "updated_at": now_iso(),
        "notes": args.notes or "账号画风绑定：发布任务必须从账号解析到固定 style_id。",
    }
    save_bindings(root, bindings)
    return {"account": args.account, "binding": bindings["accounts"][args.account], "path": str(root / BINDINGS_RELATIVE_PATH)}


def validate_bindings(args: argparse.Namespace) -> dict[str, Any]:
    bindings = load_bindings(args.root)
    opener, cookie_value = authenticated_opener(args)
    results: list[dict[str, Any]] = []
    for account, binding in sorted(bindings.get("accounts", {}).items()):
        if not isinstance(binding, dict):
            results.append({"account": account, "ok": False, "error": "binding must be object"})
            continue
        style_id = str(binding.get("style_id") or "").strip()
        if not style_id:
            results.append({"account": account, "ok": False, "error": "missing style_id"})
            continue
        try:
            style = fetch_style(opener, args.api_base_url, style_id, cookie_value)
            results.append({"account": account, "ok": True, "style_id": style_id, "style_name": style.get("name")})
        except SubmitError as exc:
            results.append({"account": account, "ok": False, "style_id": style_id, "error": str(exc)})
    return {"ok": all(item["ok"] for item in results), "results": results}


def submit_slot(args: argparse.Namespace) -> dict[str, Any]:
    plan_path = publish_plan_path(args.root, args.experiment_id)
    if not plan_path.exists():
        raise SubmitError(f"实验发布计划不存在：{plan_path}")
    plan = load_json(plan_path)
    post = find_post(plan, args.slot_id)
    assert_post_can_submit(post, force_resubmit=args.force_resubmit)
    account = str(post.get("account") or "").strip()
    if not account:
        raise SubmitError(f"slot `{args.slot_id}` 缺少 account 字段。")

    brief = post.get("generation_brief")
    if not isinstance(brief, dict) or not brief.get("artifact"):
        raise SubmitError(f"slot `{args.slot_id}` 缺少 generation_brief.artifact。")
    story_path = (args.root / str(brief["artifact"])).resolve()
    if not story_path.exists():
        raise SubmitError(f"generation brief 文件不存在：{story_path}")

    bindings = load_bindings(args.root)
    binding = account_binding(bindings, account)
    style_id = str(binding["style_id"])
    storyboard_text = extract_storyboard_text(story_path)
    payload = build_task_payload(storyboard_text, style_id)

    if args.dry_run:
        return {"dry_run": True, "slot_id": args.slot_id, "account": account, "payload": payload, "source": relative_to_root(args.root, story_path)}

    task = submit_payload(args, payload)
    submission = {
        "version": 1,
        "submitted_at": now_iso(),
        "experiment_id": args.experiment_id,
        "slot_id": args.slot_id,
        "account": account,
        "task_id": task["id"],
        "task_url": f"/tasks/{task['id']}",
        "style_id": style_id,
        "style_name": binding.get("style_name"),
        "source_storyboard": relative_to_root(args.root, story_path),
        "forced_task_options": {
            "story_input_mode": "extracted_storyboard",
            "image_count_mode": "auto",
            "requested_image_count": None,
            "use_character_references": False,
        },
    }
    post["task_id"] = task["id"]
    post["status"] = "task_created"
    post["task_submission"] = submission
    write_json(plan_path, plan)

    submission_path = args.root / TASK_SUBMISSIONS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}-{args.experiment_id}-{args.slot_id}.json"
    write_json(submission_path, submission)
    return {"task": task, "submission": submission, "submission_path": str(submission_path), "publish_plan": str(plan_path)}


def submit_file(args: argparse.Namespace) -> dict[str, Any]:
    story_path = args.storyboard_file.resolve()
    if not story_path.exists():
        raise SubmitError(f"故事文件不存在：{story_path}")
    bindings = load_bindings(args.root)
    binding = account_binding(bindings, args.account)
    payload = build_task_payload(extract_storyboard_text(story_path), str(binding["style_id"]))
    if args.dry_run:
        return {"dry_run": True, "account": args.account, "payload": payload, "source": relative_to_root(args.root, story_path)}
    task = submit_payload(args, payload)
    submission = {
        "version": 1,
        "submitted_at": now_iso(),
        "account": args.account,
        "task_id": task["id"],
        "task_url": f"/tasks/{task['id']}",
        "style_id": str(binding["style_id"]),
        "style_name": binding.get("style_name"),
        "source_storyboard": relative_to_root(args.root, story_path),
        "forced_task_options": {
            "story_input_mode": "extracted_storyboard",
            "image_count_mode": "auto",
            "requested_image_count": None,
            "use_character_references": False,
        },
    }
    submission_path = args.root / TASK_SUBMISSIONS_DIR / f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-{args.account}.json"
    write_json(submission_path, submission)
    return {"task": task, "submission": submission, "submission_path": str(submission_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit content-lab stories as DoodleStory extracted-storyboard tasks.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="DoodleStory project root")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL, help="DoodleStory backend base URL")
    parser.add_argument("--email", help="DoodleStory login email; or DOODLESTORY_EMAIL")
    parser.add_argument("--password", help="DoodleStory login password; or DOODLESTORY_PASSWORD")
    parser.add_argument("--session-cookie", help="Raw doodlestory_session cookie value; or DOODLESTORY_SESSION_COOKIE")

    subparsers = parser.add_subparsers(dest="command", required=True)

    bind = subparsers.add_parser("bind-style", help="Bind a Douyin account name to a DoodleStory style id.")
    bind.add_argument("--account", required=True)
    bind.add_argument("--style-id", required=True)
    bind.add_argument("--style-name")
    bind.add_argument("--notes")
    bind.add_argument("--verify", action="store_true", help="Verify the style through DoodleStory API before writing binding.")
    bind.set_defaults(func=bind_style)

    validate = subparsers.add_parser("validate-bindings", help="Validate all account-style bindings through DoodleStory API.")
    validate.set_defaults(func=validate_bindings)

    slot = subparsers.add_parser("submit-slot", help="Submit a publish_plan slot as an extracted-storyboard task.")
    slot.add_argument("--experiment-id", required=True)
    slot.add_argument("--slot-id", required=True)
    slot.add_argument("--dry-run", action="store_true")
    slot.add_argument("--force-resubmit", action="store_true")
    slot.set_defaults(func=submit_slot)

    file_parser = subparsers.add_parser("submit-file", help="Submit a standalone storyboard markdown/text file.")
    file_parser.add_argument("--account", required=True)
    file_parser.add_argument("--storyboard-file", type=Path, required=True)
    file_parser.add_argument("--dry-run", action="store_true")
    file_parser.set_defaults(func=submit_file)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.api_base_url = args.api_base_url.rstrip("/")
    try:
        result = args.func(args)
    except SubmitError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
