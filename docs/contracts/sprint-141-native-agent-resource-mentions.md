# Sprint 141：Native Agent 对话式资源引用

Status: Complete（Closed）

## Goal

把 Native Agent 输入区顶部的 Skill、创作账号、Style 和 YouTube 频道下拉框改为统一的
`@` 资源引用交互。用户在每一次对话提交前都可以从输入框打开资源菜单、搜索并添加真实资源，
所选资源以可移除标签展示，提交时继续映射到现有受约束的 Run 参数和不可变快照。

## User-visible outcome

- 输入 `@` 或点击输入框左侧资源按钮，打开类似 Codex 的资源选择菜单。
- 菜单可以搜索并分组展示 Skill、创作账号、Style、发布频道和审核视频。
- 选择资源后，输入框上方展示结构化标签；标签可以移除。
- 每次 Run 都可以重新增删当前上下文资源，不需要回到独立设置表单。
- 选择创作账号时自动携带该账号绑定的 Style；不能再额外选择一个冲突 Style。
- 选择发布频道后，可以继续添加审核视频并填写可见性与计划发布时间。

## Interaction direction

- 视觉主张：输入区是唯一工作面，资源是紧凑、清晰的上下文标签，不再展示配置表单墙。
- 内容结构：资源标签 → 文本输入 → 资源入口与发送动作 → 条件式发布参数。
- 交互重点：`@` 即时打开、搜索结果高亮与键盘上下/Enter 选择、选择后焦点返回输入框。

## In scope

- 移除 Native Agent composer 顶部的 Skill、创作账号、Style、频道下拉选择区。
- 新增 Native Agent 专用资源类型和纯函数，用于搜索、分组、互斥、替换及 payload 映射。
- 资源菜单支持：
  - 点击资源按钮打开；
  - 输入文本以 `@` 结尾时打开；
  - 搜索；
  - ArrowUp / ArrowDown 移动高亮；
  - Enter 选择；
  - Escape 关闭；
  - 点击外部关闭并把焦点返回输入框。
- 资源标签支持移除，并为账号绑定 Style 显示清晰的派生关系。
- Skill 必选规则保持不变，但错误提示改为用户语言。
- 发布确认、账号风格约束、Run 快照、重试和 Tool 白名单保持现有后端语义。
- 新增前端单元测试、生产构建和真实浏览器验收。

## Resource rules

- 每次 Run 最多一个 Skill。
- 每次 Run 最多一个创作账号。
- 每次 Run 最多一个直接 Style。
- 创作账号与直接 Style 互斥；添加账号会替换直接 Style，添加直接 Style会移除创作账号。
- 创作账号标签同时展示其绑定 Style，但请求只提交 `creation_channel_id`，Style 继续由后端推导。
- 每次 Run 最多一个发布频道和一个审核视频。
- 审核视频只有在选择发布频道后才可加入；移除频道时同时移除审核视频和发布参数。
- `重试` 沿用目标 Run 固定快照，当前资源标签不参与重试。

## Out of scope

- 不新增通用数据库资源表。
- 不改变 Native Agent Run API 字段、后端授权或快照模型。
- 不把尚未接入 Native Runtime 的旧 Agent Task、Panel、图片版本或 Character 假装成可用资源。
- 不在本 Sprint 接入历史素材库、Wikimedia、LOC 或 Internet Archive；菜单结构需允许后续增加这些类型。
- 不执行真实 YouTube 发布或收费模型 Run。

## Done means

- Native Agent 输入区不再出现 Skill、创作账号、Style 和频道的常驻下拉框。
- 用户可以只用键盘打开、搜索、选择和移除资源。
- 选择绑定风格账号后，标签展示账号与派生 Style，提交 payload 不包含可覆盖的 `style_id`。
- 直接 Style 与创作账号互斥，Skill/频道/视频按规则替换或清理。
- 选择发布频道和审核视频后才显示发布参数；提交前仍执行明确确认。
- 每轮 Run 的历史卡片继续展示实际 Skill、账号、Style 和发布频道快照。
- 前端测试、生产构建、项目检查和真实浏览器控制台验收通过。

## Verification

```bash
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

Browser check:

1. 输入 `@` 打开资源菜单，使用键盘选择验证 Skill。
2. 搜索并选择验证创作账号，确认标签同时显示绑定风格。
3. 添加直接 Style，确认创作账号被替换；再添加账号，确认 Style 被账号派生关系取代。
4. 添加发布频道和审核视频，确认发布参数按条件出现；移除频道后视频与参数一起清理。
5. 刷新和切换对话，确认页面没有错误，控制台无 error/warning。

## Completion evidence

- Native Agent composer 已删除 Skill、创作账号、Style、YouTube 频道和审核视频的常驻下拉框，
  改为统一的 `@` 资源按钮、搜索菜单和可移除标签。
- 输入内容以 `@` 结尾会打开菜单并移除触发字符；菜单支持搜索、上下方向键、Enter 选择和
  Escape 关闭，选择后焦点回到正文输入框。
- 新增独立 `nativeAgentResources.ts`，用纯函数固定单例替换、账号/Style 互斥、频道移除级联
  清理视频、禁用资源拒绝和成功提交后只清理一次性发布资源；14 项前端测试覆盖这些规则。
- 创作账号标签真实显示 `绑定 Style · 风格名`，请求仍只提交 `creation_channel_id`，直接
  `style_id` 保持为空，由 Sprint 140 后端约束唯一推导并快照 Style。
- 发布频道和审核视频也通过 `@` 添加；只有存在频道时才展示审核视频资源和紧凑发布参数，
  可见性改为三段按钮，移除频道会同时清理视频、时间和可见性状态。
- 真实浏览器使用验证管理员完成 `@` 打开、键盘选择 Skill、账号/Style 双向替换、频道参数
  显示和移除；页面控制台 0 error / 0 warning，未运行模型或触发真实发布。
- `./scripts/check.sh` 全部通过：338 项后端测试、空 SQLite 全量迁移、14 项前端测试、前端
  生产构建、Remotion TypeScript 检查和 5 项模板测试；`git diff --check` 通过。
