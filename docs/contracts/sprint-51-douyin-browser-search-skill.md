# Sprint 51 合同：抖音 Skill 集成浏览器态搜索采集

## 目标

把前面确认的“方案 2”落到项目内 `douyin-hot-sample-research` Skill：使用已登录浏览器的 `storage_state` 打开抖音搜索页，监听真实页面加载的搜索接口响应，提取最近图文候选样本，作为 `douyin-downloader` 直连搜索被风控时的研究入口。

## 范围内

- 在 Skill 自有目录增加浏览器态搜索采集脚本，代码独立于主业务后端。
- 采集脚本读取外部登录态 `storage_state`，不打印 Cookie 值。
- 监听 `/aweme/v1/web/general/search/single/` 响应并输出 raw response、全部候选、图文候选、meta 和 summary。
- 更新 Skill 工作流，明确优先用浏览器态搜索做关键词调研，再把选中的样本交给 `douyin-downloader` 下载。
- 更新样本字段参考，记录浏览器态采集来源、响应路径、搜索响应数量和图文筛选证据。
- 更新 `docs/progress.md`。

## 范围外

- 不包装 API 服务。
- 不修改 DoodleStory 后端内容提取链路。
- 不下载或复制第三方仓库代码到主业务目录。
- 不自动绕过抖音验证码、风控或登录校验。
- 不实现定时任务、批量调度或发布链路。

## 交付物

- `.agents/skills/douyin-hot-sample-research/scripts/browser_search_collect.py`
- `.agents/skills/douyin-hot-sample-research/SKILL.md`
- `.agents/skills/douyin-hot-sample-research/references/research-fields.md`
- `.agents/skills/douyin-hot-sample-research/agents/openai.yaml`
- `docs/progress.md`

## 完成标准

- 后续 agent 可以用一条命令基于 `social-auto-upload` 的浏览器登录态采集抖音关键词搜索结果。
- 输出文件足够支撑热门样本库筛选：raw response、全部候选、图文候选、summary 和 meta。
- Skill 明确浏览器态搜索只是调研入口，下载、评论、图片理解仍按现有 `douyin-downloader` 与 DoodleStory VL 边界执行。
- 未引入默认兜底、mock 或静默忽略。

## 验证

```bash
/Users/pengfei.shi/workspace/tmp-project/social-auto-upload/.venv/bin/python .agents/skills/douyin-hot-sample-research/scripts/browser_search_collect.py --help
python3 -m py_compile .agents/skills/douyin-hot-sample-research/scripts/browser_search_collect.py .agents/skills/douyin-hot-sample-research/scripts/summarize_samples.py
python3 /Users/pengfei.shi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/douyin-hot-sample-research
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 本次只做脚本与 Skill 集成验证，不默认打开真实浏览器采集；真实采集会启动已登录浏览器并可能触发平台验证码，应在用户明确开始采集时运行。

## 风险 / 说明

- 浏览器态搜索依赖真实登录态、页面结构和搜索接口路径，平台变更时需要重新检查。
- 采集输出包含公开搜索响应和作品元信息，不应提交到 Git。
- 如果需要下载外部代码，应放到独立目录供 Skill 调用；本次不需要下载外部代码，脚本直接放在 Skill 自有 `scripts/` 下。

## Handoff

- 下一步：用 `故事` 等关键词运行浏览器态采集，再按图文候选 summary 选择少量样本交给 `douyin-downloader` 下载和 VL 抽检。
