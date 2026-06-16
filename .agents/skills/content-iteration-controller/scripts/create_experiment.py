#!/usr/bin/env python3
"""Create a file-based content experiment workspace."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def normalize_experiment_id(value: str | None) -> str:
    if value:
        text = value.strip()
    else:
        text = f"{datetime.now().strftime('%Y-%m-%d')}-cycle-01"
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", text):
        raise ValueError("experiment_id only supports letters, digits, dot, underscore, and hyphen")
    return text


def write_if_needed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def experiment_markdown(experiment_id: str, title: str) -> str:
    return f"""# {title}

- experiment_id: `{experiment_id}`
- status: `draft`
- created_at: `{datetime.now().isoformat(timespec="seconds")}`

## 实验目标

填写本轮要验证的内容机制。不要写成“看看能不能爆”，要写成可检查的假设。

## 市场证据

关联市场扫描、样本评分、账号分析、评论分析和 VL 证据路径。

## 本轮固定变量

- 账号：
- 类目：
- 叙事人格：
- 视觉风格：
- 发布时间窗口：
- 内容长度：

## 本轮只改变的主要变量

填写一个变量，例如首图承诺、标题结构、真实感结尾、故事机制或账号。

## 发布计划摘要

发布前同步更新 `publish_plan.json`。

## 复盘入口

发布后把真实数据放入 `post_results/`，再更新 `deviation_review.md` 和 `strategy_update.json`。
"""


def prediction_json(title: str) -> dict[str, object]:
    return {
        "version": 1,
        "status": "draft",
        "title": title,
        "hypothesis": "",
        "expected_metric": "",
        "account_group": [],
        "fixed_variables": {
            "category": "",
            "narrative_persona": "",
            "visual_style": "",
            "publish_window": "",
            "story_length": "",
        },
        "changed_variable": "",
        "narrative_persona_profile": {
            "profile_id": "",
            "label": "",
            "crowd_desire": "",
            "moral_position": "",
            "emotion_curve": "",
            "taboo_boundary": "",
            "comment_trigger": "",
            "account_packaging": {
                "nickname_direction": "",
                "avatar_direction": "",
                "bio_direction": "",
            },
        },
        "review_checkpoints": ["2h", "24h", "72h"],
        "market_evidence": [],
        "risk_notes": [],
        "decision_gate": {
            "allow_publish_review": False,
            "reason": "Fill prediction before publishing; post-review is blocked until this is complete.",
        },
    }


def publish_plan_json() -> dict[str, object]:
    return {
        "version": 1,
        "status": "draft",
        "posts": [],
        "notes": "Each post should include account, content_id, planned_publish_time, and controlled variation.",
    }


def strategy_update_json() -> dict[str, object]:
    return {
        "version": 1,
        "status": "draft",
        "strongest_evidence": "",
        "largest_misread_risk": "",
        "next_changed_variable": "",
        "narrative_persona_review": {
            "persona_matched_content": "",
            "persona_misread_risk": "",
            "account_packaging_adjustment": "",
        },
        "observations_only": [],
        "rule_update_candidates": [],
        "skill_update_allowed": False,
        "skill_update_reason": "Rule upgrades require repeated evidence and user confirmation.",
    }


def deviation_review_markdown() -> str:
    return """# 偏差诊断

## 前置检查

- [ ] `prediction.json` 已在发布前完成。
- [ ] `post_results/` 已有真实发布数据。
- [ ] 本轮固定变量和改变变量清楚。

没有发布前预测时，本文件只能记录数据，不能做复盘结论。

## 当前最强证据

待填写。

## 当前最大误判风险

待填写。

## 预测与真实结果差距

待填写。

## 偏差归因

可选：`market_misread`、`account_mismatch`、`hook_failure`、`title_failure`、`story_mechanism_failure`、`visual_execution_failure`、`timing_noise`、`metric_mismatch`。

## 叙事人格复盘

- 本轮人格是否匹配内容机制：
- 大众欲望判断是否准确：
- 情绪曲线是否按预测发生：
- 道德站位是否过弱、过正或过激：
- 账号包装是否需要服务内容人格重新调整：

## 下一轮只改变一个主要变量

待填写。

## 只能记录为观察，不能升级成规则

待填写。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a content-lab experiment workspace.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="DoodleStory project root")
    parser.add_argument("--experiment-id", help="Stable experiment id")
    parser.add_argument("--title", required=True, help="Human-readable experiment title")
    parser.add_argument("--force", action="store_true", help="Overwrite existing experiment files")
    args = parser.parse_args()

    experiment_id = normalize_experiment_id(args.experiment_id)
    experiment_dir = args.root / "content-lab" / "experiments" / experiment_id
    written: list[str] = []
    skipped: list[str] = []

    files = {
        "experiment.md": experiment_markdown(experiment_id, args.title),
        "prediction.json": json.dumps(prediction_json(args.title), ensure_ascii=False, indent=2) + "\n",
        "publish_plan.json": json.dumps(publish_plan_json(), ensure_ascii=False, indent=2) + "\n",
        "deviation_review.md": deviation_review_markdown(),
        "strategy_update.json": json.dumps(strategy_update_json(), ensure_ascii=False, indent=2) + "\n",
        "post_results/.gitkeep": "",
    }

    for relative, content in files.items():
        path = experiment_dir / relative
        if write_if_needed(path, content, force=args.force):
            written.append(str(path))
        else:
            skipped.append(str(path))

    print(json.dumps({"experiment_id": experiment_id, "experiment_dir": str(experiment_dir), "written": written, "skipped": skipped}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
