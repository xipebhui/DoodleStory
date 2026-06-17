#!/usr/bin/env python3
"""Initialize Maze Controller file-state for DoodleStory content experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
STATE_DIR = PROJECT_ROOT / "content-lab" / "strategy_state"


TEXT_FILES: dict[str, str] = {
    "controller_constitution.md": """# 迷宫控制器宪法

## 使命

把混乱的抖音图文市场，压缩成越来越清楚的可验证内容机制。

## 永久禁忌

1. 没有真实证据，不输出市场结论。
2. 没有发布前预测，不做发布后复盘。
3. 没有连续证据，不升级 Skill 规则。
4. 同一轮实验不同时改变多个主要变量。
5. 不承诺爆款、变现、稳定万播或平台分发结果。

## 证据标准

- 市场证据来自最近样本、账号主页、评论、VL 点检和发布数据。
- 内部规则来自已经记录的成功假设、失败假设和预测误差。
- 单条异常只能记录观察，不能升级规则。
- 发布前必须写 `prediction.json`，发布后复盘必须引用真实结果。

## 规则升级门槛

- 同类成功 3 次，才允许进入候选成功规则。
- 同类失败 3 次，才允许进入失败规则或拒绝模式。
- 连续 10 条发布数据后，才能做批次复盘。
- 每周最多提出一次 Skill 升级建议。
- 修改 Skill 文件必须由用户明确确认。
""",
    "strategy_memory.md": """# 策略记忆

这里记录已经被多次证据支持的策略判断。不要记录单条样本带来的兴奋，也不要记录没有真实数据验证的猜测。

## 当前有效规则

- 暂无。等待真实实验数据写入。

## 候选观察

- 暂无。

## 待复核问题

- 哪些类目在最近 7 天有连续 A/B 样本？
- 哪些账号模式更适合 DoodleStory 复现？
- 哪些评论触发点能稳定转成下一轮选题？
""",
    "rubric.md": """# 内容实验判断 Rubric

## 市场证据

- 最近 7 天是否有多个样本支持同一机制？
- 是否排除了单个大号偶发爆款？
- 评论区是否说明用户真实讨论点？

## 账号适配

- 样本账号是否依赖大量粉丝或长期作品积累？
- 当前发布账号是否有相似受众和内容历史？
- 同一假设是否至少用 2 个账号测试？

## 内容机制

- 首图承诺是否清楚？
- 标题是否承诺了可兑现的故事结果？
- 结尾是否有清晰情绪、反转、证据或讨论点？

## 变量控制

- 本轮主要改变变量只能有一个。
- 其他变量必须写入 `fixed_variables`。
""",
    "rejected_patterns.md": """# 拒绝模式

记录被多次证伪或风险过高的内容机制。单次失败先写入 `prediction_errors.jsonl`，不要直接写到这里。

## 已拒绝

- 暂无。
""",
    "persona_wounds.md": """# 预测创伤记录

这里记录反复伤害系统判断质量的失败类型，用来提醒控制器不要重复犯错。

## 初始创伤

