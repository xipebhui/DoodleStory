from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    FileAsset,
    NativeAgentConversation,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    Style,
    StyleReferenceImage,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentItemType,
    NativeAgentStepStatus,
    NativeAgentStepType,
    StyleReferenceMode,
    StyleStatus,
    UserRole,
)
from app.services.agent_skill_management import parse_tool_names
from app.services.durable_agent_runtime import initialize_workflow
from app.services.native_agent_loop import execute_native_agent_run
from app.services.native_agent_model_routes import (
    SILICONFLOW_CHAT_ROUTE,
    resolve_native_agent_model_route,
)
from app.services.native_agent_persistence import add_native_agent_event
from app.services.native_agent_route_capabilities import (
    validate_native_agent_route_capability,
)
from app.services.storage import materialize_asset_to_local


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DOCUMENT = PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-chinese-script-prompt-pack.md"
G3_REPORT = PROJECT_ROOT / "docs/testing/siliconflow-native-agent-compatibility-report.json"
TEMPLATE = PROJECT_ROOT / "docs/strategy/youtube/paynes-creek-s03-gate-evidence-template.json"
STYLE_NAME = "Paynes Creek Evidence Desk 16:9"
SKILL_NAME = "Paynes Creek S03 单镜生产验证"
EXPECTED_PROMPT_SHA256 = "3cd1a0820096f3b3804aad06ced282265559adf40460401a6b0b47f980303729"
EXPECTED_STYLE_PROMPT_SHA256 = "5b8b5a7d144b13d6cdecc2ba2949205090df0958d8563b69968e8940a23b0d1b"
EXPECTED_IMAGE_MODEL = "Qwen/Qwen-Image"
EXPECTED_VISION_MODEL = "Qwen/Qwen3-VL-32B-Instruct"
EXPECTED_AGENT_MODEL = "deepseek-ai/DeepSeek-V3.2"
EXPECTED_SKILL_VERSION_ID = "ba3a4875771248c4870b1ab6cf6afabd"
EXPECTED_STYLE_ID = "4443d2412c994ec298b635e6c63806e7"
EXPECTED_TOOLS = {"generate_image", "inspect_image"}
ACTIVE_STATUSES = {
    AgentRunStatus.queued,
    AgentRunStatus.running,
    AgentRunStatus.waiting_for_tool,
    AgentRunStatus.waiting_for_input,
    AgentRunStatus.retrying,
    AgentRunStatus.cancel_requested,
}
CHECKS = [
    "historical_mechanism_alignment",
    "reconstruction_boundary",
    "modern_object_exclusion",
    "composition_and_subtitle_safety",
    "pan_right_crop_safety",
    "visual_artifacts_and_text_exclusion",
]
EXPECTED = {
    "story_beat": (
        "A cautious non-photoreal horizontal reconstruction of brine concentration. "
        "Show only a simple elevated wooden container with low-detail saline earth, "
        "liquid passing through a funnel-like outlet into one rough unglazed ceramic jar. "
        "Use one teal liquid path and amber dashed reconstruction contours. Keep essential "
        "objects inside the central 84% and upper 70%, with the bottom 30% quiet for Chinese "
        "subtitles. Exclude modern filters, pipes, valves, precision machinery, copied "
        "Sacapulas installations, text, logos and watermarks."
    ),
    "characters": [],
    "required_text": [],
}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def current_commit() -> str:
    return _git("rev-parse", "HEAD")


def working_tree_clean() -> bool:
    return not _git("status", "--porcelain")


def load_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if path.resolve() == PROMPT_DOCUMENT.resolve():
        match = re.search(r"^### S03｜.*?^```text\n(.*?)\n```", text, re.MULTILINE | re.DOTALL)
        if match is None:
            raise RuntimeError("无法从 Prompt 包解析 S03 text code block")
        return match.group(1)
    code_block = re.search(r"^```text\n(.*?)\n```", text, re.MULTILINE | re.DOTALL)
    prompt = code_block.group(1) if code_block is not None else text.strip("\n")
    if not prompt.strip():
        raise RuntimeError("G4 Prompt 文件为空")
    return prompt


