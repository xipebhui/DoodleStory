# DoodleStory Runtime Skills

产品运行时 Skill 固定放在 `backend/app/agent_skills/<skill-name>/SKILL.md`。这里的
Skill 由 DoodleStory Agent Runtime 在服务启动时扫描，与仓库根目录供 Codex 开发协作使用的
`.agents/skills/` 无关。

每个 `SKILL.md` 必须：

- 使用 UTF-8；
- 小于等于 64 KiB；
- 以仅包含 `name`、`description`、`version` 的 frontmatter 开始；
- `name` 与目录名完全一致，并使用小写字母、数字和连字符；
- `version` 是正整数，任何影响运行行为的正文变化都必须递增版本。

Runtime 自动计算完整文件的 SHA-256。基础 Agent instructions 只获得有界 catalog 元数据；
只有通过只读 `load_skill` Tool 才能取得完整文件正文。