- 没有发布前预测的数据，无法用于学习。
- 单条高播放但无互动、无复现的内容，不能升级成规则。
- 只看热门样本、不看账号基线，会高估可模仿性。
- 只看评论、不看标题和故事结构，会被情绪噪音带偏。
- 只优化生成质量，不优化选题机制，会让系统停留在工具层。
""",
}


JSON_FILES: dict[str, object] = {
    "keyword_weights.json": {"version": 1, "weights": {}, "notes": "由真实实验复盘后更新，不根据单次扫描自动修改。"},
    "category_weights.json": {"version": 1, "weights": {}, "notes": "由多轮实验表现更新，不等于市场热度排名。"},
    "account_fit_profile.json": {"version": 1, "accounts": {}, "notes": "账号适配画像来自发布数据和复盘，不来自主观感觉。"},
    "account_style_bindings.json": {
        "version": 1,
        "accounts": {},
        "notes": "抖音发布账号到 DoodleStory style_id 的显式绑定。生成任务提交前必须先绑定账号画风，不使用默认风格。",
    },
    "narrative_persona_profiles.json": {
        "version": 1,
        "principle": "控制器人格统一；内容叙事人格按人群欲望、情绪曲线、道德站位和风险边界配置；账号包装服务内容人格。",
        "profiles": {
            "cold_observer": {
                "label": "冷眼旁观型",
                "best_for": ["伦理错位", "荒诞家庭", "县城怪谈感", "命运恶作剧"],
                "voice": "克制、冷、像旁观者记录离谱现实，不急着替任何人辩护。",
                "crowd_desire": "我知道这不太体面，但我想看这件事还能离谱到哪里。",
                "risk_boundary": "只写身份、称呼、位置和命运荒诞，不写未成年人、露骨暧昧或真实隐私。",
            },
            "female_venting": {
                "label": "替女性出气型",
                "best_for": ["婚姻边界", "婆媳冲突", "背叛", "长期委屈后的兑现"],
                "voice": "站位明确，替被忽视的人把委屈说出来，但避免滑向无差别性别对立。",
                "crowd_desire": "终于有人站在我这边，终于有人把账算清。",
                "risk_boundary": "可以有道德审判和情绪释放，不煽动网暴、人肉或现实伤害。",
            },
            "adult_clarity": {
                "label": "成年人清醒型",
                "best_for": ["长期情感账号", "关系边界", "亲密关系判断", "家庭秩序"],
                "voice": "不吵不骂，但句句拆边界；用清醒感制造信任。",
                "crowd_desire": "我需要一句清楚的话，替我确认这件事不是我太敏感。",
                "risk_boundary": "不把复杂关系简化成绝对仇恨，不承诺情感或人生结果。",
            },
            "absurd_fate": {
                "label": "命运荒诞型",
                "best_for": ["离谱人生", "身份塌陷", "称呼错位", "关系不断重组"],
                "voice": "像在讲一个越想越不对劲的命运玩笑，让读者追着看下一次塌陷。",
                "crowd_desire": "这不合理，但我想知道它怎么继续崩。",
                "risk_boundary": "所有角色必须安全成年化、虚构化，不把禁忌刺激写成露骨关系。",
            },
            "intimacy_trial": {
                "label": "亲密关系审判型",
                "best_for": ["他爱不爱你", "关键时刻是否站出来", "伴侣测试", "延迟兑现"],
                "voice": "把小事当作关系审判现场，让读者等一个最终态度。",
                "crowd_desire": "他到底会不会为了我站出来。",
                "risk_boundary": "不鼓励现实操控、跟踪、报复或危险测试。",
            },
        },
    },
}


JSONL_FILES = [
    "successful_hypotheses.jsonl",
    "failed_hypotheses.jsonl",
    "prediction_errors.jsonl",
]


def write_if_needed(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize content-lab strategy_state files.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="DoodleStory project root")
    parser.add_argument("--force", action="store_true", help="Overwrite existing controller state files")
    args = parser.parse_args()

    state_dir = args.root / "content-lab" / "strategy_state"
    written: list[str] = []
    skipped: list[str] = []

    for name, content in TEXT_FILES.items():
        path = state_dir / name
        if write_if_needed(path, content, force=args.force):
            written.append(str(path))
        else:
            skipped.append(str(path))

    for name, payload in JSON_FILES.items():
        path = state_dir / name
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if write_if_needed(path, content, force=args.force):
            written.append(str(path))
        else:
            skipped.append(str(path))

    for name in JSONL_FILES:
        path = state_dir / name
        if write_if_needed(path, "", force=args.force):
            written.append(str(path))
        else:
            skipped.append(str(path))

    for relative in ["experiments", "market_scans", "render_storyboards", "content_library/items"]:
        keep = args.root / "content-lab" / relative / ".gitkeep"
        if write_if_needed(keep, "", force=False):
            written.append(str(keep))
        else:
            skipped.append(str(keep))

    print(json.dumps({"state_dir": str(state_dir), "written": written, "skipped": skipped}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