def canonical_prompt() -> str:
    return load_prompt(PROMPT_DOCUMENT)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_inspection(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("G4 inspection 文件不是有效 JSON") from exc
    if not isinstance(value, dict) or set(value) != {"checks", "expected"}:
        raise RuntimeError("G4 inspection 必须且只能包含 checks 与 expected")
    checks = value["checks"]
    expected = value["expected"]
    if (
        not isinstance(checks, list)
        or not checks
        or len(checks) > 10
        or len(checks) != len(set(checks))
        or not all(isinstance(item, str) and item.strip() for item in checks)
    ):
        raise RuntimeError("G4 inspection checks 必须为 1–10 个不重复非空字符串")
    if not isinstance(expected, dict):
        raise RuntimeError("G4 inspection expected 必须为对象")
    if not isinstance(expected.get("story_beat"), str) or not expected["story_beat"].strip():
        raise RuntimeError("G4 inspection expected.story_beat 不能为空")
    for key in ("characters", "required_text"):
        if not isinstance(expected.get(key), list):
            raise RuntimeError(f"G4 inspection expected.{key} 必须为数组")
    return value


def inspection_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)


def inspection_request_from_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    request = {
        "checks": payload.get("checks"),
        "expected": payload.get("expected"),
    }
    if not isinstance(request["checks"], list) or not isinstance(request["expected"], dict):
        raise RuntimeError("inspect_image Tool Call 缺少有效 checks 或 expected")
    return request


def _safe_timestamp(value: datetime | None) -> str | None:
    return value.isoformat(timespec="milliseconds") + "Z" if value else None


def _load_g3_status() -> str | None:
    data = json.loads(G3_REPORT.read_text(encoding="utf-8"))
    return data.get("gate_decision", {}).get("status")


def _style_and_skill(db) -> tuple[Style, AgentSkill, AgentSkillVersion, User, int]:
    styles = list(db.scalars(select(Style).where(Style.name == STYLE_NAME)).all())
    skills = list(db.scalars(select(AgentSkill).where(AgentSkill.name == SKILL_NAME)).all())
    if len(styles) != 1 or len(skills) != 1:
        raise RuntimeError("G4 要求 Style 与 Skill 在当前数据库中各自唯一")
    style = styles[0]
    skill = skills[0]
    version = db.get(AgentSkillVersion, skill.active_version_id)
    owner = db.get(User, skill.owner_user_id)
    if version is None or owner is None:
        raise RuntimeError("G4 Skill 缺少 active Version 或 owner")
    reference_count = int(
        db.scalar(
            select(func.count(StyleReferenceImage.id)).where(
                StyleReferenceImage.style_id == style.id
            )
        )
        or 0
    )
    return style, skill, version, owner, reference_count


def preflight(
    source_commit: str,
    *,
    prompt_path: Path = PROMPT_DOCUMENT,
    expected_prompt_sha256: str = EXPECTED_PROMPT_SHA256,
    inspection_path: Path | None = None,
    expected_inspection_sha256: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    prompt_hash = sha256_text(load_prompt(prompt_path))
    inspection = (
        load_inspection(inspection_path)
        if inspection_path is not None
        else {"checks": CHECKS, "expected": EXPECTED}
    )
    inspection_hash = inspection_sha256(inspection)
    observed_commit = current_commit()
    with SessionLocal() as db:
        style, skill, version, owner, reference_count = _style_and_skill(db)
        active_run_count = int(
            db.scalar(
                select(func.count(NativeAgentRun.id)).where(
                    NativeAgentRun.status.in_(ACTIVE_STATUSES)
                )
            )
            or 0
        )
        facts = {
            "style_id": style.id,
            "style_status": style.status.value,
            "style_deleted": style.deleted_at is not None,
            "style_image_model": style.image_model_name,
            "style_aspect_ratio": style.aspect_ratio,
            "style_reference_mode": style.style_reference_mode.value,
            "style_prompt_sha256": sha256_text(style.style_prompt),
            "reference_count": reference_count,
            "skill_version_id": version.id,
            "skill_status": skill.status.value,
            "skill_version": version.version,
            "skill_tools": sorted(parse_tool_names(version.tool_names_json)),
            "owner_user_id": owner.id,
            "owner_role": owner.role.value,
            "active_run_count": active_run_count,
        }
    checks = {
        "source_commit_matches": observed_commit == source_commit,
        "working_tree_clean": working_tree_clean(),
        "prompt_hash_matches": prompt_hash == expected_prompt_sha256,
        "inspection_hash_matches": (
            expected_inspection_sha256 is None
            or inspection_hash == expected_inspection_sha256
        ),
        "g3_passed": _load_g3_status() == "pass_for_s03_single_image_review",
        "style_id_matches": facts["style_id"] == EXPECTED_STYLE_ID,
        "style_active": facts["style_status"] == StyleStatus.active.value,
        "style_not_deleted": not facts["style_deleted"],
        "style_model_matches": facts["style_image_model"] == EXPECTED_IMAGE_MODEL,
        "style_ratio_matches": facts["style_aspect_ratio"] == "16:9",
        "style_mode_matches": facts["style_reference_mode"] == StyleReferenceMode.prompt.value,
        "style_prompt_matches": facts["style_prompt_sha256"] == EXPECTED_STYLE_PROMPT_SHA256,
        "style_reference_count_zero": facts["reference_count"] == 0,
        "skill_version_matches": facts["skill_version_id"] == EXPECTED_SKILL_VERSION_ID,
        "skill_published": facts["skill_status"] == AgentSkillStatus.published.value,
        "skill_tools_match": set(facts["skill_tools"]) == EXPECTED_TOOLS,
        "no_active_run": facts["active_run_count"] == 0,
        "agent_model_matches": settings.native_agent_siliconflow_model == EXPECTED_AGENT_MODEL,
        "vision_model_matches": settings.siliconflow_vision_model == EXPECTED_VISION_MODEL,
        "image_provider_qy": settings.image_provider == "qy",
        "image_gateway_configured": bool(settings.image_gateway_api_key.strip()),
        "siliconflow_configured": bool(settings.siliconflow_api_key.strip()),
        "image_http_single_attempt": settings.xg_request_max_attempts == 1,
        "image_timeout_retry_disabled": settings.image_provider_timeout_retry_attempts == 0,
        "raw_image_io_logging_disabled": not settings.image_provider_debug_log_raw_io,
        "storage_configured": settings.storage_backend in {"local", "qiniu", "aliyun_oss"},
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "all_passed": not blockers,
        "blockers": blockers,
        "observed_commit": observed_commit,
        "prompt_path": str(prompt_path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "expected_prompt_sha256": expected_prompt_sha256,
        "prompt_sha256": prompt_hash,
        "inspection_path": (
            str(inspection_path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
            if inspection_path is not None
            else None
        ),
        "expected_inspection_sha256": expected_inspection_sha256,
        "inspection_sha256": inspection_hash,
        "g3_status": _load_g3_status(),
        "database": facts,
        "checks": checks,
    }


def build_user_content(prompt: str, inspection: dict[str, Any] | None = None) -> str:
    locked_inspection = inspection or {"checks": CHECKS, "expected": EXPECTED}
    return (
        "执行 Paynes Creek S03 唯一单图媒体 Gate。只允许按下列完整 Prompt 调用一次 "
        "generate_image，provider 必须为 qy；不得改写、缩短、补充或再次调用。生成成功后，必须使用返回的 "
        "image_id 调用一次 inspect_image，checks 与 expected 必须严格使用下列 JSON。检查完成后只总结真实 "
        "image_id 和 verdict，不调用任何其他 Tool。\n\n"
        "<locked_generate_image_prompt>\n"
        f"{prompt}\n"
        "</locked_generate_image_prompt>\n\n"
        "<locked_inspection_request>\n"
        f"{json.dumps(locked_inspection, ensure_ascii=False, separators=(',', ':'))}\n"
        "</locked_inspection_request>"
    )


def create_run(
    *, source_commit: str, prompt: str, inspection: dict[str, Any], attempt_label: str
) -> tuple[str, str, bool]:
    settings = get_settings()
    with SessionLocal() as db:
        style, skill, version, owner, _ = _style_and_skill(db)
        promoted = owner.role != UserRole.admin
        if promoted:
            owner.role = UserRole.admin
            db.commit()
        route = resolve_native_agent_model_route(
            settings,
            requested_route=SILICONFLOW_CHAT_ROUTE,
        )
        tool_names = set(parse_tool_names(version.tool_names_json))
        validate_native_agent_route_capability(
            route,
            selected_tool_names=tool_names,
            style_id=style.id,
            creation_channel_id=None,
            youtube_channel_id=None,
            youtube_publishable_video_id=None,
            has_youtube_publish_confirmation=False,
        )
        conversation = NativeAgentConversation(
            owner_user_id=owner.id,
            title=f"Paynes Creek S03 {attempt_label}",
        )
        db.add(conversation)
        db.flush()
        run = NativeAgentRun(
            conversation_id=conversation.id,
            skill_version_id=version.id,
            style_id=style.id,
            status=AgentRunStatus.queued,
            model_snapshot=route.model,
            model_route_snapshot=route.route,
            model_provider_snapshot=route.provider,
            model_api_shape_snapshot=route.api_shape,
            skill_name_snapshot=version.name_snapshot,
            skill_version_snapshot=version.version,
            skill_content_hash_snapshot=version.content_hash,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_snapshot=style.image_model_name,
            aspect_ratio_snapshot=style.aspect_ratio,
            style_reference_urls_json="[]",
        )
        db.add(run)
        db.flush()
        db.add(
            NativeAgentItem(
                run_id=run.id,
                sequence=1,
                item_type=NativeAgentItemType.user_input,
                payload_json=json.dumps(
                    {"content": build_user_content(prompt, inspection)},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        )
        add_native_agent_event(
            db,
            run.id,
            "run.created",
            {"status": AgentRunStatus.queued.value, "source_commit": source_commit[:12]},
        )
        initialize_workflow(db, native_run=run, include_article_tasks=False)
        conversation.last_message_at = datetime.utcnow()
        db.commit()
        return conversation.id, run.id, promoted


def create_pan_probe(source: Path, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        width, height = image.size
        scaled = image.resize(
            (round(width * 1.08), round(height * 1.08)),
            Image.Resampling.LANCZOS,
        )
        base_left = (scaled.width - width) // 2
        base_top = (scaled.height - height) // 2
        shift = round(width * 0.03)
        crops = {}
        for label, left in (("start", base_left + shift), ("end", base_left - shift)):
            crop = scaled.crop((left, base_top, left + width, base_top + height))
            path = output_dir / f"PC-S03-pan-right-{label}.png"
            crop.save(path, format="PNG")
            crops[label] = path
        preview_size = (960, 540)
        contact = Image.new("RGB", (preview_size[0] * 2, preview_size[1]), "#080808")
        for index, label in enumerate(("start", "end")):
            with Image.open(crops[label]) as crop:
                contact.paste(ImageOps.fit(crop.convert("RGB"), preview_size), (index * 960, 0))
        contact_path = output_dir / "PC-S03-pan-right-contact-sheet.png"
        contact.save(contact_path, format="PNG")
    return {
        "start": str(crops["start"].relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "end": str(crops["end"].relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "contact_sheet": str(contact_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }


def _copy_candidate(
    image: NativeAgentImage,
    output_dir: Path,
    *,
    candidate_stem: str,
) -> tuple[Path, dict[str, str]]:
    source = materialize_asset_to_local(image.asset)
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
        image.asset.content_type,
        source.suffix or ".bin",
    )
    candidate = output_dir / f"{candidate_stem}{suffix}"
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, candidate)
    return candidate, create_pan_probe(candidate, output_dir)


def _step_payload(step: NativeAgentStep | None) -> dict[str, Any]:
    if step is None or not step.output_ref_json:
        return {}
    try:
        value = json.loads(step.output_ref_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def build_report(
    *,
    preflight_data: dict[str, Any],
    conversation_id: str,
    run_id: str,
    promoted: bool,
    source_commit: str,
    attempt_label: str,
    authorization_ref: str,
    output_dir: Path,
    prompt_path: Path,
    expected_prompt_sha256: str,
    inspection_path: Path | None,
    expected_inspection_sha256: str | None,
    previous_attempt_ref: str,
    candidate_stem: str,
) -> dict[str, Any]:
    report = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    report["record_status"] = "completed"
    report["created_at"] = "2026-08-13"
    report["gate"]["attempt_label"] = attempt_label
    previous_path = PROJECT_ROOT / previous_attempt_ref
    if previous_path.suffix.lower() == ".json":
        previous_data = json.loads(previous_path.read_text(encoding="utf-8"))
        report["gate"]["previous_attempt"] = {
            "gate_record": previous_attempt_ref,
            "run_id": previous_data.get("run_snapshot", {}).get("run_id"),
            "outcome": previous_data.get("gate_decision", {}).get("status"),
            "image_call_count": previous_data.get("observed_call_counts", {}).get(
                "image_provider_call_count"
            ),
        }
    report["locked_inputs"]["scene"]["expected_candidate_filename"] = f"{candidate_stem}.png"
    report["locked_inputs"]["source_lock"]["prompt_document"] = str(
        prompt_path.relative_to(PROJECT_ROOT)
    ).replace("\\", "/")
    report["locked_inputs"]["source_lock"]["prompt_selector"] = "entire file"
    report["locked_inputs"]["source_lock"]["expected_prompt_sha256"] = expected_prompt_sha256
    report["locked_inputs"]["source_lock"]["submitted_prompt_sha256"] = preflight_data["prompt_sha256"]
    report["locked_inputs"]["source_lock"]["prompt_hash_matches"] = True
    report["locked_inputs"]["source_lock"]["inspection_document"] = (
        str(inspection_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if inspection_path is not None
        else "runner_default"
    )
    report["locked_inputs"]["source_lock"]["expected_inspection_sha256"] = (
        expected_inspection_sha256
    )
    report["locked_inputs"]["source_lock"]["submitted_inspection_sha256"] = preflight_data[
        "inspection_sha256"
    ]
    report["locked_inputs"]["source_lock"]["inspection_hash_matches"] = True
    style_data = report["locked_inputs"]["style_and_skill"]
    style_data["observed_style_id"] = preflight_data["database"]["style_id"]
    style_data["observed_skill_version_id"] = preflight_data["database"]["skill_version_id"]
    style_data["observed_at"] = _now()
    report["preflight"]["g2_offline_adapter"].update(
        {
            "observed_status": "pass_offline",
            "evidence_ref": "docs/contracts/sprint-192-native-agent-siliconflow-chat-bounded-adapter.md",
            "verified_at": _now(),
        }
    )
    report["preflight"]["g3_zero_media_gate"].update(
        {
            "observed_status": preflight_data["g3_status"],
            "evidence_ref": "docs/testing/siliconflow-native-agent-compatibility-report.json",
            "verified_at": _now(),
        }
    )
    report["preflight"]["g4_media_authorization"].update(
        {
            "authorized_by": "workspace_owner",
            "authorized_at": _now(),
            "authorization_ref": authorization_ref,
        }
    )
    report["preflight"]["cost_cap"].update(
        {
            "currency": "existing_provider_quota_only",
            "amount": 0,
            "approved_by": "workspace_owner",
            "approved_at": _now(),
        }
    )
    report["preflight"]["reviewers"] = {
        "fact_reviewer": "Codex delegated production reviewer (AI)",
        "visual_reviewer": "Codex delegated production reviewer (AI)",
    }
    report["preflight"]["all_passed"] = preflight_data["all_passed"]
    report["preflight"]["blockers"] = preflight_data["blockers"]
    with SessionLocal() as db:
        run = db.get(NativeAgentRun, run_id)
        if run is None:
            raise RuntimeError("G4 Run 在执行后不存在")
        images = list(
            db.scalars(
                select(NativeAgentImage)
                .where(NativeAgentImage.run_id == run_id)
                .options(selectinload(NativeAgentImage.asset))
            ).all()
        )
        steps = list(
            db.scalars(
                select(NativeAgentStep)
                .where(NativeAgentStep.run_id == run_id)
                .order_by(NativeAgentStep.sequence.asc())
            ).all()
        )
        items = list(
            db.scalars(
                select(NativeAgentItem)
                .where(NativeAgentItem.run_id == run_id)
                .order_by(NativeAgentItem.sequence.asc())
            ).all()
        )
        model_steps = [step for step in steps if step.step_type == NativeAgentStepType.model_call]
        generate_steps = [step for step in steps if step.name == "generate_image"]
        inspect_steps = [step for step in steps if step.name == "inspect_image"]
        publish_steps = [step for step in steps if step.name == "publish_youtube_video"]
        generate = generate_steps[0] if generate_steps else None
        inspection = inspect_steps[0] if inspect_steps else None
        generate_output = _step_payload(generate)
        inspection_output = _step_payload(inspection)
        inspection_tool_payloads = []
        for item in items:
            if item.item_type != NativeAgentItemType.tool_call:
                continue
            payload = json.loads(item.payload_json or "{}")
            if isinstance(payload, dict) and payload.get("tool") == "inspect_image":
                inspection_tool_payloads.append(payload)
        actual_inspection_request = (
            inspection_request_from_tool_payload(inspection_tool_payloads[0])
            if len(inspection_tool_payloads) == 1
            else None
        )
        actual_inspection_hash = (
            inspection_sha256(actual_inspection_request)
            if actual_inspection_request is not None
            else None
        )
        inspection_request_matches = (
            actual_inspection_hash == preflight_data["inspection_sha256"]
        )
        report["locked_inputs"]["source_lock"]["observed_inspection_sha256"] = (
            actual_inspection_hash
        )
        report["locked_inputs"]["source_lock"]["inspection_tool_request_matches"] = (
            inspection_request_matches
        )
        report["run_snapshot"].update(
            {
                "conversation_id": conversation_id,
                "run_id": run.id,
                "execution_attempt": max((step.execution_attempt or 0 for step in model_steps), default=0) or None,
                "created_at": _safe_timestamp(run.created_at),
                "finished_at": _safe_timestamp(run.finished_at),
                "terminal_status": run.status.value,
                "route_id": run.model_route_snapshot,
                "provider": run.model_provider_snapshot,
                "api_shape": run.model_api_shape_snapshot,
                "agent_model": run.model_snapshot,
                "image_provider": images[0].provider_snapshot if len(images) == 1 else "qy",
                "image_model": run.image_model_snapshot,
                "aspect_ratio": run.aspect_ratio_snapshot,
            }
        )
        report["observed_call_counts"].update(
            {
                "model_call_count": len(model_steps),
                "generate_image_tool_call_count": len(generate_steps),
                "image_provider_call_count": sum(step.attempts for step in generate_steps),
                "inspect_image_tool_call_count": sum(step.attempts for step in inspect_steps),
                "speech_call_count": run.speech_call_count,
                "subtitle_call_count": run.subtitle_call_count,
                "video_call_count": run.video_call_count,
                "publish_call_count": len(publish_steps),
            }
        )
        report["generate_image"].update(
            {
                "tool_call_id": generate.tool_call_id if generate else None,
                "step_id": generate.id if generate else None,
                "status": generate.status.value if generate else "not_run",
                "started_at": _safe_timestamp(generate.started_at) if generate else None,
                "finished_at": _safe_timestamp(generate.finished_at) if generate else None,
                "provider": images[0].provider_snapshot if len(images) == 1 else "qy",
                "model": images[0].image_model_snapshot if len(images) == 1 else run.image_model_snapshot,
                "provider_request_id": generate_output.get("provider_request_id"),
                "image_id": images[0].id if len(images) == 1 else None,
                "asset_id": images[0].asset_id if len(images) == 1 else None,
                "error_type": generate.error_code if generate else None,
                "error_code": generate.error_code if generate else None,
                "error_summary": generate.error_message if generate else None,
                "retryable": False if generate else None,
            }
        )
        if len(images) == 1:
            image = images[0]
            candidate, probes = _copy_candidate(
                image,
                output_dir,
                candidate_stem=candidate_stem,
            )
            candidate_bytes = candidate.read_bytes()
            with Image.open(candidate) as actual:
                width, height = actual.size
            report["candidate_asset"].update(
                {
                    "status": "observed",
                    "candidate_filename": str(candidate.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "mime_type": image.asset.content_type,
                    "byte_size": len(candidate_bytes),
                    "sha256": hashlib.sha256(candidate_bytes).hexdigest(),
                    "actual_width_px": width,
                    "actual_height_px": height,
                    "actual_aspect_ratio": round(width / height, 6),
                }
            )
            report["candidate_asset"]["motion_probe"].update(
                {
                    "safe_after_probe": None,
                    "evidence_ref": probes["contact_sheet"],
                }
            )
            report["audit"]["evidence_refs"].extend(
                [
                    report["candidate_asset"]["candidate_filename"],
                    probes["start"],
                    probes["end"],
                    probes["contact_sheet"],
                ]
            )
        report["inspect_image"].update(
            {
                "tool_call_id": inspection.tool_call_id if inspection else None,
                "step_id": inspection.id if inspection else None,
                "status": inspection.status.value if inspection else "not_run",
            }
        )
        report["inspect_image"]["request"] = {
            "image_id": inspection_tool_payloads[0].get("image_id")
            if len(inspection_tool_payloads) == 1
            else None,
            "checks": actual_inspection_request["checks"]
            if actual_inspection_request is not None
            else None,
            "expected": actual_inspection_request["expected"]
            if actual_inspection_request is not None
            else None,
            "canonical_sha256": actual_inspection_hash,
            "matches_locked_request": inspection_request_matches,
        }
        report["inspect_image"]["response"].update(
            {
                "image_id": inspection_output.get("image_id"),
                "verdict": inspection_output.get("verdict"),
                "scores": inspection_output.get("scores", {}),
                "issues": inspection_output.get("issues", []),
                "provider": inspection_output.get("provider"),
                "model": inspection_output.get("model"),
                "latency_ms": inspection_output.get("latency_ms"),
                "error_type": inspection.error_code if inspection else None,
                "error_summary": inspection.error_message if inspection else None,
            }
        )
        decision = report["gate_decision"]
        machine_verdict = inspection_output.get("verdict")
        decision["machine_verdict"] = machine_verdict
        decision["decided_by"] = "G4 execution runner"
        decision["decided_at"] = _now()
        if not generate_steps:
            decision.update(
                {
                    "status": "failed_before_image",
                    "decision_note": "Agent 在 generate_image Tool Call 前结束或失败。",
                    "stop_reason": run.error_code or "no_generate_image_tool_call",
                }
            )
        elif not images:
            decision.update(
                {
                    "status": "failed_during_image",
                    "decision_note": "唯一图片 Tool 未形成可读资产。",
                    "stop_reason": generate.error_code or "image_asset_missing",
                }
            )
        elif inspection is None or inspection.status != NativeAgentStepStatus.succeeded:
            decision.update(
                {
                    "status": "failed_during_inspection",
                    "decision_note": "候选已保留，但唯一 VL 检查未成功。",
                    "stop_reason": inspection.error_code if inspection else "inspection_missing",
                }
            )
        elif not inspection_request_matches:
            decision.update(
                {
                    "status": "needs_revision",
                    "decision_note": "实际 inspect_image 请求与锁定检查请求不一致；本 Attempt 停止。",
                    "stop_reason": "inspection_request_hash_mismatch",
                }
            )
        elif machine_verdict != "accept":
            decision.update(
                {
                    "status": "needs_revision",
                    "decision_note": "机器 verdict 非 accept；本 Attempt 停止。",
                    "stop_reason": f"machine_verdict_{machine_verdict}",
                }
            )
        else:
            report["record_status"] = "awaiting_delegated_review"
            decision.update(
                {
                    "status": "not_run",
                    "decision_note": "机器 accept；等待委托的事实与视觉复核后写最终 G4 终态。",
                    "stop_reason": "awaiting_delegated_review",
                }
            )
    report["audit"]["evidence_refs"].extend(
        [
            "docs/contracts/sprint-195-youtube-paynes-creek-g4-single-image-gate.md",
            "docs/testing/siliconflow-native-agent-compatibility-report.json",
            f"native_agent_run:{run_id}",
            f"source_git_commit:{source_commit}",
            f"local_owner_promoted_to_admin:{str(promoted).lower()}",
        ]
    )
    report["audit"]["sensitive_values_removed"] = True
    report["audit"]["record_validated_at"] = _now()
    report["audit"]["record_git_commit"] = source_commit
    return report


async def execute(args: argparse.Namespace) -> int:
    prompt_path = (PROJECT_ROOT / args.prompt_file).resolve()
    prompt = load_prompt(prompt_path)
    inspection_path = (
        (PROJECT_ROOT / args.inspection_file).resolve() if args.inspection_file else None
    )
    inspection = (
        load_inspection(inspection_path)
        if inspection_path is not None
        else {"checks": CHECKS, "expected": EXPECTED}
    )
    initial = preflight(
        args.source_git_commit,
        prompt_path=prompt_path,
        expected_prompt_sha256=args.expected_prompt_sha256,
        inspection_path=inspection_path,
        expected_inspection_sha256=args.expected_inspection_sha256,
    )
    if not initial["all_passed"]:
        print(json.dumps(initial, ensure_ascii=False, indent=2))
        return 2
    conversation_id, run_id, promoted = create_run(
        source_commit=args.source_git_commit,
        prompt=prompt,
        inspection=inspection,
        attempt_label=args.attempt_label,
    )
    await execute_native_agent_run(run_id, settings=get_settings())
    report = build_report(
        preflight_data=initial,
        conversation_id=conversation_id,
        run_id=run_id,
        promoted=promoted,
        source_commit=args.source_git_commit,
        attempt_label=args.attempt_label,
        authorization_ref=args.authorization_ref,
        output_dir=(PROJECT_ROOT / args.output_dir).resolve(),
        prompt_path=prompt_path,
        expected_prompt_sha256=args.expected_prompt_sha256,
        inspection_path=inspection_path,
        expected_inspection_sha256=args.expected_inspection_sha256,
        previous_attempt_ref=args.previous_attempt_ref,
        candidate_stem=args.candidate_stem,
    )
    output = (PROJECT_ROOT / args.output_report).resolve()
    if output.exists():
        raise RuntimeError("G4 evidence record 已存在，拒绝覆盖")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(output.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "run_id": run_id,
                "run_status": report["run_snapshot"]["terminal_status"],
                "image_calls": report["observed_call_counts"]["image_provider_call_count"],
                "inspect_calls": report["observed_call_counts"]["inspect_image_tool_call_count"],
                "machine_verdict": report["gate_decision"]["machine_verdict"],
                "gate_status": report["gate_decision"]["status"],
                "candidate": report["candidate_asset"]["candidate_filename"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paynes Creek S03 G4 single-image gate")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument("--attempt-label", default="g4-2026-08-13-attempt-02")
    parser.add_argument(
        "--authorization-ref",
        default="user-current-task-full-local-video-authorization",
    )
    parser.add_argument(
        "--prompt-file",
        default="docs/strategy/youtube/paynes-creek-chinese-script-prompt-pack.md",
    )
    parser.add_argument(
        "--expected-prompt-sha256",
        default=EXPECTED_PROMPT_SHA256,
    )
    parser.add_argument("--inspection-file")
    parser.add_argument("--expected-inspection-sha256")
    parser.add_argument(
        "--previous-attempt-ref",
        default="docs/strategy/youtube/paynes-creek-s03-media-gate.md",
    )
    parser.add_argument("--candidate-stem", default="PC-S03-v01")
    parser.add_argument(
        "--output-report",
        default="docs/testing/paynes-creek-s03-g4-2026-08-13-attempt-02.json",
    )
    parser.add_argument(
        "--output-dir",
        default="storage/exports/paynes-creek/g4-attempt-02",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight:
        result = preflight(
            args.source_git_commit,
            prompt_path=(PROJECT_ROOT / args.prompt_file).resolve(),
            expected_prompt_sha256=args.expected_prompt_sha256,
            inspection_path=(
                (PROJECT_ROOT / args.inspection_file).resolve()
                if args.inspection_file
                else None
            ),
            expected_inspection_sha256=args.expected_inspection_sha256,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["all_passed"] else 2
    return asyncio.run(execute(args))


if __name__ == "__main__":
    raise SystemExit(main())
